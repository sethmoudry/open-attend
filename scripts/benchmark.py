#!/usr/bin/env python3
"""Benchmark latency for Open Attend pipeline components.

Generates a synthetic audio chunk and transcript, then measures:
- MedASR transcription latency (p50, p95)
- Orchestrator chunk processing latency
- Individual tool call latencies
- End-to-end: audio -> sidebar update

Usage:
    python scripts/benchmark.py                     # default 10 runs, real LLM
    python scripts/benchmark.py --mock-llm          # mock LLM (fixed 50ms delay)
    python scripts/benchmark.py --runs 20           # 20 iterations
    python scripts/benchmark.py --output-dir results/  # custom output dir
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable, Coroutine

# Ensure backend is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))


# ---------------------------------------------------------------------------
# Synthetic test data
# ---------------------------------------------------------------------------

SAMPLE_TRANSCRIPT = (
    "Patient reports persistent headache for the past three days, "
    "rated 7 out of 10 in severity. She has been taking ibuprofen 400mg "
    "every 6 hours with minimal relief. She also mentions feeling dizzy "
    "when standing up quickly. No history of migraines. Family history "
    "significant for hypertension in her mother. She is currently on "
    "lisinopril 10mg daily and metformin 500mg twice daily for type 2 "
    "diabetes. No known drug allergies. She denies any recent head trauma "
    "or visual changes. Blood pressure today is 148/92."
)

SAMPLE_MEDICATIONS_TEXT = (
    "The patient is taking lisinopril 10mg daily, metformin 500mg twice daily, "
    "and has been using ibuprofen 400mg every 6 hours for her headache."
)

SAMPLE_SYMPTOMS = ["persistent headache", "dizziness on standing", "elevated blood pressure"]

SAMPLE_HISTORY = ["hypertension (mother)"]

SAMPLE_SECTION_DATA = {
    "chief_complaint_symptoms": SAMPLE_SYMPTOMS,
    "medications_reported": [
        {"name": "lisinopril", "dose": "10mg", "frequency": "daily"},
        {"name": "metformin", "dose": "500mg", "frequency": "twice daily"},
    ],
    "allergies": [],
    "family_history": SAMPLE_HISTORY,
}

SAMPLE_ASSESSMENT = (
    "Persistent headache likely tension-type vs secondary to uncontrolled hypertension. "
    "Blood pressure 148/92, above goal. Orthostatic dizziness may relate to medication "
    "timing or dehydration. Type 2 diabetes on metformin, stable."
)


# ---------------------------------------------------------------------------
# Mock LLM for --mock-llm mode
# ---------------------------------------------------------------------------

MOCK_DELAY_S = 0.05  # 50ms simulated latency

MOCK_RESPONSES: dict[str, dict] = {
    "default": {"_raw": "mock response"},
    "medications": {
        "medications": [
            {"name": "lisinopril", "dose": "10mg", "frequency": "daily"},
            {"name": "metformin", "dose": "500mg", "frequency": "twice daily"},
            {"name": "ibuprofen", "dose": "400mg", "frequency": "every 6 hours"},
        ]
    },
    "interactions": {
        "interactions": [
            {
                "drug_a": "lisinopril",
                "drug_b": "ibuprofen",
                "severity": "moderate",
                "mechanism": "NSAIDs may reduce antihypertensive effect of ACE inhibitors",
                "recommendation": "Monitor blood pressure closely",
            }
        ]
    },
    "differential": {
        "differential": [
            "Tension-type headache",
            "Hypertensive headache",
            "Medication overuse headache",
            "Orthostatic hypotension",
        ]
    },
    "red_flags": {"red_flags": []},
    "soap_section": {"text": "Patient presents with persistent headache for 3 days."},
    "chunk_analysis": {
        "symptoms": ["headache", "dizziness"],
        "allergies": [],
        "family_history": ["hypertension"],
        "exam_findings": ["BP 148/92"],
        "mental_health_signals": [],
        "alerts": [],
        "orders": [],
        "medications": [],
        "medication_source": "patient_reported",
        "soap_routing": "subjective",
        "soap_updates": {
            "subjective": "Headache x3 days, dizziness on standing.",
            "objective": "BP 148/92.",
        },
    },
    "icd10": {
        "codes": [
            {"code": "G43.1", "description": "Migraine with aura", "confidence": 0.92},
        ]
    },
    "cpt": {
        "codes": [
            {"code": "99214", "description": "Office visit, established", "confidence": 0.85},
        ]
    },
    "follow_ups": {
        "follow_ups": [
            {"action": "Neurology follow-up", "type": "referral", "timeframe": "4 weeks", "details": "Migraine with aura evaluation"},
        ]
    },
    "patient_summary": {
        "visit_summary": "You came in for a severe headache with visual changes.",
        "new_medications": ["Sumatriptan 50mg as needed for migraines"],
        "follow_up_steps": ["See neurologist in 4 weeks"],
        "when_to_seek_care": "If you experience the worst headache of your life, sudden vision loss, or weakness",
    },
}


def install_mock_llm() -> None:
    """Monkey-patch llm.call_medgemma_json with a mock that returns
    canned responses after a fixed delay."""
    import llm as llm_module

    _original = llm_module.call_medgemma_json

    async def _mock_call(prompt: str, **kwargs: Any) -> dict:
        await asyncio.sleep(MOCK_DELAY_S)
        # Try to match prompt to a known response type
        prompt_lower = prompt.lower()
        if "medication" in prompt_lower and "interaction" not in prompt_lower:
            return MOCK_RESPONSES["medications"]
        if "interaction" in prompt_lower:
            return MOCK_RESPONSES["interactions"]
        if "differential" in prompt_lower:
            return MOCK_RESPONSES["differential"]
        if "red flag" in prompt_lower:
            return MOCK_RESPONSES["red_flags"]
        if "icd" in prompt_lower:
            return MOCK_RESPONSES["icd10"]
        if "cpt" in prompt_lower:
            return MOCK_RESPONSES["cpt"]
        if "follow" in prompt_lower:
            return MOCK_RESPONSES["follow_ups"]
        if "summary" in prompt_lower and "patient" in prompt_lower:
            return MOCK_RESPONSES["patient_summary"]
        if "soap" in prompt_lower or "section" in prompt_lower:
            return MOCK_RESPONSES["soap_section"]
        # Orchestrator classification prompt
        if "chunk" in prompt_lower or "transcript" in prompt_lower:
            return MOCK_RESPONSES["chunk_analysis"]
        return MOCK_RESPONSES["default"]

    llm_module.call_medgemma_json = _mock_call  # type: ignore[attr-defined]
    llm_module.call_medgemma = lambda *a, **kw: asyncio.coroutine(  # type: ignore[attr-defined]
        lambda: json.dumps(MOCK_RESPONSES["default"])
    )()


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------


def compute_stats(timings: list[float]) -> dict[str, float]:
    """Compute p50, p95, mean, min, max from a list of durations (seconds)."""
    if not timings:
        return {"p50_ms": 0, "p95_ms": 0, "mean_ms": 0, "min_ms": 0, "max_ms": 0, "n": 0}
    sorted_t = sorted(timings)
    n = len(sorted_t)
    p50_idx = int(n * 0.50)
    p95_idx = min(int(n * 0.95), n - 1)
    return {
        "p50_ms": round(sorted_t[p50_idx] * 1000, 2),
        "p95_ms": round(sorted_t[p95_idx] * 1000, 2),
        "mean_ms": round(statistics.mean(sorted_t) * 1000, 2),
        "min_ms": round(sorted_t[0] * 1000, 2),
        "max_ms": round(sorted_t[-1] * 1000, 2),
        "n": n,
    }


def print_table(results: dict[str, dict]) -> None:
    """Print results in a clean table."""
    header = f"{'Scenario':<35} {'p50':>8} {'p95':>8} {'mean':>8} {'min':>8} {'max':>8} {'n':>4}"
    sep = "-" * len(header)
    print(f"\n{sep}")
    print(header)
    print(sep)
    for name, stats in results.items():
        print(
            f"{name:<35} "
            f"{stats['p50_ms']:>7.1f}ms "
            f"{stats['p95_ms']:>7.1f}ms "
            f"{stats['mean_ms']:>7.1f}ms "
            f"{stats['min_ms']:>7.1f}ms "
            f"{stats['max_ms']:>7.1f}ms "
            f"{stats['n']:>4}"
        )
    print(sep)


# ---------------------------------------------------------------------------
# Benchmark runners
# ---------------------------------------------------------------------------


async def bench_async(
    name: str,
    fn: Callable[..., Coroutine],
    args: tuple,
    kwargs: dict,
    runs: int,
) -> tuple[str, dict]:
    """Run an async function `runs` times and collect timings."""
    timings: list[float] = []
    for i in range(runs):
        t0 = time.perf_counter()
        try:
            await fn(*args, **kwargs)
        except Exception as exc:
            print(f"  [{name}] run {i+1}/{runs} FAILED: {exc}")
            continue
        elapsed = time.perf_counter() - t0
        timings.append(elapsed)
    return name, compute_stats(timings)


def load_test_audio() -> bytes:
    """Load test audio WAV bytes. Generate if missing."""
    wav_path = REPO_ROOT / "benchmarks" / "test_audio.wav"
    if not wav_path.exists():
        print("Test audio not found, generating...")
        from generate_test_audio import generate_speech_like_samples, write_wav

        samples = generate_speech_like_samples(16000 * 5, 16000)
        wav_path.parent.mkdir(parents=True, exist_ok=True)
        write_wav(wav_path, samples, 16000)
        print(f"  Generated {wav_path}")
    return wav_path.read_bytes()


# ---------------------------------------------------------------------------
# Individual scenario functions
# ---------------------------------------------------------------------------


async def scenario_transcribe(audio_bytes: bytes) -> Any:
    from transcribe import transcribe
    return await transcribe(audio_bytes)


async def scenario_extract_medications(text: str) -> Any:
    from tools import extract_medications
    return await extract_medications(text, chunk_id="bench")


async def scenario_check_interactions() -> Any:
    from models import Medication
    from tools import check_interactions

    meds = [
        Medication(name="lisinopril", dose="10mg", frequency="daily"),
        Medication(name="ibuprofen", dose="400mg", frequency="every 6 hours"),
        Medication(name="metformin", dose="500mg", frequency="twice daily"),
    ]
    return await check_interactions(meds)


async def scenario_build_differential() -> Any:
    from tools import build_differential
    return await build_differential(SAMPLE_SYMPTOMS, SAMPLE_HISTORY)


async def scenario_draft_soap_section() -> Any:
    from tools import draft_soap_section
    return await draft_soap_section("Subjective", SAMPLE_SECTION_DATA)


async def scenario_detect_red_flags(text: str) -> Any:
    from tools import detect_red_flags
    return await detect_red_flags(text, symptoms=SAMPLE_SYMPTOMS, chunk_id="bench")


async def scenario_extract_icd10(text: str) -> Any:
    from tools import extract_icd10_codes
    return await extract_icd10_codes(text)


async def scenario_extract_cpt(text: str) -> Any:
    from tools import extract_cpt_codes
    return await extract_cpt_codes(text)


async def scenario_extract_follow_ups(text: str) -> Any:
    from tools import extract_follow_ups
    return await extract_follow_ups(plan=text)


async def scenario_generate_summary() -> Any:
    from models import FollowUpItem, Medication, SOAPNote
    from tools import generate_patient_summary

    soap = SOAPNote(
        subjective="Headache x3 days.",
        objective="BP 148/92.",
        assessment="Tension headache vs hypertensive.",
        plan="Start topiramate, neurology referral.",
    )
    return await generate_patient_summary(soap, [Medication(name="topiramate")], [])


async def scenario_process_chunk(text: str) -> Any:
    from models import Session, Speaker, TranscriptChunk
    from orchestrator import process_chunk

    chunk = TranscriptChunk(
        id="bench_chunk",
        timestamp_start=0.0,
        timestamp_end=5.0,
        speaker=Speaker.PATIENT,
        text=text,
    )
    session = Session()
    return await process_chunk(chunk, session)


async def scenario_end_to_end(audio_bytes: bytes) -> Any:
    """Full pipeline: audio -> transcribe -> orchestrator."""
    from models import Session, Speaker, TranscriptChunk
    from orchestrator import process_chunk
    from transcribe import transcribe

    chunk = await transcribe(audio_bytes)
    if not chunk.text:
        # Use synthetic text if transcription returns empty (e.g. tone input)
        chunk.text = SAMPLE_TRANSCRIPT
    session = Session()
    return await process_chunk(chunk, session)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run_benchmarks(runs: int, output_dir: Path) -> dict:
    """Execute all benchmark scenarios and return aggregated results."""
    audio_bytes = load_test_audio()

    scenarios = [
        ("transcribe()", scenario_transcribe, (audio_bytes,), {}, True),
        ("extract_medications()", scenario_extract_medications, (SAMPLE_MEDICATIONS_TEXT,), {}, False),
        ("check_interactions()", scenario_check_interactions, (), {}, False),
        ("build_differential()", scenario_build_differential, (), {}, False),
        ("draft_soap_section()", scenario_draft_soap_section, (), {}, False),
        ("detect_red_flags()", scenario_detect_red_flags, (SAMPLE_TRANSCRIPT,), {}, False),
        ("extract_icd10_codes()", scenario_extract_icd10, (SAMPLE_ASSESSMENT,), {}, False),
        ("extract_cpt_codes()", scenario_extract_cpt, (SAMPLE_ASSESSMENT,), {}, False),
        ("extract_follow_ups()", scenario_extract_follow_ups, (SAMPLE_ASSESSMENT,), {}, False),
        ("generate_patient_summary()", scenario_generate_summary, (), {}, False),
        ("process_chunk() [orchestrator]", scenario_process_chunk, (SAMPLE_TRANSCRIPT,), {}, False),
        ("end_to_end: audio->update", scenario_end_to_end, (audio_bytes,), {}, True),
    ]

    results: dict[str, dict] = {}

    for name, fn, args, kwargs, requires_model in scenarios:
        if requires_model:
            try:
                # Probe if transcription model is available
                print(f"Running: {name} ({runs} iterations)...")
                _, stats = await bench_async(name, fn, args, kwargs, runs)
                results[name] = stats
                print(f"  -> p50={stats['p50_ms']:.1f}ms  p95={stats['p95_ms']:.1f}ms  mean={stats['mean_ms']:.1f}ms")
            except Exception as exc:
                print(f"  SKIPPED {name}: {exc}")
                results[name] = compute_stats([])
        else:
            print(f"Running: {name} ({runs} iterations)...")
            _, stats = await bench_async(name, fn, args, kwargs, runs)
            results[name] = stats
            print(f"  -> p50={stats['p50_ms']:.1f}ms  p95={stats['p95_ms']:.1f}ms  mean={stats['mean_ms']:.1f}ms")

    # Print summary table
    print_table(results)

    # Write JSON results
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to: {output_file}")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark latency for Open Attend pipeline components"
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=20,
        help="Number of iterations per scenario (default: 20)",
    )
    parser.add_argument(
        "--mock-llm",
        action="store_true",
        help="Replace LLM calls with a fixed-delay mock (50ms)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory for results.json (default: benchmarks/)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else REPO_ROOT / "benchmarks"

    if args.mock_llm:
        print("Using mock LLM (50ms fixed delay per call)")
        install_mock_llm()
    else:
        print(f"Using real LLM at {os.getenv('LLM_BASE_URL', 'http://localhost:8080/v1')}")

    print(f"Runs per scenario: {args.runs}\n")

    asyncio.run(run_benchmarks(args.runs, output_dir))


if __name__ == "__main__":
    main()

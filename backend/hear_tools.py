"""HeAR (Health Acoustic Representations) audio analysis tools.

Lazy-loads google/hear-pytorch to extract 512-dim health audio embeddings
from 2-second clips.  Uses the LLM to interpret embeddings in clinical context.
"""

import asyncio
import io
import logging
import os
from typing import Optional

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)

_hear_model = None
_SAMPLE_RATE = 16000
_WINDOW_SAMPLES = 2 * _SAMPLE_RATE  # 2 seconds = 32000 samples


def _load_hear():
    """Lazy-load the HeAR PyTorch model."""
    global _hear_model
    if _hear_model is not None:
        return _hear_model
    try:
        import torch
        from transformers import AutoModel

        logger.info("Loading google/hear-pytorch ...")
        hf_token = os.environ.get("HF_TOKEN")
        _hear_model = AutoModel.from_pretrained(
            "google/hear-pytorch",
            token=hf_token,
        )
        _hear_model.eval()
        logger.info("HeAR model loaded successfully")
        return _hear_model
    except Exception as exc:
        logger.error("Failed to load HeAR model: %s", exc)
        raise


def _slice_audio(wav_bytes: bytes, start_s: float, end_s: float) -> np.ndarray:
    """Slice WAV audio and return mono float32 array at 16 kHz."""
    audio, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32")
    # Convert to mono if stereo
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    # Resample if needed (simple linear interpolation)
    if sr != _SAMPLE_RATE:
        import scipy.signal
        num_samples = int(len(audio) * _SAMPLE_RATE / sr)
        audio = scipy.signal.resample(audio, num_samples)
    start_sample = int(start_s * _SAMPLE_RATE)
    end_sample = int(end_s * _SAMPLE_RATE)
    return audio[start_sample:end_sample]


def _preprocess_audio(raw_batch: "torch.Tensor") -> "torch.Tensor":
    """Convert raw 16 kHz audio to mel-PCEN spectrograms for HeAR.

    Matches Google's hear/python/data_processing/audio_utils.preprocess_audio.
    Input:  (batch, 32000) float32 waveform
    Output: (batch, 1, 192, 128) mel-PCEN spectrogram
    """
    import torch
    import torch.nn.functional as F

    # --- Mel filterbank (128 bins, 0-8000 Hz) ---
    n_fft = 400
    hop = 160
    n_mels = 128
    sr = _SAMPLE_RATE
    fmax = sr / 2.0

    # Mel-scale conversion helpers
    def hz_to_mel(f: float) -> float:
        return 2595.0 * np.log10(1.0 + f / 700.0)

    def mel_to_hz(m: float) -> float:
        return 700.0 * (10.0 ** (m / 2595.0) - 1.0)

    n_freqs = n_fft // 2 + 1
    mel_low = hz_to_mel(0.0)
    mel_high = hz_to_mel(fmax)
    mel_points = np.linspace(mel_low, mel_high, n_mels + 2)
    hz_points = np.array([mel_to_hz(m) for m in mel_points])
    bin_points = np.floor((n_fft + 1) * hz_points / sr).astype(int)

    filterbank = np.zeros((n_mels, n_freqs), dtype=np.float32)
    for i in range(n_mels):
        left, center, right = bin_points[i], bin_points[i + 1], bin_points[i + 2]
        for j in range(left, center):
            filterbank[i, j] = (j - left) / max(center - left, 1)
        for j in range(center, right):
            filterbank[i, j] = (right - j) / max(right - center, 1)

    mel_fb = torch.tensor(filterbank, dtype=torch.float32, device=raw_batch.device)

    # --- Normalize to [-1, 1] ---
    peak = raw_batch.abs().max(dim=-1, keepdim=True).values.clamp(min=1e-9)
    audio = raw_batch / peak

    # --- STFT → power spectrogram ---
    window = torch.hann_window(n_fft, device=audio.device)
    stft = torch.stft(audio, n_fft=n_fft, hop_length=hop, win_length=n_fft,
                       window=window, return_complex=True)
    power = stft.abs().pow(2)  # (batch, n_freqs, time)

    # --- Mel spectrogram ---
    mel = torch.matmul(mel_fb, power)  # (batch, n_mels, time)

    # --- PCEN (Per-Channel Energy Normalization) ---
    alpha = 0.8
    smooth_coef = 0.04
    delta = 2.0
    root = 2.0
    floor = 1e-6

    # Exponential moving average smoother along time axis
    ema = torch.zeros_like(mel[:, :, :1])
    ema_list = []
    for t in range(mel.shape[2]):
        ema = (1.0 - smooth_coef) * ema + smooth_coef * mel[:, :, t:t+1]
        ema_list.append(ema)
    ema_smooth = torch.cat(ema_list, dim=2)

    pcen = (mel / (floor + ema_smooth).pow(alpha) + delta).pow(1.0 / root) - delta ** (1.0 / root)

    # --- Resize to (192, 128) with bilinear interpolation ---
    pcen = pcen.unsqueeze(1)  # (batch, 1, n_mels, time)
    pcen = F.interpolate(pcen, size=(192, 128), mode="bilinear", align_corners=False)

    return pcen


def extract_embeddings(audio: np.ndarray) -> np.ndarray:
    """Extract HeAR embeddings from audio. Returns (n_windows, 512) array."""
    import torch

    model = _load_hear()

    # Chunk into 2-second windows
    windows = []
    for i in range(0, len(audio), _WINDOW_SAMPLES):
        window = audio[i : i + _WINDOW_SAMPLES]
        if len(window) < _WINDOW_SAMPLES:
            window = np.pad(window, (0, _WINDOW_SAMPLES - len(window)))
        windows.append(window)

    if not windows:
        return np.zeros((1, 512))

    batch = torch.tensor(np.stack(windows), dtype=torch.float32)

    # Convert raw audio to mel-PCEN spectrograms (HeAR expects (batch, 1, 192, 128))
    spectrograms = _preprocess_audio(batch)

    with torch.no_grad():
        output = model(spectrograms, return_dict=True, output_hidden_states=True)
        # HeAR ViT pooler projects CLS token (1024-dim) → 512-dim embedding
        embeddings = output.pooler_output

    return embeddings.cpu().numpy()


def _compute_audio_features(audio: np.ndarray) -> dict:
    """Compute basic audio features for LLM context."""
    rms = float(np.sqrt(np.mean(audio ** 2)))
    peak = float(np.max(np.abs(audio)))
    # Zero crossing rate
    zcr = float(np.mean(np.abs(np.diff(np.sign(audio))) > 0))
    # Spectral centroid approximation
    fft = np.abs(np.fft.rfft(audio))
    freqs = np.fft.rfftfreq(len(audio), d=1.0 / _SAMPLE_RATE)
    spectral_centroid = float(np.sum(freqs * fft) / (np.sum(fft) + 1e-10))
    # Energy variance (indicates intermittent sounds like coughing)
    frame_size = _SAMPLE_RATE // 10  # 100ms frames
    frame_energies = [
        np.mean(audio[i : i + frame_size] ** 2)
        for i in range(0, len(audio) - frame_size, frame_size)
    ]
    energy_variance = float(np.var(frame_energies)) if frame_energies else 0.0

    return {
        "rms_level": round(rms, 4),
        "peak_amplitude": round(peak, 4),
        "zero_crossing_rate": round(zcr, 4),
        "spectral_centroid_hz": round(spectral_centroid, 1),
        "energy_variance": round(energy_variance, 6),
        "duration_s": round(len(audio) / _SAMPLE_RATE, 2),
    }


async def analyze_audio_segment(
    wav_bytes: bytes,
    start_s: float,
    end_s: float,
    clinical_context: str = "",
) -> dict:
    """Run HeAR on a selected audio segment and return analysis results."""
    # 1. Slice audio
    audio = _slice_audio(wav_bytes, start_s, end_s)
    if len(audio) < _SAMPLE_RATE // 4:  # less than 250ms
        return {
            "detected_sounds": [],
            "clinical_relevance": "Segment too short for analysis.",
            "recommendation": "",
            "segment_duration": round((end_s - start_s), 2),
            "hear_model_used": True,
        }

    # 2. Extract HeAR embeddings (CPU-bound, run in thread)
    embeddings = await asyncio.to_thread(extract_embeddings, audio)
    mean_embedding = embeddings.mean(axis=0)

    # 3. Compute audio features for LLM context
    features = await asyncio.to_thread(_compute_audio_features, audio)

    # 4. Run enabled audio classifiers on embeddings
    classifier_results: dict[str, dict] = {}
    try:
        import classifier_registry

        for clf in classifier_registry.get_enabled_classifiers("audio"):
            preds = await classifier_registry.predict_audio(clf["id"], embeddings)
            if preds:
                classifier_results[clf["id"]] = {
                    "name": clf.get("name", clf["id"]),
                    "predictions": preds,
                }
    except Exception as exc:
        logger.warning("Audio classifier pipeline error: %s", exc)

    # 5. Interpret via LLM
    from llm import call_medgemma_json

    classifier_context = ""
    if classifier_results:
        classifier_context = "\n\nClassifier Predictions (from trained models on HeAR embeddings):\n"
        for clf_id, clf_data in classifier_results.items():
            classifier_context += f"  {clf_data['name']}:\n"
            for label, score in clf_data["predictions"].items():
                classifier_context += f"    - {label}: {score:.3f}\n"
        classifier_context += "\nUse these classifier predictions as PRIMARY evidence. They are from trained models and should be weighted heavily.\n"

    prompt = f"""You are a clinical audio analyst using Google's HeAR (Health Acoustic Representations) model.
You are analyzing a {features['duration_s']}s audio segment from a doctor-patient clinical visit.

The HeAR health acoustic foundation model (trained on 300M+ health audio clips) has processed this segment
and produced embeddings. Combined with the audio features below, classify what health-relevant sounds
are present.

Audio Features:
- RMS Level: {features['rms_level']} (higher = louder)
- Peak Amplitude: {features['peak_amplitude']}
- Zero Crossing Rate: {features['zero_crossing_rate']} (higher = more high-frequency content)
- Spectral Centroid: {features['spectral_centroid_hz']} Hz (tonal center)
- Energy Variance: {features['energy_variance']} (higher = intermittent/burst sounds like coughing)
- Duration: {features['duration_s']}s
- HeAR Embedding Norm: {float(np.linalg.norm(mean_embedding)):.2f}
- HeAR Windows Processed: {len(embeddings)}{classifier_context}

Clinical Context: {clinical_context or 'General clinical visit'}

Respond with JSON:
{{
  "detected_sounds": [
    {{"sound": "cough|wheeze|stridor|crackle|normal_breathing|speech|throat_clearing|silence|other",
      "confidence": 0.0-1.0,
      "description": "brief clinical description"}}
  ],
  "clinical_relevance": "summary of clinical significance",
  "recommendation": "any follow-up suggested based on findings, or empty string"
}}"""

    try:
        result = await call_medgemma_json(prompt, temperature=0.0, max_tokens=512)
    except Exception as exc:
        logger.warning("LLM interpretation failed: %s", exc)
        result = {
            "detected_sounds": [],
            "clinical_relevance": "Analysis completed but LLM interpretation unavailable.",
            "recommendation": "",
        }

    result["segment_duration"] = features["duration_s"]
    result["audio_features"] = features
    result["hear_model_used"] = True
    result["embedding_windows"] = len(embeddings)
    if classifier_results:
        result["classifier_predictions"] = classifier_results
    return result

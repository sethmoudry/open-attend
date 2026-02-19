"""E2E test: Landing → New Visit → Sample Playback → verify orchestrator output.

Requires:
  - SSH tunnel active: ssh -L 8000:localhost:8000 -p PORT root@ssh9.vast.ai
  - Backend running with sample audio
  - pip install playwright && playwright install chromium

Usage:
  python test/test_sample_e2e.py              # headless
  python test/test_sample_e2e.py --headed     # watch it run
  python test/test_sample_e2e.py --timeout 180  # extend wait (seconds)
"""

import argparse
import re
import sys
import time

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT = 240  # seconds to wait for orchestrator results


def run_test(headed: bool = False, timeout_s: int = DEFAULT_TIMEOUT):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context(permissions=["microphone"])
        page = context.new_page()
        page.set_default_timeout(30000)

        print("[1/7] Landing page — accepting disclaimer")
        page.goto(BASE_URL)
        page.click('button:has-text("Accept & Continue")')
        page.wait_for_url("**/dashboard")
        print("       -> Dashboard loaded")

        print("[2/7] Starting new visit")
        # Use "New Visit" or "Start First Visit" depending on state
        new_visit = page.locator('button:has-text("New Visit"), button:has-text("Start First Visit")')
        new_visit.first.click()
        page.wait_for_url("**/setup")
        print("       -> Visit setup loaded")

        print("[3/7] Filling visit form")
        page.fill("#patientName", "E2E Test Patient")
        # Check if chiefComplaint exists
        cc = page.locator("textarea#chiefComplaint")
        if cc.count() > 0:
            cc.fill("Persistent cough for 3 weeks, smoker")
        page.click('button:has-text("Start Recording")')
        page.wait_for_url(re.compile(r"/session/.+"), timeout=15000)
        session_url = page.url
        session_id = session_url.rstrip("/").split("/")[-1]
        print(f"       -> Session created: {session_id}")

        print("[4/7] Waiting for WebSocket connection")
        page.wait_for_selector('span:has-text("Connected")', timeout=15000)
        print("       -> WebSocket connected")

        print("[5/7] Starting sample playback")
        sample_btn = page.locator('header button:has-text("Sample")')
        sample_btn.click()
        print("       -> Sample started, waiting for first transcript chunk...")

        # Wait for transcript to appear — ASR can take 15-30s for first chunk
        page.wait_for_selector("div.group.flex.gap-3", timeout=60000)
        print("       -> First transcript chunk received!")

        print(f"[6/7] Waiting up to {timeout_s}s for orchestrator to process...")
        start = time.time()
        results = {
            "transcript_chunks": 0,
            "soap_populated": False,
            "medications_found": False,
            "alerts_found": False,
            "orders_found": False,
        }

        while time.time() - start < timeout_s:
            # Count transcript rows
            rows = page.locator("div.group.flex.gap-3").count()
            results["transcript_chunks"] = rows

            # Check SOAP sections have content
            page_text = page.locator("body").inner_text()
            results["soap_populated"] = any(
                kw in page_text for kw in ["Subjective", "cough", "lisinopril"]
            )
            results["medications_found"] = any(
                kw.lower() in page_text.lower()
                for kw in ["lisinopril", "warfarin", "ibuprofen"]
            )
            results["alerts_found"] = "Alert" in page_text or "alert" in page_text
            results["orders_found"] = any(
                kw.lower() in page_text.lower()
                for kw in ["chest x-ray", "CBC", "INR", "pulmonology"]
            )

            # Check if sample is still playing
            stop_btn = page.locator('header button:has-text("Stop")')
            still_playing = stop_btn.count() > 0 and stop_btn.is_visible()

            elapsed = int(time.time() - start)
            print(
                f"       [{elapsed:3d}s] chunks={rows} "
                f"soap={'Y' if results['soap_populated'] else 'N'} "
                f"meds={'Y' if results['medications_found'] else 'N'} "
                f"alerts={'Y' if results['alerts_found'] else 'N'} "
                f"orders={'Y' if results['orders_found'] else 'N'} "
                f"playing={'Y' if still_playing else 'N'}"
            )

            # If sample finished, wait for orchestrator to finish processing
            if not still_playing and results["transcript_chunks"] > 0:
                print("       -> Sample finished, waiting 30s for orchestrator...")
                time.sleep(30)
                break

            time.sleep(5)

        print("\n[7/7] Results")
        print("=" * 50)

        # Poll the session API for structured data
        api_resp = page.evaluate(
            f"""async () => {{
                const r = await fetch('{BASE_URL}/api/session/{session_id}');
                return await r.json();
            }}"""
        )

        session_data = api_resp
        soap = session_data.get("soap_note", {})
        meds = session_data.get("medications", [])
        alerts = session_data.get("clinical_alerts", [])
        orders = session_data.get("pending_orders", [])
        transcript = session_data.get("transcript_chunks", [])
        differential = session_data.get("differential", [])
        interactions = session_data.get("interaction_flags", [])

        print(f"  Transcript chunks:  {len(transcript)}")
        print(f"  SOAP Subjective:    {'Yes' if soap.get('subjective') else 'No'}")
        print(f"  SOAP Objective:     {'Yes' if soap.get('objective') else 'No'}")
        print(f"  SOAP Assessment:    {'Yes' if soap.get('assessment') else 'No'}")
        print(f"  SOAP Plan:          {'Yes' if soap.get('plan') else 'No'}")
        med_names = [m.get("name", "?") if isinstance(m, dict) else str(m) for m in meds]
        print(f"  Medications:        {len(meds)} — {med_names}")
        print(f"  Clinical Alerts:    {len(alerts)}")
        for a in alerts:
            if isinstance(a, dict):
                print(f"    - [{a.get('priority','?')}] {a.get('type','?')}: {a.get('message','?')[:80]}")
            else:
                print(f"    - {a}")
        print(f"  Interactions:       {len(interactions)}")
        print(f"  Pending Orders:     {len(orders)}")
        for o in orders:
            if isinstance(o, dict):
                print(f"    - {o.get('order_type','?')}: {o.get('description','?')}")
            else:
                print(f"    - {o}")
        print(f"  Differential:       {len(differential)}")
        for d in differential:
            if isinstance(d, dict):
                print(f"    - {d.get('condition','?')} ({d.get('likelihood','?')})")
            else:
                print(f"    - {d}")

        # Assertions
        passed = 0
        total = 6
        checks = [
            ("Transcript has entries", len(transcript) > 0),
            ("SOAP has content", bool(soap.get("subjective") or soap.get("objective"))),
            ("Medications extracted", len(meds) >= 1),
            ("Alerts generated", len(alerts) >= 1),
            ("Orders detected", len(orders) >= 1),
            ("Differential built", len(differential) >= 1),
        ]

        print("\n  Checks:")
        for label, ok in checks:
            status = "PASS" if ok else "FAIL"
            if ok:
                passed += 1
            print(f"    [{status}] {label}")

        print(f"\n  Score: {passed}/{total}")

        # Take a screenshot for review
        screenshot_path = "/tmp/openattend_e2e_result.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"  Screenshot saved: {screenshot_path}")

        browser.close()

        return passed == total


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--headed", action="store_true", help="Run with visible browser")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Max wait seconds")
    args = parser.parse_args()

    success = run_test(headed=args.headed, timeout_s=args.timeout)
    sys.exit(0 if success else 1)

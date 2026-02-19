# Playwright E2E Test Guide

Reference for agents writing Playwright tests against the Open Attend app.

## Prerequisites

- `pip install playwright && playwright install chromium`
- SSH tunnel active: `ssh -L 8000:localhost:8000 -p PORT root@ssh9.vast.ai`
- Backend running with sample audio at `backend/static/sample_conversation.wav`

## No data-testid Attributes

This codebase has **zero** `data-testid` attributes. All selectors are text-based or structural.

## Complete Click-Path: Landing → Sample Playback

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(permissions=["microphone"])
    page = context.new_page()

    # 1. Landing: accept disclaimer
    page.goto("http://localhost:8000")
    page.click('button:has-text("Accept & Continue")')
    page.wait_for_url("**/dashboard")

    # 2. Dashboard: start a new visit
    page.click('button:has-text("New Visit")')
    page.wait_for_url("**/setup")

    # 3. Setup: fill form + start (mic permission already granted)
    page.fill("#patientName", "Test Patient")
    page.click('button:has-text("Start Recording")')
    page.wait_for_url(re.compile(r"/session/.+$"))

    # 4. In-Room: wait for WebSocket, then play sample
    page.wait_for_selector('span:has-text("Connected")', timeout=10000)
    page.click('header button:has-text("Sample")')

    # 5. Wait for transcript chunks to appear (15-30s depending on ASR)
    page.wait_for_selector("div.group.flex.gap-3", timeout=60000)

    # 6. Let it run or stop
    page.click('header button:has-text("Stop")')

    browser.close()
```

## Key Selectors

### Header Controls (`/session/{id}`)

| Element | Selector | Notes |
|---|---|---|
| Sample button (idle) | `header button:has-text("Sample")` | Disabled while recording |
| Sample button (playing) | `header button:has-text("Stop")` | Same button, text changes |
| Record button | `header button:has-text("Record")` | Hidden during sample playback |
| Pause/Resume | `header button:has-text("Pause")` | Toggles to "Resume" |
| End Visit | `header button:has-text("End Visit")` | Opens confirmation modal |

### Landing Page (`/`)

| Element | Selector |
|---|---|
| Accept disclaimer | `button:has-text("Accept & Continue")` |

### Dashboard (`/dashboard`)

| Element | Selector |
|---|---|
| New Visit | `button:has-text("New Visit")` |
| First visit (empty state) | `button:has-text("Start First Visit")` |
| Session cards | `div[role="button"]` |

### Visit Setup (`/setup`)

| Element | Selector |
|---|---|
| Patient name | `input#patientName` |
| Visit type | `select#visitType` |
| Chief complaint | `textarea#chiefComplaint` |
| Start Recording | `button:has-text("Start Recording")` |

### In-Room Layout (`/session/{id}`)

| Element | Selector |
|---|---|
| Connection status | `span:has-text("Connected")` or `span:has-text("Offline")` |
| Transcript rows | `div.group.flex.gap-3` |
| Processing overlay | `text="Processing sample audio..."` |
| SOAP heading | `text="SOAP Note"` |
| Alerts heading | `text="Alerts"` |
| Pending Orders | `text="Pending Orders"` |

### Post-Visit (`/session/{id}/review`)

| Element | Selector |
|---|---|
| SOAP Editor sections | `text="Subjective"`, `text="Objective"`, etc. |
| Export bar | `text="Export"` |
| ICD-10 codes | `text="ICD-10"` |
| Patient summary | `text="Patient Summary"` |

## Sample Playback Progress

While playing:
- Progress bar inner: `.bg-clinical-500` (width % changes)
- Percentage text: `span` with `text-[10px]` class
- Overlay (before first chunk): `"Processing sample audio..."`

## Sample Audio API Endpoints

| Endpoint | Returns |
|---|---|
| `GET /api/sample-audio/info` | `{ duration, chunk_seconds[], total_chunks }` |
| `GET /api/sample-audio/full` | Full audio Blob (browser playback) |
| `GET /api/sample-audio/chunk/{index}` | Single VAD chunk Blob |
| `WS /ws/audio/{sessionId}` | WebSocket for binary audio chunks |

## Important Caveats

1. **Mic permission required** — `Start Recording` button stays disabled without it. Grant at context creation: `browser.new_context(permissions=["microphone"])`
2. **Don't click Record before Sample** — the Sample button is disabled while `isRecording || isPaused`
3. **ASR latency** — First transcript chunk takes 5-15s (Whisper loads model on first chunk, then processes 15s audio buffer). Use `timeout=60000` for first chunk.
4. **Polling interval** — Frontend polls `GET /session/{id}` every 2s for SOAP/alerts/meds updates
5. **Session state** — `status: "active"` during visit, `"completed"` after End Visit
6. **SPA routing** — All deep routes (`/session/{id}/review`) serve `index.html` via catch-all fallback

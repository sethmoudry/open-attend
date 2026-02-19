"""Evaluation pipeline configuration."""

import os

BACKEND_URL = os.getenv("EVAL_BACKEND_URL", "http://localhost:8000")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
ENTITY_CACHE_DIR = os.path.join(RESULTS_DIR, ".entity_cache")

# Stage 1 — Fareez OSCE
FAREEZ_COLLECTION_ID = 5545842
FAREEZ_ARTICLE_ID = 16550013
FAREEZ_SUBSET_SIZE = 25
FAREEZ_SPECIALTIES = ["RES", "MSK", "CAR", "GAS", "DER"]
FAREEZ_SPECIALTY_COUNTS = {"RES": 214, "MSK": 46, "CAR": 5, "GAS": 6, "DER": 1}
AUDIO_SAMPLE_RATE = 16000

# Scoring
ENTITY_FUZZY_THRESHOLD = 0.85
ROUGE_METRICS = ["rouge1", "rouge2", "rougeL"]
ROUGE_USE_STEMMER = True

# Stage 2 — ACI-Bench
ACI_BENCH_FIGSHARE_ARTICLE_ID = 22494601
ACI_SPLITS = ["clinicalnlp_taskB_test1", "clinicalnlp_taskC_test2"]
NOTE_FORMAT = "both"
LLM_JUDGE_ENABLED = False
LLM_JUDGE_SAMPLE_SIZE = 80

# Timeouts (seconds)
ASR_TIMEOUT = 900.0
LLM_TIMEOUT = 600.0

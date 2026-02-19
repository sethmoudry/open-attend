"""Generate Open Attend architecture diagrams with custom styling.

Requirements:
    pip install graphviz
    brew install graphviz   (or apt install graphviz)

Usage:
    python docs/generate_diagrams.py

Outputs PNGs to docs/diagrams/
"""

from pathlib import Path

import graphviz

OUT_DIR = Path(__file__).parent / "diagrams"
OUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
# MedGemma accent — bold teal/blue
MEDGEMMA_BG = "#0d9488"       # teal-600
MEDGEMMA_BG_LIGHT = "#ccfbf1" # teal-100
MEDGEMMA_BORDER = "#0f766e"   # teal-700
MEDGEMMA_TEXT = "#ffffff"

# Supporting models — muted gray
SUPPORT_BG = "#f1f5f9"        # slate-100
SUPPORT_BORDER = "#94a3b8"    # slate-400
SUPPORT_TEXT = "#475569"       # slate-600

# Clusters
CLUSTER_BG = "#f8fafc"        # slate-50
CLUSTER_BORDER = "#cbd5e1"    # slate-300

# Accent colors for tool categories
TOOL_MEDS = "#ef4444"         # red-500
TOOL_ALERTS = "#f97316"       # orange-500
TOOL_SOAP = "#3b82f6"         # blue-500
TOOL_DIFF = "#8b5cf6"         # violet-500
TOOL_ORDERS = "#eab308"       # yellow-500
TOOL_ROLES = "#6b7280"        # gray-500

# User flow colors
FLOW_BG = "#eff6ff"           # blue-50
FLOW_ACTIVE = "#2563eb"       # blue-600
FLOW_BORDER = "#93c5fd"       # blue-300

# Common graph attributes
COMMON_GRAPH = {
    "fontname": "Helvetica Neue,Helvetica,Arial,sans-serif",
    "bgcolor": "white",
    "pad": "0.6",
    "margin": "0.2",
    "dpi": "200",
}
COMMON_NODE = {
    "fontname": "Helvetica Neue,Helvetica,Arial,sans-serif",
    "fontsize": "11",
    "style": "filled",
    "penwidth": "1.5",
}
COMMON_EDGE = {
    "fontname": "Helvetica Neue,Helvetica,Arial,sans-serif",
    "fontsize": "9",
    "arrowsize": "0.8",
}


def _medgemma_node(g, name, label, **kwargs):
    """Large, bold MedGemma-branded node."""
    attrs = dict(
        shape="box", style="filled,rounded,bold",
        fillcolor=MEDGEMMA_BG, fontcolor=MEDGEMMA_TEXT,
        color=MEDGEMMA_BORDER, fontsize="13", penwidth="2.5",
        width="2.2", height="0.9",
    )
    attrs.update(kwargs)
    g.node(name, label, **attrs)


def _support_node(g, name, label, **kwargs):
    """Smaller, muted supporting model node."""
    attrs = dict(
        shape="box", style="filled,rounded",
        fillcolor=SUPPORT_BG, fontcolor=SUPPORT_TEXT,
        color=SUPPORT_BORDER, fontsize="10", penwidth="1.0",
        width="1.6", height="0.65",
    )
    attrs.update(kwargs)
    g.node(name, label, **attrs)


def _tool_node(g, name, label, color, **kwargs):
    """Tool node with accent left border."""
    g.node(name, label,
           shape="box", style="filled,rounded",
           fillcolor=f"{color}18", fontcolor=color,
           color=color, fontsize="10", penwidth="1.8",
           width="1.5", height="0.6",
           **kwargs)


def _io_node(g, name, label, **kwargs):
    """Input/output node (rounded pill)."""
    g.node(name, label,
           shape="ellipse", style="filled",
           fillcolor="#e2e8f0", fontcolor="#334155",
           color="#94a3b8", fontsize="10", penwidth="1.2",
           **kwargs)


def _flow_node(g, name, label, description="", active=False, **kwargs):
    """User flow page node."""
    bg = FLOW_ACTIVE if active else "#ffffff"
    fc = "#ffffff" if active else "#1e293b"
    border = FLOW_ACTIVE if active else FLOW_BORDER
    pw = "2.5" if active else "1.5"
    full_label = f"<<b>{label}</b><br/><font point-size='9' color='{'#dbeafe' if active else '#64748b'}'>{description}</font>>" if description else f"<<b>{label}</b>>"
    g.node(name, full_label,
           shape="box", style="filled,rounded",
           fillcolor=bg, fontcolor=fc,
           color=border, fontsize="12", penwidth=pw,
           width="2.0", height="0.8",
           **kwargs)


# ---------------------------------------------------------------------------
# Diagram 1: System Architecture (end-to-end)
# ---------------------------------------------------------------------------
def diagram_system_overview():
    g = graphviz.Digraph("system_overview", format="png",
                         engine="dot")
    g.attr(**COMMON_GRAPH, rankdir="LR", nodesep="0.6", ranksep="1.6",
           splines="spline", label="Open Attend — System Architecture",
           labelloc="t", fontsize="20", fontcolor="#0f172a")
    g.node_attr.update(**COMMON_NODE)
    g.edge_attr.update(**COMMON_EDGE)

    # --- Frontend ---
    with g.subgraph(name="cluster_frontend") as c:
        c.attr(label="Frontend", style="rounded,filled",
               fillcolor="#f0f9ff", color="#93c5fd", fontcolor="#1e40af",
               fontsize="12")
        c.node("physician", "Physician\nBrowser",
               shape="house", fillcolor="#dbeafe", color="#3b82f6",
               fontcolor="#1e40af", fontsize="10")

    # --- Audio Ingestion ---
    with g.subgraph(name="cluster_audio") as c:
        c.attr(label="Audio Ingestion", style="rounded,filled",
               fillcolor=CLUSTER_BG, color=CLUSTER_BORDER, fontcolor="#475569",
               fontsize="11")
        c.node("ws", "WebSocket\naudio_ws.py",
               shape="box", style="filled,rounded",
               fillcolor="#e2e8f0", color="#94a3b8", fontcolor="#475569",
               fontsize="9")
        c.node("buffer", "AudioBuffer\n15s batches",
               shape="box", style="filled,rounded",
               fillcolor="#e2e8f0", color="#94a3b8", fontcolor="#475569",
               fontsize="9")

    # --- ASR ---
    with g.subgraph(name="cluster_asr") as c:
        c.attr(label="Dual ASR + Diarization", style="rounded,filled",
               fillcolor=CLUSTER_BG, color=CLUSTER_BORDER, fontcolor="#475569",
               fontsize="11")
        _support_node(c, "whisper", "Whisper base\ngeneral ASR")
        _support_node(c, "medasr", "MedASR 105M\nmedical vocab CTC")
        _support_node(c, "pyannote", "Pyannote 3.1\nspeaker diarization")
        c.node("merge", "Entity-Guided\nMerge",
               shape="box", style="filled,rounded",
               fillcolor="#ccfbf1", color="#14b8a6", fontcolor="#0f766e",
               fontsize="10", penwidth="1.5")

    # --- Orchestrator (MedGemma prominent) ---
    with g.subgraph(name="cluster_orch") as c:
        c.attr(label="", style="rounded,filled",
               fillcolor=MEDGEMMA_BG_LIGHT, color=MEDGEMMA_BORDER,
               fontsize="12", penwidth="2.5")
        _medgemma_node(c, "orchestrator",
                       "MedGemma 27B\nOrchestrator Agent")
        with c.subgraph(name="cluster_tools") as t:
            t.attr(label="Clinical Tools (concurrent)", style="rounded,filled",
                   fillcolor="#ffffff", color="#d1d5db", fontcolor="#6b7280",
                   fontsize="10")
            _tool_node(t, "meds", "Medications\n+ Interactions", TOOL_MEDS)
            _tool_node(t, "alerts", "Alerts\n+ Red Flags", TOOL_ALERTS)
            _tool_node(t, "soap", "SOAP\nDraft", TOOL_SOAP)
            _tool_node(t, "diff", "Differential\nDiagnosis", TOOL_DIFF)
            _tool_node(t, "orders", "Orders\n+ Referrals", TOOL_ORDERS)

    # --- Multimodal (MedGemma prominent) ---
    with g.subgraph(name="cluster_multi") as c:
        c.attr(label="Multimodal Analysis", style="rounded,filled",
               fillcolor=MEDGEMMA_BG_LIGHT, color=MEDGEMMA_BORDER,
               fontsize="12", penwidth="2.0")
        _medgemma_node(c, "vision", "MedGemma 4B-IT\nMedical Vision")
        _support_node(c, "siglip", "MedSigLIP\n+ FAISS retrieval")
        _support_node(c, "hear", "HeAR\naudio embeddings")
        c.node("clf", "Classifier\nRegistry",
               shape="box", style="filled,rounded,dashed",
               fillcolor="#fff7ed", color="#f97316", fontcolor="#c2410c",
               fontsize="9", penwidth="1.5")

    # --- Storage ---
    with g.subgraph(name="cluster_store") as c:
        c.attr(label="Storage + Post-Visit", style="rounded,filled",
               fillcolor=CLUSTER_BG, color=CLUSTER_BORDER, fontcolor="#475569",
               fontsize="11")
        c.node("db", "Session Store\nAES-256 encrypted",
               shape="cylinder", fillcolor="#e2e8f0", color="#64748b",
               fontcolor="#334155", fontsize="10")
        c.node("postvisit", "ICD-10 / CPT\nSummary / Export",
               shape="box", style="filled,rounded",
               fillcolor="#e2e8f0", color="#94a3b8", fontcolor="#475569",
               fontsize="9")

    # --- Edges ---
    g.edge("physician", "ws", label="PCM audio", color="#3b82f6",
           penwidth="2.0", style="bold")
    g.edge("ws", "buffer", color="#64748b")
    g.edge("buffer", "whisper", color="#94a3b8")
    g.edge("buffer", "medasr", color="#94a3b8")
    g.edge("buffer", "pyannote", color="#94a3b8", style="dashed")
    g.edge("medasr", "merge", color="#14b8a6")
    g.edge("whisper", "merge", color="#14b8a6")
    g.edge("pyannote", "merge", color="#94a3b8", style="dashed")

    g.edge("merge", "orchestrator", label="transcript chunks",
           color=MEDGEMMA_BG, penwidth="2.5", style="bold")

    g.edge("orchestrator", "meds", color=TOOL_MEDS, penwidth="1.5")
    g.edge("orchestrator", "alerts", color=TOOL_ALERTS, penwidth="1.5")
    g.edge("orchestrator", "soap", color=TOOL_SOAP, penwidth="1.5")
    g.edge("orchestrator", "diff", color=TOOL_DIFF, penwidth="1.5")
    g.edge("orchestrator", "orders", color=TOOL_ORDERS, penwidth="1.5")

    for tool in ["meds", "alerts", "soap", "diff", "orders"]:
        g.edge(tool, "db", color="#94a3b8", style="dashed", arrowsize="0.6")

    g.edge("hear", "clf", color="#f97316", style="dashed")
    g.edge("vision", "clf", color="#f97316", style="dashed")
    g.edge("clf", "orchestrator", label="predictions",
           color="#f97316", style="bold", penwidth="1.5")
    g.edge("siglip", "orchestrator", label="similar cases",
           color="#94a3b8", style="dashed")

    g.edge("db", "physician", label="REST poll",
           color="#16a34a", penwidth="2.0", style="bold")
    g.edge("db", "postvisit", color="#94a3b8", style="dotted")

    g.render(str(OUT_DIR / "system_overview"), cleanup=True)


# ---------------------------------------------------------------------------
# Diagram 2: Orchestrator Agent Flow
# ---------------------------------------------------------------------------
def diagram_orchestrator_flow():
    g = graphviz.Digraph("orchestrator_flow", format="png", engine="dot")
    g.attr(**COMMON_GRAPH, rankdir="TB", nodesep="0.6", ranksep="1.0",
           splines="spline",
           label="Open Attend — Orchestrator Agent Flow",
           labelloc="t", fontsize="20", fontcolor="#0f172a")
    g.node_attr.update(**COMMON_NODE)
    g.edge_attr.update(**COMMON_EDGE)

    # Input
    _io_node(g, "chunk", "Transcript Chunk\n+ Speaker Role + Context")

    # Step 1: Classification
    with g.subgraph(name="cluster_classify") as c:
        c.attr(label="Step 1 — Chunk Classification", style="rounded,filled",
               fillcolor=MEDGEMMA_BG_LIGHT, color=MEDGEMMA_BORDER,
               fontcolor="#0f766e", fontsize="12", penwidth="2.0")
        _medgemma_node(c, "classify",
                       "MedGemma 27B\nChunk Classifier\norchestrator.md")

    # Step 2: Tool dispatch
    with g.subgraph(name="cluster_dispatch") as c:
        c.attr(label="Step 2 — Concurrent Tool Dispatch (Fibonacci-throttled)",
               style="rounded,filled",
               fillcolor="#f8fafc", color="#cbd5e1",
               fontcolor="#475569", fontsize="11")
        _tool_node(c, "t_meds", "extract_medications()\ncheck_interactions()\n30s throttle", TOOL_MEDS)
        _tool_node(c, "t_alerts", "generate_alerts()\ndetect_red_flags()\n30s throttle", TOOL_ALERTS)
        _tool_node(c, "t_diff", "build_differential()\n60s throttle", TOOL_DIFF)
        _tool_node(c, "t_soap", "draft_full_soap()\nevery batch", TOOL_SOAP)
        _tool_node(c, "t_orders", "extract_orders()\non detection", TOOL_ORDERS)
        _tool_node(c, "t_roles", "assign_roles()\nwhen enough context", TOOL_ROLES)

    # Step 3: SOAP routing
    with g.subgraph(name="cluster_soap") as c:
        c.attr(label="Step 3 — Speaker-Aware SOAP Routing",
               style="rounded,filled",
               fillcolor="#f0fdf4", color="#86efac",
               fontcolor="#166534", fontsize="11")
        for section, desc, color in [
            ("subj", "Subjective", "#22c55e"),
            ("obj", "Objective", "#16a34a"),
            ("assess", "Assessment", "#15803d"),
            ("plan_s", "Plan", "#166534"),
        ]:
            g.node(section, f"{desc}",
                   shape="box", style="filled,rounded",
                   fillcolor=f"{color}22", fontcolor=color,
                   color=color, fontsize="10", penwidth="1.5",
                   width="1.2")

    # Session
    g.node("session", "Session Store\nSOAP + meds + alerts + differential + orders",
           shape="cylinder", fillcolor="#e2e8f0", color="#64748b",
           fontcolor="#334155", fontsize="10")

    # Edges
    g.edge("chunk", "classify", color=MEDGEMMA_BG, penwidth="2.0")

    g.edge("classify", "t_meds", label="meds\nmentioned", color=TOOL_MEDS, penwidth="1.5")
    g.edge("classify", "t_alerts", label="red flags", color=TOOL_ALERTS, penwidth="1.5")
    g.edge("classify", "t_diff", label="new\nsymptoms", color=TOOL_DIFF, penwidth="1.5")
    g.edge("classify", "t_soap", label="every\nbatch", color=TOOL_SOAP, penwidth="1.5")
    g.edge("classify", "t_orders", label="orders\nverbalized", color=TOOL_ORDERS, penwidth="1.5")
    g.edge("classify", "t_roles", label="enough\ncontext", color=TOOL_ROLES, penwidth="1.2")

    g.edge("t_soap", "subj", color="#22c55e", penwidth="1.5")
    g.edge("t_soap", "obj", color="#16a34a", penwidth="1.5")
    g.edge("t_soap", "assess", color="#15803d", penwidth="1.5")
    g.edge("t_soap", "plan_s", color="#166534", penwidth="1.5")

    for tool in ["t_meds", "t_alerts", "t_diff", "t_soap", "t_orders", "t_roles"]:
        g.edge(tool, "session", color="#94a3b8", style="dashed", arrowsize="0.6")

    g.render(str(OUT_DIR / "orchestrator_flow"), cleanup=True)


# ---------------------------------------------------------------------------
# Diagram 3: Model Stack (MedGemma prominent, others muted)
# ---------------------------------------------------------------------------
def diagram_model_stack():
    g = graphviz.Digraph("model_stack", format="png", engine="dot")
    g.attr(**COMMON_GRAPH, rankdir="TB", nodesep="0.8", ranksep="1.2",
           splines="spline",
           label="Open Attend — AI Model Stack",
           labelloc="t", fontsize="20", fontcolor="#0f172a")
    g.node_attr.update(**COMMON_NODE)
    g.edge_attr.update(**COMMON_EDGE)

    # Inputs
    _io_node(g, "audio", "Audio Input\n16kHz PCM")
    _io_node(g, "images", "Image Upload\nX-ray, skin, labs")

    # --- MedGemma hero section ---
    with g.subgraph(name="cluster_medgemma") as c:
        c.attr(label="MedGemma Model Family (Google Health AI)",
               style="rounded,filled,bold",
               fillcolor=MEDGEMMA_BG_LIGHT, color=MEDGEMMA_BORDER,
               fontcolor="#0f766e", fontsize="14", penwidth="3.0",
               margin="20")
        _medgemma_node(c, "mg27",
                       "MedGemma 27B text-it\n━━━━━━━━━━━━━━━━━━━━━\n"
                       "Orchestrator  •  SOAP Notes\n"
                       "Medications  •  Alerts  •  Differential\n"
                       "ICD-10/CPT  •  Patient Summary",
                       width="3.5", height="1.4", fontsize="12")
        _medgemma_node(c, "mg4",
                       "MedGemma 4B-IT (Vision)\n━━━━━━━━━━━━━━━━━━━━━\n"
                       "X-ray  •  Skin lesions  •  Lab reports\n"
                       "Document understanding",
                       width="3.0", height="1.1", fontsize="11")

    # --- Supporting models (muted) ---
    with g.subgraph(name="cluster_asr_support") as c:
        c.attr(label="Speech-to-Text", style="rounded,filled",
               fillcolor="#f8fafc", color="#d1d5db",
               fontcolor="#9ca3af", fontsize="10")
        _support_node(c, "medasr_m", "MedASR 105M\nCTC • medical vocab")
        _support_node(c, "whisper_m", "Whisper base\ngeneral conversational")
        c.node("merge_m", "Entity-Guided Merge",
               shape="box", style="filled,rounded",
               fillcolor="#ccfbf1", color="#14b8a6", fontcolor="#0f766e",
               fontsize="9", penwidth="1.2")

    with g.subgraph(name="cluster_support_other") as c:
        c.attr(label="Supporting Models", style="rounded,filled",
               fillcolor="#f8fafc", color="#d1d5db",
               fontcolor="#9ca3af", fontsize="10")
        _support_node(c, "pyannote_m", "Pyannote 3.1\nspeaker diarization")
        _support_node(c, "siglip_m", "MedSigLIP + FAISS\nsimilar-case retrieval")
        _support_node(c, "hear_m", "HeAR 512-dim\nhealth audio embeddings")

    # --- Classifier registry ---
    with g.subgraph(name="cluster_clf") as c:
        c.attr(label="Classifier Registry (drop-in)",
               style="rounded,filled,dashed",
               fillcolor="#fff7ed", color="#f97316",
               fontcolor="#c2410c", fontsize="10")
        c.node("img_clf", "Image Classifiers\nTorchXRayVision DenseNet121\n14 pathologies + custom",
               shape="box", style="filled,rounded",
               fillcolor="#fff7ed", color="#f97316", fontcolor="#c2410c",
               fontsize="9", penwidth="1.2")
        c.node("aud_clf", "Audio Classifiers\nRespiratory CNN\nCough Detector + custom",
               shape="box", style="filled,rounded",
               fillcolor="#fff7ed", color="#f97316", fontcolor="#c2410c",
               fontsize="9", penwidth="1.2")

    # --- Edges ---
    g.edge("audio", "medasr_m", color="#94a3b8")
    g.edge("audio", "whisper_m", color="#94a3b8")
    g.edge("audio", "pyannote_m", color="#94a3b8", style="dashed")
    g.edge("audio", "hear_m", color="#94a3b8", style="dashed")

    g.edge("medasr_m", "merge_m", color="#14b8a6")
    g.edge("whisper_m", "merge_m", color="#14b8a6")

    # Key flow: transcript → MedGemma 27B (bold)
    g.edge("merge_m", "mg27", label="transcript",
           color=MEDGEMMA_BG, penwidth="3.0", style="bold")
    g.edge("pyannote_m", "mg27", color="#94a3b8", style="dashed",
           label="speaker labels")

    g.edge("images", "mg4", color=MEDGEMMA_BG, penwidth="2.5", style="bold")
    g.edge("images", "siglip_m", color="#94a3b8", style="dashed")

    g.edge("mg4", "img_clf", color="#f97316", style="dashed")
    g.edge("hear_m", "aud_clf", color="#f97316", style="dashed")

    g.edge("img_clf", "mg27", label="structured\npredictions",
           color="#f97316", penwidth="1.8", style="bold")
    g.edge("aud_clf", "mg27", label="structured\npredictions",
           color="#f97316", penwidth="1.8", style="bold")
    g.edge("siglip_m", "mg27", label="similar cases",
           color="#94a3b8", style="dashed")

    g.render(str(OUT_DIR / "model_stack"), cleanup=True)


# ---------------------------------------------------------------------------
# Diagram 4: Deployment Tiers
# ---------------------------------------------------------------------------
def diagram_deployment_tiers():
    g = graphviz.Digraph("deployment_tiers", format="png", engine="dot")
    g.attr(**COMMON_GRAPH, rankdir="TB", nodesep="0.8", ranksep="0.8",
           splines="spline",
           label="Open Attend — Deployment Tiers",
           labelloc="t", fontsize="20", fontcolor="#0f172a")
    g.node_attr.update(**COMMON_NODE)
    g.edge_attr.update(**COMMON_EDGE)

    tiers = [
        {
            "name": "cluster_t1",
            "label": "Tier 1: Laptop  —  $0/month\nRural clinic / dev / solo practitioner",
            "bg": "#f0f9ff", "border": "#93c5fd", "fc": "#1e40af",
            "nodes": [
                ("t1_hw", "Apple M1+ 16GB\nNo GPU required", False),
                ("t1_llm", "MedGemma 4B-IT\nOllama (CPU/Metal)", True),
                ("t1_asr", "Whisper + MedASR\nPyannote (CPU)", False),
            ],
            "edge_color": "#3b82f6",
        },
        {
            "name": "cluster_t2",
            "label": "Tier 2: Small Clinic  —  ~$780/mo\n5–20 physicians  •  A100 80GB / A6000 48GB",
            "bg": "#f0fdf4", "border": "#86efac", "fc": "#166534",
            "nodes": [
                ("t2_hw", "A100 80GB\nor A6000 48GB", False),
                ("t2_llm", "MedGemma 27B\nvLLM (GPU)", True),
                ("t2_asr", "Whisper + MedASR\nPyannote (GPU)", False),
                ("t2_vis", "MedGemma 4B-IT\nSigLIP + HeAR", True),
            ],
            "edge_color": "#22c55e",
        },
        {
            "name": "cluster_t3",
            "label": "Tier 3: Hospital  —  ~$200/physician/mo\n50+ physicians  •  Google Cloud (BAA)",
            "bg": "#fdf4ff", "border": "#d8b4fe", "fc": "#7e22ce",
            "nodes": [
                ("t3_hw", "Google Cloud\nBAA signed", False),
                ("t3_llm", "MedGemma 27B\nVertex AI endpoint", True),
                ("t3_aux", "MedGemma 4B-IT +\nauxiliary models\nGKE autoscaled", True),
            ],
            "edge_color": "#a855f7",
        },
    ]

    for tier in tiers:
        with g.subgraph(name=tier["name"]) as c:
            c.attr(label=tier["label"], style="rounded,filled",
                   fillcolor=tier["bg"], color=tier["border"],
                   fontcolor=tier["fc"], fontsize="12", penwidth="2.0")
            prev = None
            for nid, nlabel, is_medgemma in tier["nodes"]:
                if is_medgemma:
                    _medgemma_node(c, nid, nlabel, width="2.0", height="0.7")
                else:
                    _support_node(c, nid, nlabel)
                if prev:
                    g.edge(prev, nid, color=tier["edge_color"],
                           style="dashed", arrowsize="0.6")
                prev = nid

    g.render(str(OUT_DIR / "deployment_tiers"), cleanup=True)


# ---------------------------------------------------------------------------
# Diagram 5: User Flow (Landing → Dashboard → ... → Post-Visit)
# ---------------------------------------------------------------------------
def diagram_user_flow():
    g = graphviz.Digraph("user_flow", format="png", engine="dot")
    g.attr(**COMMON_GRAPH, rankdir="LR", nodesep="1.0", ranksep="1.5",
           splines="spline",
           label="Open Attend — User Flow",
           labelloc="t", fontsize="20", fontcolor="#0f172a")
    g.node_attr.update(**COMMON_NODE)
    g.edge_attr.update(**COMMON_EDGE)

    # Pages
    pages = [
        ("landing", "Landing Page", "Disclaimer acceptance\nMedical AI notice", False),
        ("dashboard", "Dashboard", "Session list + search\nDate filter + new visit", False),
        ("setup", "Visit Setup", "Patient context\nSpecialty + chief complaint", False),
        ("inroom", "In-Room View", "Live SOAP + transcript\nAlerts + medications\nDifferential + orders", True),
        ("postvisit", "Post-Visit Review", "Edit SOAP sections\nICD-10 / CPT codes\nPatient summary + export", False),
    ]

    for pid, label, desc, active in pages:
        _flow_node(g, pid, label, desc, active)

    # Main flow arrows
    g.edge("landing", "dashboard",
           label="Accept\ndisclaimer", color=FLOW_ACTIVE,
           penwidth="2.5", style="bold")
    g.edge("dashboard", "setup",
           label="New Visit", color=FLOW_ACTIVE,
           penwidth="2.5", style="bold")
    g.edge("setup", "inroom",
           label="Start\nRecording", color=FLOW_ACTIVE,
           penwidth="2.5", style="bold")
    g.edge("inroom", "postvisit",
           label="End Visit", color=FLOW_ACTIVE,
           penwidth="2.5", style="bold")

    # Return arrows
    g.edge("postvisit", "dashboard",
           label="Back to\nDashboard", color="#94a3b8",
           style="dashed", penwidth="1.2",
           constraint="false")
    g.edge("dashboard", "postvisit",
           label="Review past\nsession", color="#94a3b8",
           style="dashed", penwidth="1.2",
           constraint="false")

    # Side annotations — what happens at each stage
    annotations = [
        ("landing_note", "landing", "Cookie-based\npersistence"),
        ("inroom_note", "inroom", "Real-time WebSocket\n15s audio batches\nMedGemma 27B orchestrator"),
        ("postvisit_note", "postvisit", "Editable SOAP\nPDF/text export"),
    ]

    for aid, parent, label in annotations:
        g.node(aid, label,
               shape="note", style="filled",
               fillcolor="#fefce8", color="#facc15",
               fontcolor="#854d0e", fontsize="8",
               penwidth="1.0", width="1.5")
        g.edge(parent, aid, style="dotted", color="#d4d4d8",
               arrowhead="none", constraint="false")

    # Settings accessible from dashboard
    g.node("settings", "Settings",
           shape="box", style="filled,rounded",
           fillcolor="#f1f5f9", color="#94a3b8",
           fontcolor="#475569", fontsize="10",
           width="1.2")
    g.edge("dashboard", "settings",
           label="Gear icon", color="#94a3b8",
           style="dashed", penwidth="1.0",
           constraint="false")

    g.render(str(OUT_DIR / "user_flow"), cleanup=True)


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Generating diagrams to docs/diagrams/ ...")
    diagram_system_overview()
    print("  1/5  system_overview.png")
    diagram_orchestrator_flow()
    print("  2/5  orchestrator_flow.png")
    diagram_model_stack()
    print("  3/5  model_stack.png")
    diagram_deployment_tiers()
    print("  4/5  deployment_tiers.png")
    diagram_user_flow()
    print("  5/5  user_flow.png")
    print("Done.")

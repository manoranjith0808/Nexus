"""Sentinel Swarm — Compliance Decision Platform.

3 views:
  1. Alert Queue  → prioritized list, filters, click to investigate
  2. Case View    → full investigation: summary, graph, evidence, DECIDE
  3. Metrics      → KPIs for managers

streamlit run dashboard.py
"""

import json
import random
import streamlit as st
import streamlit.components.v1 as components
import httpx
import plotly.graph_objects as go

st.set_page_config(page_title="Sentinel Swarm", page_icon="⬡", layout="wide", initial_sidebar_state="collapsed")

API = "http://localhost:3000"

# ═══════════════════════════════════════════════
# THEME
# ═══════════════════════════════════════════════

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
:root{--bg0:#050507;--bg1:#0a0a0c;--bg2:#111114;--bg3:#18181b;--bg4:#1f1f23;--bd:#222228;--bd2:#2e2e35;--t0:#fafafa;--t1:#d4d4d8;--t2:#a1a1aa;--t3:#71717a;--t4:#52525b;--accent:#635bff;--green:#10b981;--yellow:#f59e0b;--orange:#f97316;--red:#ef4444;--blue:#3b82f6;--purple:#8b5cf6;--r:10px;}
*,html,body,[class*="css"]{font-family:'Inter',-apple-system,sans-serif!important;}
.stApp{background:var(--bg0)!important;}
.stApp>header{display:none!important;}
.block-container{padding:0!important;max-width:100%!important;}
section[data-testid="stSidebar"]{display:none!important;}

/* Metrics */
div[data-testid="stMetric"]{background:var(--bg2);border:1px solid var(--bd);border-radius:var(--r);padding:16px 18px;box-shadow:0 1px 2px rgba(0,0,0,.4);}
div[data-testid="stMetric"] label{color:var(--t3)!important;font-size:.65rem!important;font-weight:600!important;letter-spacing:.05em!important;text-transform:uppercase!important;}
div[data-testid="stMetric"] [data-testid="stMetricValue"]{color:var(--t0)!important;font-size:1.4rem!important;font-weight:700!important;font-feature-settings:'tnum'!important;}

/* Buttons */
.stButton>button{background:var(--bg3)!important;color:var(--t1)!important;border:1px solid var(--bd)!important;border-radius:8px!important;font-weight:600!important;font-size:.78rem!important;padding:7px 16px!important;transition:all .12s!important;}
.stButton>button:hover{background:var(--bg4)!important;border-color:var(--bd2)!important;}

/* Tabs */
.stTabs [data-baseweb="tab-list"]{gap:0!important;background:var(--bg2)!important;border-radius:var(--r)!important;padding:3px!important;border:1px solid var(--bd)!important;}
.stTabs [data-baseweb="tab"]{background:transparent!important;color:var(--t3)!important;border-radius:7px!important;padding:7px 14px!important;font-weight:500!important;font-size:.78rem!important;border:none!important;}
.stTabs [aria-selected="true"]{background:var(--bg4)!important;color:var(--t0)!important;}
.stTabs [data-baseweb="tab-panel"]{padding-top:1rem!important;}

/* Inputs */
.stTextInput input,.stNumberInput input,.stSelectbox>div>div,textarea{background:var(--bg2)!important;border:1px solid var(--bd)!important;color:var(--t0)!important;border-radius:8px!important;font-size:.82rem!important;}
.stTextInput input:focus,textarea:focus{border-color:var(--accent)!important;box-shadow:0 0 0 3px rgba(99,91,255,.1)!important;}
div[data-baseweb="select"]>div{background:var(--bg2)!important;border-color:var(--bd)!important;}
div[data-baseweb="select"] span{color:var(--t0)!important;}

/* Expander */
details{background:var(--bg2)!important;border:1px solid var(--bd)!important;border-radius:var(--r)!important;}
details summary{color:var(--t1)!important;font-weight:500!important;}

/* Slider */
.stSlider label,.stSlider div{color:var(--t3)!important;}

hr{border-color:var(--bd)!important;opacity:.5;}
pre{background:var(--bg1)!important;border:1px solid var(--bd)!important;border-radius:8px!important;font-family:'JetBrains Mono'!important;font-size:.75rem!important;}
[data-testid="stStatusWidget"]{background:var(--bg2)!important;border:1px solid var(--bd)!important;border-radius:var(--r)!important;}
.stAlert{border-radius:8px!important;font-size:.82rem!important;}
.stCheckbox label span{color:var(--t2)!important;font-size:.8rem!important;}
</style>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════

def api(method, path, **kw):
    try:
        with httpx.Client(base_url=API, timeout=90) as c:
            r = getattr(c, method)(path, **kw)
            return r.json() if r.status_code < 400 else None
    except Exception:
        return None

def rc(s):
    if s >= .85: return "#ef4444"
    if s >= .65: return "#f97316"
    if s >= .40: return "#f59e0b"
    return "#10b981"

def verdict_color(v):
    return {"BLOCK":"#ef4444","ESCALATE":"#f97316","MONITOR":"#f59e0b"}.get(v,"#10b981")

def severity_label(s):
    if s >= .85: return "CRITICAL"
    if s >= .65: return "HIGH"
    if s >= .40: return "MEDIUM"
    return "LOW"

def badge_html(text, color):
    return f'<span style="display:inline-flex;align-items:center;padding:2px 8px;border-radius:9999px;font-size:.65rem;font-weight:600;letter-spacing:.02em;background:{color}14;color:{color};border:1px solid {color}30;">{text}</span>'

def money(amt):
    if amt is None: return "—"
    return f"${amt:,.0f}"


# ═══════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════

if "view" not in st.session_state:
    st.session_state.view = "queue"
if "selected_case" not in st.session_state:
    st.session_state.selected_case = None

# ═══════════════════════════════════════════════
# TOP NAV BAR
# ═══════════════════════════════════════════════

queue_stats = api("get", "/api/alerts/queue/stats") or {}
pending_count = queue_stats.get("pending", 0)
critical_count = queue_stats.get("critical_count", 0)

# Route based on query params
params = st.query_params
if "view" in params:
    st.session_state.view = params["view"]
if "case" in params:
    st.session_state.view = "case"
    st.session_state.selected_case = params["case"]

view = st.session_state.view

# Build navbar HTML safely (avoid nested f-strings)
q_active = "background:#1f1f23;color:#fafafa;" if view == "queue" else "color:#71717a;"
m_active = "background:#1f1f23;color:#fafafa;" if view == "metrics" else "color:#71717a;"
pending_badge = f' <span style="background:#ef444420;color:#ef4444;padding:1px 6px;border-radius:9999px;font-size:.65rem;font-weight:700;margin-left:4px;">{pending_count}</span>' if pending_count else ""
crit_badge = badge_html(f"{critical_count} critical", "#ef4444") if critical_count else ""

navbar = (
    '<div style="display:flex;align-items:center;justify-content:space-between;padding:10px 24px;background:#0a0a0c;border-bottom:1px solid #222228;">'
    '<div style="display:flex;align-items:center;gap:20px;">'
    '<div style="display:flex;align-items:center;gap:8px;">'
    '<div style="width:26px;height:26px;background:linear-gradient(135deg,#635bff,#8b5cf6);border-radius:6px;"></div>'
    '<span style="color:#fafafa;font-weight:700;font-size:.88rem;">Sentinel Swarm</span>'
    '</div>'
    '<div style="display:flex;gap:2px;">'
    f'<a href="?view=queue" style="text-decoration:none;padding:5px 12px;border-radius:6px;font-size:.78rem;font-weight:500;{q_active}">Alertas{pending_badge}</a>'
    f'<a href="?view=metrics" style="text-decoration:none;padding:5px 12px;border-radius:6px;font-size:.78rem;font-weight:500;{m_active}">Metricas</a>'
    '</div></div>'
    f'<div style="display:flex;align-items:center;gap:10px;">{crit_badge}</div>'
    '</div>'
)
st.markdown(navbar, unsafe_allow_html=True)


# ═══════════════════════════════════════════════
# VIEW: ALERT QUEUE
# ═══════════════════════════════════════════════

if view == "queue":
    # Content area with padding
    st.markdown('<div style="padding:20px 24px;">', unsafe_allow_html=True)

    # Stats bar
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pendientes", pending_count)
    c2.metric("En revisión", queue_stats.get("reviewing", 0))
    c3.metric("Críticos", critical_count)
    c4.metric("Score promedio", f"{queue_stats.get('avg_score', 0):.2f}")

    st.markdown("---")

    # Filters
    fc = st.columns([1, 1, 1, 1, 2])
    f_sort = fc[0].selectbox("Ordenar", ["score", "amount", "created_at"], label_visibility="collapsed")
    f_min = fc[1].number_input("Score mín", value=0.0, step=0.1, min_value=0.0, max_value=1.0, label_visibility="collapsed")
    f_country = fc[2].selectbox("País", ["Todos", "UY", "AR"], label_visibility="collapsed")
    f_limit = fc[3].selectbox("Mostrar", [25, 50, 100], index=1, label_visibility="collapsed")

    # Fetch alerts
    alert_params = {"sort_by": f_sort, "min_score": f_min, "limit": f_limit, "status": "ALL"}
    if f_country != "Todos":
        alert_params["country"] = f_country

    data = api("get", "/api/alerts/queue", params=alert_params)
    if not data or not data.get("alerts"):
        st.info("No hay alertas activas.")
        st.stop()

    st.markdown(f'<div style="color:var(--t3);font-size:.75rem;margin-bottom:12px;">{data["total"]} alertas</div>', unsafe_allow_html=True)

    # Table header
    st.markdown("""<div style="display:grid;grid-template-columns:2fr 1fr 1fr 1fr 1fr 1fr;padding:8px 16px;font-size:.65rem;font-weight:600;color:var(--t4);letter-spacing:.04em;text-transform:uppercase;border-bottom:1px solid var(--bd);">
    <div>Caso</div><div>Veredicto</div><div>Score</div><div>Patrón</div><div>Monto</div><div>País</div></div>""", unsafe_allow_html=True)

    # Alert rows
    for a in data["alerts"]:
        sc = a["score"]
        v = a["verdict"]
        sev = severity_label(sc)
        vc = verdict_color(v)
        sev_c = rc(sc)
        status = a.get("alert_status", "PENDING")
        status_dot = {"PENDING": "#f59e0b", "REVIEWING": "#3b82f6", "APPROVED": "#10b981", "REJECTED": "#52525b", "ESCALATED": "#f97316"}

        pattern_display = a["pattern"] if a["pattern"] != "—" else ""
        name_display = a.get("user_name") or "—"
        if name_display == "—" or name_display is None:
            name_display = a["account_id"]

        st.markdown(f"""
        <a href="?view=case&case={a['case_id']}" style="text-decoration:none;display:grid;grid-template-columns:2fr 1fr 1fr 1fr 1fr 1fr;padding:12px 16px;border-bottom:1px solid var(--bd);transition:background .1s;cursor:pointer;align-items:center;" onmouseover="this.style.background='var(--bg2)'" onmouseout="this.style.background='transparent'">
            <div>
                <div style="display:flex;align-items:center;gap:8px;">
                    <div style="width:6px;height:6px;border-radius:50%;background:{status_dot.get(status,'#52525b')};flex-shrink:0;"></div>
                    <div>
                        <div style="color:var(--t1);font-weight:500;font-size:.82rem;">{name_display}</div>
                        <div style="color:var(--t4);font-size:.68rem;font-family:'JetBrains Mono';">{a['case_id']}</div>
                    </div>
                </div>
            </div>
            <div>{badge_html(v, vc)}</div>
            <div>
                <span style="color:{sev_c};font-weight:700;font-size:.85rem;font-family:'JetBrains Mono';font-feature-settings:'tnum';">{sc:.2f}</span>
                <span style="color:var(--t4);font-size:.6rem;margin-left:4px;">{sev}</span>
            </div>
            <div style="color:var(--t2);font-size:.78rem;">{pattern_display}</div>
            <div style="color:var(--t1);font-size:.82rem;font-family:'JetBrains Mono';font-feature-settings:'tnum';">{money(a.get('amount'))}</div>
            <div style="color:var(--t2);font-size:.78rem;">{'🇺🇾' if a.get('country')=='UY' else '🇦🇷' if a.get('country')=='AR' else ''} {a.get('country','')}</div>
        </a>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════
# VIEW: CASE DETAIL
# ═══════════════════════════════════════════════

elif view == "case":
    case_id = st.session_state.selected_case
    if not case_id:
        st.warning("No case selected."); st.stop()

    a = api("get", f"/api/alerts/{case_id}")
    if not a:
        st.error(f"Case {case_id} not found."); st.stop()

    # Fetch narrative + ROS
    narrative = api("get", f"/api/reports/{case_id}/narrative") or {}
    ros = api("get", f"/api/reports/{case_id}/ros") or {}

    sc = a["score"]
    v = a["verdict"]
    vc = verdict_color(v)
    sev = severity_label(sc)

    # ── Header ──
    st.markdown(f"""<div style="padding:16px 24px 0;">
    <a href="?view=queue" style="color:var(--t3);text-decoration:none;font-size:.78rem;font-weight:500;">← Alertas</a>
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-top:10px;">
    <div>
        <div style="display:flex;align-items:center;gap:8px;">
            <span style="color:var(--t0);font-size:1.25rem;font-weight:700;letter-spacing:-.01em;">{a.get('user_name') or a['account_id']}</span>
            {badge_html(v, vc)} {badge_html(sev, rc(sc))}
        </div>
        <div style="color:var(--t4);font-size:.72rem;font-family:'JetBrains Mono';margin-top:3px;">{case_id} · {a.get('account_id','')} · {'🇺🇾' if a.get('country')=='UY' else '🇦🇷'} {a.get('country','')}</div>
    </div>
    <div style="text-align:right;">
        <div style="color:{rc(sc)};font-size:1.8rem;font-weight:800;font-feature-settings:'tnum';line-height:1;">{sc:.4f}</div>
        <div style="color:var(--t4);font-size:.65rem;">confidence score</div>
    </div></div></div>""", unsafe_allow_html=True)

    st.markdown('<div style="padding:0 24px;">', unsafe_allow_html=True)

    # ── Narrative summary (the WHAT HAPPENED — top of case view) ──
    summary = narrative.get("summary", "")
    recommendation = narrative.get("recommendation", "")
    if summary:
        st.markdown(f"""<div style="background:var(--bg2);border:1px solid var(--bd);border-radius:10px;padding:16px 20px;margin:16px 0;">
        <div style="color:var(--t2);font-size:.65rem;font-weight:600;letter-spacing:.05em;text-transform:uppercase;margin-bottom:6px;">Resumen del caso</div>
        <div style="color:var(--t1);font-size:.88rem;line-height:1.55;">{summary}</div>
        <div style="color:var(--t0);font-size:.82rem;line-height:1.5;margin-top:10px;padding-top:10px;border-top:1px solid var(--bd);">{recommendation}</div>
        </div>""", unsafe_allow_html=True)

    # ── Metrics row ──
    mc = st.columns(5)
    mc[0].metric("Monto", money(a.get("amount")))
    mc[1].metric("Tipo", a.get("event_type", "—"))
    mc[2].metric("IP", a.get("ip_address", "—"))
    mc[3].metric("Device", (a.get("device_id") or "—")[:16])
    mc[4].metric("Latencia", f"{a.get('latency_ms',0)}ms")

    st.markdown("---")

    # ── Tabs: Evidence | Graph | Reasoning | Report | Audit ──
    tabs = st.tabs(["Señales de riesgo", "Red de relaciones", "Razonamiento IA", "Reporte ROS", "Audit log"])

    # TAB 1: Risk signals + agent scores
    with tabs[0]:
        col_signals, col_agents = st.columns([1, 1])

        with col_signals:
            rules = narrative.get("rules_triggered", [])
            if rules:
                for r in rules:
                    sev_c = {"CRITICAL":"#ef4444","HIGH":"#f97316","MEDIUM":"#f59e0b"}.get(r.get("severity"), "#52525b")
                    st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:var(--bg2);border:1px solid var(--bd);border-radius:8px;margin-bottom:6px;border-left:3px solid {sev_c};">
                    <div style="flex:1;">
                        <div style="display:flex;justify-content:space-between;"><span style="color:var(--t2);font-size:.68rem;font-weight:600;">{r['rule']}</span>
                        {badge_html(r.get('severity',''), sev_c)}</div>
                        <div style="color:var(--t0);font-size:.82rem;margin-top:2px;">{r['desc']}</div>
                    </div></div>""", unsafe_allow_html=True)
            else:
                st.info("Sin reglas activadas.")

        with col_agents:
            sentinel = a.get("sentinel") or {}
            osint = a.get("osint") or {}
            patterns = a.get("patterns") or {}
            historian = a.get("historian") or {}
            jurist = a.get("jurist") or {}

            agent_list = [
                ("Centinela", sentinel.get("risk_score", 0), "Topología"),
                ("OSINT", osint.get("risk_score", 0), "Identidad"),
                ("Patrones", patterns.get("risk_score", 0), "Clasificación"),
                ("Historiador", historian.get("risk_score", 0), "Precedentes"),
                ("Jurista", jurist.get("confidence_score", 0), "Legal"),
            ]
            for name, score, desc in agent_list:
                c = rc(score)
                pct = int(score * 100)
                st.markdown(f"""<div style="padding:6px 0;">
                <div style="display:flex;justify-content:space-between;align-items:baseline;">
                    <div><span style="color:var(--t1);font-size:.78rem;font-weight:500;">{name}</span>
                    <span style="color:var(--t4);font-size:.65rem;margin-left:4px;">{desc}</span></div>
                    <span style="color:{c};font-weight:700;font-size:.8rem;font-family:'JetBrains Mono';font-feature-settings:'tnum';">{score:.4f}</span>
                </div>
                <div style="height:4px;border-radius:2px;background:var(--bg4);margin-top:3px;overflow:hidden;">
                    <div style="height:100%;width:{pct}%;background:{c};border-radius:2px;"></div>
                </div></div>""", unsafe_allow_html=True)

    # TAB 2: Graph
    with tabs[1]:
        tid = a.get("tenant_id")
        acc_id = a.get("account_id", "")
        if tid and acc_id:
            gdata = api("get", f"/api/graph/{tid}/subgraph/{acc_id}", params={"hops": 2})
            if gdata and gdata.get("nodes"):
                _render_case_graph(gdata, a)
            else:
                st.info(f"Sin datos de grafo para {acc_id}")
        else:
            st.info("Sin tenant asignado.")

    # TAB 3: AI Reasoning (explainability)
    with tabs[2]:
        why = narrative.get("why_suspicious", [])
        if why:
            st.markdown('<div style="color:var(--t2);font-size:.65rem;font-weight:600;letter-spacing:.05em;text-transform:uppercase;margin-bottom:10px;">¿Por qué es sospechoso?</div>', unsafe_allow_html=True)
            for i, line in enumerate(why, 1):
                st.markdown(f"""<div style="display:flex;gap:12px;padding:10px 0;border-bottom:1px solid var(--bd);">
                <div style="width:22px;height:22px;border-radius:50%;background:var(--bg3);border:1px solid var(--bd);display:flex;align-items:center;justify-content:center;font-size:.7rem;color:var(--t3);flex-shrink:0;">{i}</div>
                <div style="color:var(--t1);font-size:.82rem;line-height:1.5;">{line}</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.info("Sin explicación disponible.")

        # Score breakdown
        breakdown = jurist.get("score_breakdown") or []
        if breakdown:
            st.markdown("---")
            st.markdown('<div style="color:var(--t2);font-size:.65rem;font-weight:600;letter-spacing:.05em;text-transform:uppercase;margin-bottom:8px;">Desglose del score</div>', unsafe_allow_html=True)
            for sb in breakdown:
                st.markdown(f"""<div style="display:flex;justify-content:space-between;padding:4px 0;font-size:.8rem;">
                <span style="color:var(--t2);">{sb['agent']}</span>
                <span class="mono" style="color:var(--t1);">{sb['raw_score']:.4f} × {sb['weight']} = <b style="color:var(--t0);">{sb['weighted_score']:.4f}</b></span>
                </div>""", unsafe_allow_html=True)

    # TAB 4: ROS Report
    with tabs[3]:
        if ros:
            st.markdown(f"""<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <div>
                <div style="color:var(--t0);font-weight:600;font-size:.9rem;">{ros.get('report_type','Reporte')}</div>
                <div style="color:var(--t4);font-size:.72rem;">{ros.get('report_id','')} · {ros.get('regulator','')}</div>
            </div>
            <a href="{API}/api/reports/{case_id}/ros/html" target="_blank" style="text-decoration:none;background:var(--accent);color:white;padding:6px 14px;border-radius:6px;font-size:.78rem;font-weight:600;">Abrir para imprimir / PDF</a>
            </div>""", unsafe_allow_html=True)

            sub = ros.get("subject", {})
            op = ros.get("operation", {})

            st.markdown(f"""<div style="background:var(--bg2);border:1px solid var(--bd);border-radius:10px;padding:16px;">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
            <div>
                <div style="color:var(--t3);font-size:.65rem;font-weight:600;letter-spacing:.04em;text-transform:uppercase;margin-bottom:6px;">Sujeto reportado</div>
                <div style="color:var(--t1);font-size:.82rem;line-height:1.6;">
                    <b>{sub.get('name','—')}</b><br>
                    Cuenta: <span class="mono">{sub.get('account','—')}</span><br>
                    {sub.get('document_type','')}: {sub.get('document','—')}<br>
                    País: {sub.get('country','')}
                </div>
            </div>
            <div>
                <div style="color:var(--t3);font-size:.65rem;font-weight:600;letter-spacing:.04em;text-transform:uppercase;margin-bottom:6px;">Operación</div>
                <div style="color:var(--t1);font-size:.82rem;line-height:1.6;">
                    Tipo: {op.get('type','—')}<br>
                    Monto: <b>{op.get('currency','')} {op.get('amount',0):,.2f}</b><br>
                    Destino: <span class="mono">{op.get('destination_account','—')}</span> ({op.get('destination_country','')})<br>
                    Canal: {op.get('channel','—')}
                </div>
            </div></div></div>""", unsafe_allow_html=True)

            # Grounds
            grounds = ros.get("suspicion_grounds", [])
            if grounds:
                st.markdown('<div style="margin-top:12px;color:var(--t3);font-size:.65rem;font-weight:600;letter-spacing:.04em;text-transform:uppercase;">Fundamentos de la sospecha</div>', unsafe_allow_html=True)
                for g in grounds:
                    st.markdown(f'<div style="color:var(--t1);font-size:.82rem;padding:4px 0;border-bottom:1px solid var(--bd);">• {g}</div>', unsafe_allow_html=True)

    # TAB 5: Audit log
    with tabs[4]:
        audit = a.get("audit_log") or []
        if audit:
            for entry in reversed(audit):
                action_c = {"APPROVE":"#10b981","REJECT":"#ef4444","ESCALATE":"#f97316","ASSIGN":"#3b82f6"}.get(entry.get("action",""),"#52525b")
                st.markdown(f"""<div style="display:flex;gap:12px;padding:12px 0;border-bottom:1px solid var(--bd);">
                <div style="width:8px;height:8px;border-radius:50%;background:{action_c};margin-top:5px;flex-shrink:0;"></div>
                <div>
                    <div style="display:flex;gap:6px;align-items:center;">
                        {badge_html(entry.get('action',''), action_c)}
                        <span style="color:var(--t3);font-size:.72rem;">{entry.get('analyst_id','system')}</span>
                    </div>
                    <div style="color:var(--t2);font-size:.78rem;margin-top:2px;">{entry.get('reason','')}</div>
                    <div style="color:var(--t4);font-size:.68rem;font-family:'JetBrains Mono';margin-top:2px;">{entry.get('timestamp','')}</div>
                </div></div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:var(--t4);font-size:.82rem;padding:20px 0;text-align:center;">Sin actividad registrada</div>', unsafe_allow_html=True)

    # ── DECISION PANEL (always visible at bottom) ──
    st.markdown("---")

    current_status = a.get("alert_status", "PENDING")
    if current_status in ("APPROVED", "REJECTED", "ESCALATED"):
        dec = a.get("decision", {})
        dec_c = '#10b981' if current_status=='APPROVED' else '#ef4444' if current_status=='REJECTED' else '#f97316'
        st.markdown(f"""<div style="background:var(--bg2);border:1px solid var(--bd);border-radius:10px;padding:18px 20px;">
        <div style="display:flex;align-items:center;gap:8px;">
            <span style="color:var(--t0);font-weight:600;font-size:.85rem;">Decisión registrada</span>
            {badge_html(current_status, dec_c)}
        </div>
        <div style="color:var(--t2);font-size:.78rem;margin-top:6px;">
            {dec.get('analyst_name','—')} · {dec.get('decided_at','—')[:19]}<br>
            {dec.get('reason','')}
        </div></div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div style="background:var(--bg2);border:1px solid var(--bd);border-radius:10px;padding:18px 20px;">
        <div style="color:var(--t0);font-weight:600;font-size:.85rem;margin-bottom:10px;">Tomar decisión</div>""", unsafe_allow_html=True)

        dc = st.columns([1, 2])
        with dc[0]:
            analyst_name = st.text_input("Nombre", value="Analista", label_visibility="collapsed", placeholder="Tu nombre")
        with dc[1]:
            reason = st.text_input("Razón", value="", label_visibility="collapsed", placeholder="Razón (opcional)")

        bc = st.columns(3)
        with bc[0]:
            if st.button("Confirmar fraude", use_container_width=True, key="approve"):
                api("post", f"/api/alerts/{case_id}/decide", json={"action": "APPROVE", "analyst_id": "analyst-1", "analyst_name": analyst_name, "reason": reason or "Fraude confirmado"})
                st.rerun()
        with bc[1]:
            if st.button("Falso positivo", use_container_width=True, key="reject"):
                api("post", f"/api/alerts/{case_id}/decide", json={"action": "REJECT", "analyst_id": "analyst-1", "analyst_name": analyst_name, "reason": reason or "Falso positivo"})
                st.rerun()
        with bc[2]:
            if st.button("Escalar", use_container_width=True, key="escalate"):
                api("post", f"/api/alerts/{case_id}/decide", json={"action": "ESCALATE", "analyst_id": "analyst-1", "analyst_name": analyst_name, "reason": reason or "Requiere revisión adicional"})
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    # Raw data
    with st.expander("Datos completos (JSON)"):
        st.json(a.get("raw", a))

    st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════
# VIEW: METRICS
# ═══════════════════════════════════════════════

elif view == "metrics":
    st.markdown('<div style="padding:20px 24px;">', unsafe_allow_html=True)

    stats = api("get", "/api/cases/stats/summary") or {}
    total = stats.get("total", 0)
    vd = stats.get("verdicts", {})

    st.markdown("### Métricas de rendimiento")
    st.markdown("---")

    mc = st.columns(6)
    mc[0].metric("Casos totales", f"{total:,}")
    mc[1].metric("Bloqueados", f"{vd.get('BLOCK', 0):,}")
    mc[2].metric("Escalados", f"{vd.get('ESCALATE', 0):,}")
    mc[3].metric("Monitoreados", f"{vd.get('MONITOR', 0):,}")
    mc[4].metric("Descartados", f"{vd.get('DISCARD', 0):,}")
    mc[5].metric("Latencia prom.", f"{stats.get('avg_latency_ms', 0):,}ms")

    st.markdown("---")

    cl, cr = st.columns(2)

    with cl:
        labels = [k for k in vd.keys() if vd[k] > 0]
        vals = [vd[k] for k in labels]
        cm = {"DISCARD": "#10b981", "MONITOR": "#f59e0b", "ESCALATE": "#f97316", "BLOCK": "#ef4444"}
        fig = go.Figure(go.Pie(labels=labels, values=vals, hole=.65,
            marker=dict(colors=[cm.get(l, "#52525b") for l in labels], line=dict(color="#050507", width=2)),
            textfont=dict(color="#fafafa", size=11), textinfo="label+value", textposition="outside"))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#71717a", family="Inter", size=11), margin=dict(l=0, r=0, t=30, b=0),
            height=320, showlegend=False, title=dict(text="Distribución de veredictos", font=dict(color="#d4d4d8", size=13)))
        st.plotly_chart(fig, use_container_width=True)

    with cr:
        # Pattern distribution
        qstats = queue_stats.get("by_pattern", {})
        if qstats:
            labels_p = list(qstats.keys())
            vals_p = list(qstats.values())
            fig2 = go.Figure(go.Bar(x=vals_p, y=labels_p, orientation="h",
                marker=dict(color="#635bff", line=dict(width=0)),
                texttemplate="%{x}", textposition="outside",
                textfont=dict(color="#a1a1aa", size=11)))
            fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#71717a", family="Inter", size=11), margin=dict(l=120, r=40, t=30, b=0),
                height=320, yaxis=dict(gridcolor="#1f1f23"), xaxis=dict(gridcolor="#1f1f23"),
                title=dict(text="Patrones detectados", font=dict(color="#d4d4d8", size=13)))
            st.plotly_chart(fig2, use_container_width=True)

    # Banks table
    st.markdown("---")
    st.markdown("### Bancos")
    tenants = api("get", "/api/tenants/") or []
    if tenants:
        st.markdown("""<div style="display:grid;grid-template-columns:2fr 1fr 1fr 1fr 1fr;padding:8px 16px;font-size:.65rem;font-weight:600;color:var(--t4);letter-spacing:.04em;text-transform:uppercase;border-bottom:1px solid var(--bd);">
        <div>Banco</div><div>País</div><div style="text-align:right;">Casos</div><div style="text-align:right;">Alertas</div><div style="text-align:right;">Bloqueados</div></div>""", unsafe_allow_html=True)

        for t in tenants:
            flag = "🇺🇾" if t["country"] == "UY" else "🇦🇷"
            st.markdown(f"""<div style="display:grid;grid-template-columns:2fr 1fr 1fr 1fr 1fr;padding:12px 16px;border-bottom:1px solid var(--bd);align-items:center;">
            <div style="color:var(--t1);font-weight:500;font-size:.82rem;">{t['name']}</div>
            <div style="color:var(--t2);font-size:.78rem;">{flag} {t['country']}</div>
            <div style="color:var(--t1);text-align:right;font-family:'JetBrains Mono';font-feature-settings:'tnum';font-size:.82rem;">{t.get('total_cases',0):,}</div>
            <div style="color:var(--t1);text-align:right;font-family:'JetBrains Mono';font-size:.82rem;">{t.get('total_alerts',0)}</div>
            <div style="color:{'var(--red)' if t.get('total_blocked',0)>0 else 'var(--t2)'};text-align:right;font-family:'JetBrains Mono';font-weight:600;font-size:.82rem;">{t.get('total_blocked',0)}</div></div>""", unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════
# GRAPH RENDERER (for case view)
# ═══════════════════════════════════════════════

def _render_case_graph(data, alert):
    """Render vis.js graph scoped to a case — smaller, focused."""
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    center_id = alert.get("account_id", "")

    type_cfg = {
        "Persona": {"color": "#8b5cf6", "shape": "dot", "size": 18},
        "Cuenta": {"color": "#3b82f6", "shape": "dot", "size": 22},
        "Dispositivo": {"color": "#f59e0b", "shape": "diamond", "size": 14},
        "IP": {"color": "#ef4444", "shape": "triangle", "size": 13},
        "Transaccion": {"color": "#10b981", "shape": "square", "size": 11},
        "Unknown": {"color": "#52525b", "shape": "dot", "size": 10},
    }
    risk_map = {"CRITICAL": "#dc2626", "HIGH": "#f97316", "MEDIUM": "#eab308"}

    vis_nodes = []
    for nd in nodes:
        cfg = type_cfg.get(nd["type"], type_cfg["Unknown"])
        rl = nd.get("risk_level")
        bc = risk_map.get(rl, cfg["color"])
        bw = 4 if rl == "CRITICAL" else 3 if rl in risk_map else 1.5
        sz = cfg["size"] + (8 if nd["id"] == center_id else 4 if rl in risk_map else 0)
        vis_nodes.append({
            "id": nd["id"], "label": nd["id"], "size": sz, "shape": cfg["shape"],
            "color": {"background": "#635bff" if nd["id"] == center_id else cfg["color"], "border": bc,
                       "highlight": {"background": cfg["color"], "border": "#fafafa"}},
            "borderWidth": bw, "font": {"color": "#a1a1aa", "size": 9, "face": "Inter"},
        })

    vis_edges = []
    for i, e in enumerate(edges):
        is_tx = "TRANSFIERE" in e["label"]
        amt = e.get("properties", {}).get("amount")
        lbl = f"${amt:,.0f}" if amt else ""
        vis_edges.append({
            "id": e["id"], "from": e["source"], "to": e["target"], "label": lbl,
            "color": {"color": "#28282e", "highlight": "#fafafa"},
            "width": 2 if is_tx else 1,
            "arrows": {"to": {"enabled": is_tx, "scaleFactor": .4}},
            "font": {"color": "#3f3f46", "size": 8, "face": "JetBrains Mono", "strokeWidth": 0},
            "smooth": {"type": "curvedCW", "roundness": .1},
        })

    nj = json.dumps(vis_nodes)
    ej = json.dumps(vis_edges)
    h = 450

    html = f"""<!DOCTYPE html><html><head>
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:transparent;overflow:hidden;}}
#g{{width:100%;height:{h}px;border:1px solid #222228;border-radius:12px;background:#0a0a0c;}}
#leg{{position:absolute;bottom:8px;left:8px;display:flex;gap:10px;background:#111114dd;border:1px solid #222228;border-radius:6px;padding:5px 10px;font:500 9px/1 Inter,sans-serif;z-index:10;}}
.li{{display:flex;align-items:center;gap:4px;color:#52525b;}}.ld{{width:6px;height:6px;border-radius:50%;}}
</style></head><body><div style="position:relative;"><div id="g"></div>
<div id="leg">
<div class="li"><div class="ld" style="background:#8b5cf6"></div>Persona</div>
<div class="li"><div class="ld" style="background:#3b82f6"></div>Cuenta</div>
<div class="li"><div class="ld" style="background:#f59e0b"></div>Device</div>
<div class="li"><div class="ld" style="background:#ef4444"></div>IP</div>
<div class="li"><div class="ld" style="background:#10b981"></div>Tx</div>
</div></div>
<script>
var net=new vis.Network(document.getElementById('g'),
{{nodes:new vis.DataSet({nj}),edges:new vis.DataSet({ej})}},
{{physics:{{enabled:true,barnesHut:{{gravitationalConstant:-2000,springLength:100,damping:.4}},stabilization:{{iterations:150}}}},
interaction:{{hover:true,dragNodes:true,zoomView:true,dragView:true}},
edges:{{smooth:{{type:'curvedCW',roundness:.1}}}},
nodes:{{shadow:{{enabled:true,color:'rgba(0,0,0,.3)',size:5}}}}
}});
net.on('stabilized',function(){{setTimeout(function(){{net.setOptions({{physics:{{enabled:false}}}});}},400);}});
</script></body></html>"""
    components.html(html, height=h + 10, scrolling=False)

from __future__ import annotations

import sqlite3
from datetime import timezone

import pandas as pd
import streamlit as st

from utils import database_path, format_duration, parse_iso, utc_now


st.set_page_config(page_title="Slack SLA Dashboard", layout="wide")

STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@500&family=Inter:wght@400;500;600&display=swap');
:root {
  --font-heading: "Source Serif 4", Georgia, serif;
  --font-body: "Inter", Arial, system-ui, sans-serif;
  --text: #1d1d1f;
  --muted: #615d59;
  --border: rgba(0,0,0,0.1);
  --blue: #0071e3;
  --success: #1aae39;
  --warning: #dd5b00;
  --danger: #d92d20;
  --card-shadow: rgba(0,0,0,0.04) 0px 4px 18px, rgba(0,0,0,0.027) 0px 2.025px 7.84688px, rgba(0,0,0,0.02) 0px 0.8px 2.925px, rgba(0,0,0,0.01) 0px 0.175px 1.04062px;
}
html, body, [class*="css"] { font-family: var(--font-body); color: var(--text); }
h1, h2, h3 { font-family: var(--font-heading); font-weight: 500; letter-spacing: normal; color: var(--text); }
.block-container { max-width: 1200px; padding-top: 32px; }
.metric-card {
  background: #ffffff;
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: var(--card-shadow);
  padding: 18px 20px;
  min-height: 118px;
}
.metric-label { color: var(--muted); font-size: 12px; font-weight: 500; letter-spacing: .12px; }
.metric-value { font-size: 28px; font-weight: 600; margin-top: 10px; color: var(--text); }
.metric-note { color: var(--muted); font-size: 13px; margin-top: 4px; }
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: 980px;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid transparent;
  white-space: nowrap;
}
.badge-open { background: #f2f9ff; color: #097fe8; }
.badge-acknowledged { background: #eefaf1; color: #137d2c; }
.badge-breached { background: #fff1f0; color: #d92d20; }
.badge-warning { background: #fff6e8; color: #b64a00; }
.badge-neutral { background: #f6f5f4; color: #615d59; border-color: var(--border); }
.sentiment-negative { color: #d92d20; font-weight: 600; }
.sentiment-positive { color: #1aae39; font-weight: 600; }
.sentiment-neutral { color: #b77900; font-weight: 600; }
div[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 8px; box-shadow: var(--card-shadow); }
button[kind="secondary"] { border-radius: 8px !important; }
</style>
"""
st.markdown(STYLE, unsafe_allow_html=True)


def load_cases() -> pd.DataFrame:
    try:
        conn = sqlite3.connect(database_path())
        df = pd.read_sql_query("SELECT * FROM sla_cases ORDER BY created_at DESC", conn)
        conn.close()
    except Exception:
        return pd.DataFrame()
    return df


def load_notifications() -> pd.DataFrame:
    try:
        conn = sqlite3.connect(database_path())
        df = pd.read_sql_query("SELECT * FROM notifications ORDER BY sent_at", conn)
        conn.close()
    except Exception:
        return pd.DataFrame()
    return df


def pct(value: float) -> str:
    return f"{value:.1%}"


def compliance_rate(df: pd.DataFrame) -> float:
    completed = df[df["status"].isin(["acknowledged", "breached"])]
    if completed.empty:
        return 0.0
    met = completed[completed["breached"] == 0]
    return len(met) / len(completed)


def seconds_to_label(value) -> str:
    if pd.isna(value):
        return "-"
    return format_duration(int(value))


def parse_time(value: str | None):
    parsed = parse_iso(value)
    if parsed and parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_near_due(row: pd.Series) -> bool:
    if row.get("status") != "open":
        return False
    due_at = parse_time(row.get("due_at"))
    if not due_at:
        return False
    seconds_left = (due_at - utc_now()).total_seconds()
    return 0 < seconds_left <= 15


def status_badge(row: pd.Series) -> str:
    if row.get("status") == "open" and is_near_due(row):
        return '<span class="badge badge-warning">Near due</span>'
    status = row.get("status", "open")
    classes = {
        "open": "badge-open",
        "acknowledged": "badge-acknowledged",
        "breached": "badge-breached",
    }
    return f'<span class="badge {classes.get(status, "badge-neutral")}">{status.title()}</span>'


def sentiment_label(sentiment: str | None) -> str:
    sentiment = (sentiment or "neutral").lower()
    icons = {"negative": "😡", "positive": "🙂", "neutral": "😐"}
    return f"{icons.get(sentiment, '😐')} {sentiment.title()}"


def metric_card(label: str, value: str | int, note: str = "") -> None:
    st.markdown(
        f"""
        <div class="metric-card">
          <div class="metric-label">{label}</div>
          <div class="metric-value">{value}</div>
          <div class="metric-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.title("Slack SLA Manager Dashboard")
st.caption("40-second demo SLA with Gemini-assisted triage and response detection.")

left, right = st.columns([1, 0.16])
with right:
    if st.button("Refresh", use_container_width=True):
        st.rerun()

cases = load_cases()
notifications = load_notifications()

if cases.empty:
    st.info("No SLA cases found yet. Run `python scripts/seed_demo_data.py` or start the bot and create a Slack case.")
    st.stop()

for column in ["needs_response", "breached", "escalated"]:
    if column in cases.columns:
        cases[column] = cases[column].fillna(0).astype(int)

defaults = {
    "sentiment": "neutral",
    "priority": "medium",
    "ai_reason": "",
    "classifier_source": "rule_based",
    "response_source": "",
}
for column, default in defaults.items():
    if column not in cases.columns:
        cases[column] = default
    cases[column] = cases[column].fillna(default)

with st.sidebar:
    st.header("Filters")
    statuses = sorted(cases["status"].dropna().unique().tolist())
    priorities = sorted(cases["priority"].dropna().unique().tolist())
    sentiments = sorted(cases["sentiment"].dropna().unique().tolist())
    channels = sorted(cases["slack_channel_name"].fillna(cases["slack_channel_id"]).dropna().unique().tolist())
    owners = sorted(cases["assigned_owner_user_id"].fillna("Unassigned").unique().tolist())

    selected_statuses = st.multiselect("Status", statuses, default=statuses)
    selected_priorities = st.multiselect("Priority", priorities, default=priorities)
    selected_sentiments = st.multiselect("Sentiment", sentiments, default=sentiments)
    selected_channels = st.multiselect("Channel", channels, default=channels)
    selected_owners = st.multiselect("Assigned owner", owners, default=owners)
    breached_filter = st.selectbox("Breached", ["All", "Breached", "Not breached"])

case_owner = cases["assigned_owner_user_id"].fillna("Unassigned")
filtered = cases[
    cases["status"].isin(selected_statuses)
    & cases["priority"].isin(selected_priorities)
    & cases["sentiment"].isin(selected_sentiments)
    & case_owner.isin(selected_owners)
]
filtered = filtered[
    filtered["slack_channel_name"].fillna(filtered["slack_channel_id"]).isin(selected_channels)
]
if breached_filter == "Breached":
    filtered = filtered[filtered["breached"] == 1]
elif breached_filter == "Not breached":
    filtered = filtered[filtered["breached"] == 0]

total_cases = len(filtered)
open_cases = len(filtered[filtered["status"] == "open"])
ack_cases = len(filtered[filtered["status"] == "acknowledged"])
breached_cases = len(filtered[filtered["status"] == "breached"])
avg_response = filtered["response_time_seconds"].dropna().mean()

st.subheader("SLA Health")
kpi_cols = st.columns(6)
with kpi_cols[0]:
    metric_card("Total cases", total_cases, "All tracked requests")
with kpi_cols[1]:
    metric_card("Open cases", open_cases, "Awaiting response")
with kpi_cols[2]:
    metric_card("Acknowledged", ack_cases, "First response found")
with kpi_cols[3]:
    metric_card("Breached", breached_cases, "Escalated cases")
with kpi_cols[4]:
    metric_card("Compliance rate", pct(compliance_rate(filtered)), "Closed cases within SLA")
with kpi_cols[5]:
    metric_card("Avg first response", seconds_to_label(avg_response), "Acknowledged cases")

st.subheader("Case Queue")
details = filtered.copy()
details["channel"] = details["slack_channel_name"].fillna(details["slack_channel_id"])
details["sentiment_display"] = details["sentiment"].apply(sentiment_label)
details["status_display"] = details.apply(status_badge, axis=1)
details["response_time"] = details["response_time_seconds"].apply(seconds_to_label)
table = details[
    [
        "case_id",
        "channel",
        "message_text",
        "sentiment_display",
        "priority",
        "status_display",
        "created_at",
        "due_at",
        "first_response_at",
        "response_source",
        "ai_reason",
    ]
].rename(
    columns={
        "case_id": "Case ID",
        "channel": "Channel",
        "message_text": "Customer message",
        "sentiment_display": "Sentiment",
        "priority": "Priority",
        "status_display": "Status",
        "created_at": "Created time",
        "due_at": "Due time",
        "first_response_at": "First response time",
        "response_source": "Response source",
        "ai_reason": "AI reason",
    }
)
st.write(table.to_html(escape=False, index=False), unsafe_allow_html=True)

st.subheader("Team Performance")
employee = (
    filtered.groupby("assigned_owner_user_id", dropna=False)
    .agg(
        assigned_cases=("case_id", "count"),
        acknowledged_cases=("status", lambda s: (s == "acknowledged").sum()),
        breached_cases=("breached", "sum"),
        avg_first_response_seconds=("response_time_seconds", "mean"),
    )
    .reset_index()
    .rename(columns={"assigned_owner_user_id": "employee"})
)
employee["sla_compliance_rate"] = employee.apply(
    lambda row: 0
    if row["assigned_cases"] == 0
    else (row["assigned_cases"] - row["breached_cases"]) / row["assigned_cases"],
    axis=1,
)
employee["avg_first_response"] = employee["avg_first_response_seconds"].apply(seconds_to_label)
employee["sla_compliance_rate"] = employee["sla_compliance_rate"].apply(pct)
st.dataframe(
    employee[
        [
            "employee",
            "assigned_cases",
            "acknowledged_cases",
            "breached_cases",
            "avg_first_response",
            "sla_compliance_rate",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

st.subheader("Case Detail")
case_ids = filtered["case_id"].tolist()
selected_case_id = st.selectbox("Select a case", case_ids)
selected = filtered[filtered["case_id"] == selected_case_id].iloc[0]

detail_cols = st.columns([1, 1])
with detail_cols[0]:
    st.markdown("**Original customer message**")
    st.write(selected["message_text"])
    st.markdown("**AI classification**")
    st.write(
        {
            "needs_response": bool(selected.get("needs_response", 1)),
            "sentiment": selected.get("sentiment"),
            "priority": selected.get("priority"),
            "reason": selected.get("ai_reason"),
            "source": selected.get("classifier_source"),
        }
    )
with detail_cols[1]:
    st.markdown("**Slack and response context**")
    st.write(
        {
            "channel": selected.get("slack_channel_name") or selected.get("slack_channel_id"),
            "assigned_employee": selected.get("assigned_owner_user_id"),
            "response_source": selected.get("response_source") or "-",
            "response_match_confidence": selected.get("response_match_confidence"),
        }
    )
    st.markdown("**Timeline**")
    timeline = [
        ("Created", selected.get("created_at")),
        ("Warning sent", None),
        ("Acknowledged", selected.get("first_response_at")),
        ("Breached", selected.get("resolved_at") if selected.get("status") == "breached" else None),
    ]
    if not notifications.empty:
        case_notes = notifications[notifications["case_id"] == selected_case_id]
        warning = case_notes[case_notes["notification_type"] == "warning_25s"]
        breach = case_notes[case_notes["notification_type"] == "breach_40s"]
        if not warning.empty:
            timeline[1] = ("Warning sent", warning.iloc[0]["sent_at"])
        if not breach.empty:
            timeline[3] = ("Breached", breach.iloc[0]["sent_at"])
    for label, value in timeline:
        st.write(f"{label}: {value or '-'}")

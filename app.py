"""
Jules Go-Live Tracker
=====================
Streamlit app for CS team to track client onboarding checklists.

Usage:
  pip install streamlit pandas supabase
  streamlit run app.py

Template: Edit golive_template.csv to change default checklist items.
"""

import streamlit as st
import pandas as pd
import json
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from supabase import create_client as supabase_client
import plotly.graph_objects as go

# ─── Config ───
st.set_page_config(
    page_title="Jules Go-Live Tracker",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

supabase = supabase_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"],
)
TEMPLATE_PATH = Path("golive_template.csv")

STATUSES = ["Not started", "Requested", "In progress", "Approved", "N/A"]
STATUS_COLORS = {
    "Not started": "🔘",
    "Requested": "🟡",
    "In progress": "🔵",
    "Approved": "🟢",
    "N/A": "⚪",
}
TIERS = ["Tier 1", "Tier 2", "Tier 3"]

ROLES = ["csm", "product", "cs_config", "dashboard"]
ROLE_LABELS = {
    "csm": "CSM",
    "product": "Product",
    "cs_config": "CS Config",
    "dashboard": "Dashboard",
}

CATEGORY_ORDER = [
    "Master Data", "Master Data Setup", "Dashboard Setup", "Transaction Migration",
    "External Emails", "Internal Emails", "Views", "Permissions & Access",
    "Integrations", "Documents", "Notifications (Knock)", "Features",
    "SOPs", "UATs", "Trainings",
]

CATEGORY_COLORS = {
    "Master Data": "#FF6B6B", "Master Data Setup": "#4ECDC4",
    "Dashboard Setup": "#45B7D1", "Transaction Migration": "#FFA07A",
    "External Emails": "#98D8C8", "Internal Emails": "#6C5CE7",
    "Views": "#A8E6CF", "Permissions & Access": "#FFD93D",
    "Integrations": "#6BCF7F", "Documents": "#95A5A6",
    "Notifications (Knock)": "#F4A460", "Features": "#BB86FC",
    "SOPs": "#03DAC6", "UATs": "#CF6679", "Trainings": "#FFB74D",
}

CATEGORY_ICONS = {
    "Master Data": "◈", "Master Data Setup": "⚙️", "Dashboard Setup": "📊",
    "Transaction Migration": "🔄", "External Emails": "✉️", "Internal Emails": "📨",
    "Views": "👁️", "Permissions & Access": "🔐", "Integrations": "🔗",
    "Documents": "📄", "Notifications (Knock)": "🔔", "Features": "✨",
    "SOPs": "📖", "UATs": "🧪", "Trainings": "🎓",
}

# ─── Custom CSS ───
st.markdown("""
<style>
    /* Clean dark aesthetic */
    .stApp { background-color: #0a0a0a; }

    section[data-testid="stSidebar"] {
        background-color: #0e0e0e;
        border-right: 1px solid #1a1a1a;
    }

    /* Headers */
    h1 { color: #ffffff !important; letter-spacing: -0.5px; }
    h2 { color: #e8d44d !important; font-size: 1.1rem !important; }
    h3 { color: #cccccc !important; font-size: 0.95rem !important; }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: #141414;
        border: 1px solid #1e1e1e;
        border-radius: 10px;
        padding: 12px 16px;
    }
    [data-testid="stMetricValue"] { color: #ffffff !important; }
    [data-testid="stMetricLabel"] { color: #888888 !important; }

    /* Data editor */
    [data-testid="stDataEditor"] {
        border: 1px solid #1e1e1e;
        border-radius: 8px;
    }

    /* Expander */
    [data-testid="stExpander"] {
        background: #111111;
        border: 1px solid #1e1e1e;
        border-radius: 10px;
    }

    /* Progress bar */
    .stProgress > div > div { background-color: #1a1a1a; border-radius: 4px; }
    .stProgress > div > div > div { border-radius: 4px; }

    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
    }

    /* Dividers */
    hr { border-color: #1a1a1a !important; }

    div[data-testid="stVerticalBlock"] > div:has(> .category-header) {
        margin-bottom: 0 !important;
    }
</style>
""", unsafe_allow_html=True)

# ── Week banner (sticky) ──
_today = date.today()
_week_num = _today.isocalendar()[1]
_date_str = f"{_today.strftime('%B')} {_today.day}, {_today.year}"
st.markdown(
    f"""<div style="
        position:sticky; top:0; z-index:999;
        background:#111111; color:#888888;
        padding:6px 18px; font-size:12px; font-weight:600;
        border-bottom:1px solid #1a1a1a; margin-bottom:8px;
        letter-spacing:0.05em;
    ">📅 WEEK {_week_num} &nbsp;·&nbsp; {_date_str}</div>""",
    unsafe_allow_html=True,
)


# ─── Data Helpers ───

def load_template(csv_source=None):
    """Load checklist template from CSV.

    Args:
        csv_source: A file path (str/Path), a file-like object (from st.file_uploader),
                    or None to use the default template.

    Returns:
        dict: {category: [{"item": ..., "points": ..., "default_assignee": ..., "default_role": ...}, ...]}
    """
    if csv_source is not None:
        try:
            df = pd.read_csv(csv_source)
        except Exception as e:
            st.error(f"Could not read CSV: {e}")
            return {}
    elif TEMPLATE_PATH.exists():
        df = pd.read_csv(TEMPLATE_PATH)
    else:
        st.error(
            "No template found. Place a `golive_template.csv` in the app directory, "
            "or upload one via the Template section in the sidebar."
        )
        return {}

    # Normalize columns
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    required = {"category", "item", "points"}
    missing = required - set(df.columns)
    if missing:
        st.error(
            f"CSV is missing required columns: {missing}. "
            f"Required: category, item, points. Found: {', '.join(df.columns)}"
        )
        return {}

    # Detect role columns
    has_role_cols = any(r in df.columns for r in ROLES)

    template = {}
    for _, row in df.iterrows():
        cat = str(row["category"]).strip()
        if cat not in template:
            template[cat] = []

        # Determine default_role from role columns
        default_role = ""
        if has_role_cols:
            for role in ROLES:
                val = str(row.get(role, "")).strip().lower()
                if val and val not in ("", "nan", "0", "false"):
                    default_role = role
                    break

        # Fall back to default_assignee column if no role columns
        default_assignee = ""
        if not has_role_cols:
            raw = row.get("default_assignee", "")
            default_assignee = str(raw).strip() if pd.notna(raw) else ""

        # Get date offsets if present (days before go-live)
        start_offset = row.get("start_offset_days", "")
        end_offset = row.get("end_offset_days", "")

        raw_pts = row.get("points")
        template[cat].append({
            "item": str(row["item"]).strip(),
            "points": float(raw_pts) if pd.notna(raw_pts) and raw_pts != "" else 1.0,
            "default_assignee": default_assignee,
            "default_role": default_role,
            "start_offset_days": int(start_offset) if pd.notna(start_offset) and start_offset != "" else None,
            "end_offset_days": int(end_offset) if pd.notna(end_offset) and end_offset != "" else None,
        })
    return template


def create_client(name, tier, go_live_date, account_manager, tech_lead, template,
                  roles=None, template_id=None):
    """Create a new client dict from template.

    Args:
        roles: dict like {"csm": "Alice", "product": "Bob", ...} mapping role to person name.
        template_id: optional ID of the DB template used.
    """
    checklist = {}
    for cat, items in template.items():
        checklist[cat] = []
        for it in items:
            # Resolve assignee: if roles provided and item has default_role, use the person
            assignee = it.get("default_assignee", "")
            if roles and it.get("default_role"):
                role_person = roles.get(it["default_role"], "")
                if role_person:
                    assignee = role_person

            # Calculate dates from offsets if go_live_date is provided
            start_date_str = ""
            end_date_str = ""
            if go_live_date and it.get("start_offset_days") is not None and it.get("end_offset_days") is not None:
                # Convert go_live_date to date object if it's not already
                if isinstance(go_live_date, str):
                    try:
                        go_live_dt = date.fromisoformat(go_live_date)
                    except (ValueError, TypeError):
                        go_live_dt = go_live_date
                else:
                    go_live_dt = go_live_date

                # Calculate actual dates by subtracting offsets from go-live date
                start_dt = go_live_dt - timedelta(days=it["start_offset_days"])
                end_dt = go_live_dt - timedelta(days=it["end_offset_days"])
                start_date_str = str(start_dt)
                end_date_str = str(end_dt)

            checklist[cat].append({
                "id": str(uuid.uuid4())[:8],
                "item": it["item"],
                "points": it["points"],
                "status": "Not started",
                "assignee": assignee,
                "notes": "",
                "start_date": start_date_str,
                "end_date": end_date_str,
            })

    return {
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "tier": tier,
        "go_live_date": str(go_live_date) if go_live_date else "",
        "kickoff_date": "",
        "account_manager": account_manager,
        "tech_lead": tech_lead,
        "roles": roles or {},
        "template_id": template_id or "",
        "created_at": datetime.now().isoformat(),
        "checklist": checklist,
    }


def save_client(client):
    """Save client data to Supabase."""
    supabase.table("clients").upsert({
        "id": client["id"],
        "data": client,
        "created_at": client.get("created_at"),
    }).execute()


def migrate_client_dates(client):
    """Migrate old due_date field to start_date/end_date if needed."""
    for cat, items in client.get("checklist", {}).items():
        for it in items:
            # If old due_date exists but new fields don't
            if "due_date" in it and ("start_date" not in it or "end_date" not in it):
                due = it.get("due_date", "")
                # Migrate: due_date becomes end_date, leave start_date empty
                it["start_date"] = ""
                it["end_date"] = due if due else ""
                # Remove old field
                if "due_date" in it:
                    del it["due_date"]
    return client


def sync_template_categories(client, template):
    """Add missing categories and items from template to an existing client.

    - Adds entire categories that are missing in the client's checklist.
    - Adds missing items within existing categories.
    - Never modifies or deletes existing items.
    Returns (client, added_categories, added_items).
    """
    go_live_date = client.get("go_live_date", "")
    try:
        go_live_dt = date.fromisoformat(go_live_date) if go_live_date else None
    except ValueError:
        go_live_dt = None

    roles = client.get("roles", {})
    checklist = client.setdefault("checklist", {})
    added_categories = []
    added_items = []

    for cat, tpl_items in template.items():
        if cat not in checklist:
            # Entire category missing — add it
            checklist[cat] = []
            for it in tpl_items:
                assignee = it.get("default_assignee", "")
                if roles and it.get("default_role"):
                    assignee = roles.get(it["default_role"], assignee)
                start_str, end_str = "", ""
                if go_live_dt and it.get("start_offset_days") is not None and it.get("end_offset_days") is not None:
                    start_str = str(go_live_dt - timedelta(days=it["start_offset_days"]))
                    end_str   = str(go_live_dt - timedelta(days=it["end_offset_days"]))
                checklist[cat].append({
                    "id": str(uuid.uuid4())[:8],
                    "item": it["item"],
                    "points": it["points"],
                    "status": "Not started",
                    "assignee": assignee,
                    "notes": "",
                    "start_date": start_str,
                    "end_date": end_str,
                })
            added_categories.append(cat)
        else:
            # Category exists — add items that are missing (match by item name)
            existing_labels = {i["item"].strip().lower() for i in checklist[cat]}
            for it in tpl_items:
                if it["item"].strip().lower() not in existing_labels:
                    assignee = it.get("default_assignee", "")
                    if roles and it.get("default_role"):
                        assignee = roles.get(it["default_role"], assignee)
                    start_str, end_str = "", ""
                    if go_live_dt and it.get("start_offset_days") is not None and it.get("end_offset_days") is not None:
                        start_str = str(go_live_dt - timedelta(days=it["start_offset_days"]))
                        end_str   = str(go_live_dt - timedelta(days=it["end_offset_days"]))
                    checklist[cat].append({
                        "id": str(uuid.uuid4())[:8],
                        "item": it["item"],
                        "points": it["points"],
                        "status": "Not started",
                        "assignee": assignee,
                        "notes": "",
                        "start_date": start_str,
                        "end_date": end_str,
                    })
                    added_items.append(f"{cat} › {it['item']}")

    return client, added_categories, added_items


def load_all_clients():
    """Load all clients from Supabase."""
    res = supabase.table("clients").select("data").order("created_at", desc=True).execute()
    clients = [row["data"] for row in res.data]
    # Migrate old date format
    return [migrate_client_dates(c) for c in clients]


def delete_client(client_id):
    """Delete a client from Supabase. Returns True on success."""
    try:
        supabase.table("clients").delete().eq("id", client_id).execute()
        return True
    except Exception as e:
        st.error(f"Could not delete client: {e}")
        return False


# ─── Team Members Helpers ───

def load_team_members():
    """Load team members from Supabase, grouped by role.

    Returns:
        dict: {"csm": ["Alice", ...], "product": ["Bob", ...], ...}
    """
    try:
        res = supabase.table("team_members").select("name, role").order("name").execute()
        members = {r: [] for r in ROLES}
        for row in res.data:
            role = row["role"]
            if role in members:
                members[role].append(row["name"])
        return members
    except Exception:
        return {r: [] for r in ROLES}


def save_team_member(name, role):
    """Upsert a team member into Supabase."""
    try:
        supabase.table("team_members").upsert({
            "name": name.strip(),
            "role": role,
        }, on_conflict="name,role").execute()
    except Exception as e:
        st.error(f"Could not save team member: {e}")


# ─── Templates Helpers ───

def load_db_templates():
    """Load all named templates from Supabase.

    Returns:
        list: [{"id": ..., "name": ..., "data": {...}}, ...]
    """
    try:
        res = supabase.table("templates").select("id, name, data").order("name").execute()
        return res.data
    except Exception:
        return []


def save_template_to_db(name, template_data):
    """Save a named template to Supabase."""
    try:
        supabase.table("templates").upsert({
            "name": name.strip(),
            "data": template_data,
        }, on_conflict="name").execute()
        return True
    except Exception as e:
        st.error(f"Could not save template: {e}")
        return False


def delete_template_from_db(template_id):
    """Delete a template from Supabase."""
    try:
        supabase.table("templates").delete().eq("id", template_id).execute()
        return True
    except Exception as e:
        st.error(f"Could not delete template: {e}")
        return False


# ─── Stats Helper ───

def get_client_stats(client):
    """Calculate completion stats for a client."""
    total = 0
    done = 0
    total_points = 0
    done_points = 0
    by_category = {}

    for cat, items in client.get("checklist", {}).items():
        cat_total = len(items)
        cat_done = sum(1 for i in items if i["status"] in ("Approved", "N/A"))
        cat_points = sum(i["points"] for i in items)
        cat_done_pts = sum(i["points"] for i in items if i["status"] in ("Approved", "N/A"))

        total += cat_total
        done += cat_done
        total_points += cat_points
        done_points += cat_done_pts
        by_category[cat] = {
            "total": cat_total,
            "done": cat_done,
            "pct": round(cat_done / cat_total * 100) if cat_total > 0 else 0,
            "points": cat_points,
            "done_points": cat_done_pts,
        }

    return {
        "total": total,
        "done": done,
        "pct": round(done / total * 100) if total > 0 else 0,
        "total_points": total_points,
        "done_points": done_points,
        "by_category": by_category,
    }


def get_process_violations(client, stats):
    """Return a list of human-readable process violation strings for a client."""
    violations = []
    today = date.today()
    checklist = client.get("checklist", {})

    go_live = client.get("go_live_date", "")
    try:
        go_live_dt = date.fromisoformat(go_live) if go_live else None
        days_left = (go_live_dt - today).days if go_live_dt else None
    except (ValueError, TypeError):
        go_live_dt = None
        days_left = None

    # Rule 1: overdue items (end_date < today and not Approved/N/A)
    for cat, items in checklist.items():
        overdue = []
        for it in items:
            end = it.get("end_date", "")
            if not end or it["status"] in ("Approved", "N/A"):
                continue
            try:
                if date.fromisoformat(end) < today:
                    overdue.append(it["item"])
            except (ValueError, TypeError):
                pass
        if overdue:
            violations.append(f"{cat} — {len(overdue)} item(s) overdue")

    # Rule 2: category behind schedule relative to go-live
    if days_left is not None and 0 <= days_left <= 14:
        for cat, cat_s in stats["by_category"].items():
            if cat_s["pct"] < 50 and cat_s["total"] > 0:
                violations.append(f"{cat} only {cat_s['pct']}% with {days_left}d to go-live")

    # Rule 3: late categories started before early ones are done
    # "Early" = first half of CATEGORY_ORDER, "Late" = UATs / Trainings
    early_cats = CATEGORY_ORDER[:8]
    late_cats = ["UATs", "Trainings"]

    early_incomplete = any(
        stats["by_category"].get(c, {}).get("pct", 0) < 30
        for c in early_cats if c in stats["by_category"]
    )
    for cat in late_cats:
        cat_s = stats["by_category"].get(cat, {})
        if cat_s.get("done", 0) > 0 and early_incomplete:
            violations.append(f"{cat} started before foundational categories complete")

    return violations


def _parse_approved_at(it):
    val = it.get("approved_at", "")
    if not val:
        return None
    try:
        return datetime.fromisoformat(val)
    except (ValueError, TypeError):
        return None

def _first_approved_at(items):
    """Earliest approved_at timestamp in a list of items."""
    ts = [t for it in items if (t := _parse_approved_at(it)) is not None]
    return min(ts) if ts else None

def _last_approved_at(items):
    """Latest approved_at timestamp in a list of items."""
    ts = [t for it in items if (t := _parse_approved_at(it)) is not None]
    return max(ts) if ts else None


def get_compliance_results(clients, all_stats):
    """Evaluate protocol compliance rules for all clients.

    Returns a list of rule dicts:
      {"label": str, "desc": str, "results": {client_id: "pass"|"fail"|"na"}}
    """
    today = date.today()

    # Categories considered "setup/config" work that must precede UATs
    CONFIG_CATS = [
        "Master Data", "Master Data Setup", "Dashboard Setup",
        "External Emails", "Internal Emails", "Views",
        "Permissions & Access", "Documents",
    ]

    rules_meta = [
        ("Master Data 100% complete", "All Master Data items must be Approved before go-live."),
        ("SOPs done before UATs", "All SOP items must be Approved before the first UAT is approved."),
        ("Config/Setup done before UATs", "Setup categories (Master Data, Emails, Views…) must be complete before any UAT is approved."),
        ("UATs complete before go-live", "All UAT items must be Approved before the go-live date."),
        ("No overdue items", "No item with an end date in the past should be pending."),
        ("On schedule", "Progress is consistent with time remaining to go-live."),
        ("Master data within 5d of kick-off", "All Master Data items should be Approved within 5 days of the kick-off date."),
        ("First UAT within 7d of kick-off", "First UAT should be Approved within 7 days of the kick-off date."),
    ]

    compliance = [{"label": lbl, "desc": desc, "results": {}} for lbl, desc in rules_meta]

    for client, stats in zip(clients, all_stats):
        cid = client["id"]
        checklist = client.get("checklist", {})
        go_live = client.get("go_live_date", "")
        try:
            go_live_dt = date.fromisoformat(go_live) if go_live else None
            days_left = (go_live_dt - today).days if go_live_dt else None
        except (ValueError, TypeError):
            go_live_dt = None
            days_left = None

        kickoff = client.get("kickoff_date", "")
        try:
            kickoff_dt = date.fromisoformat(kickoff) if kickoff else None
        except (ValueError, TypeError):
            kickoff_dt = None

        sops = checklist.get("SOPs", [])
        uats = checklist.get("UATs", [])

        # ── Rule 0: Master Data 100% ──
        md_pct = stats["by_category"].get("Master Data", {}).get("pct", None)
        if md_pct is None:
            compliance[0]["results"][cid] = "na"
        else:
            compliance[0]["results"][cid] = "pass" if md_pct == 100 else "fail"

        # ── Rule 1: SOPs done before first UAT approved ──
        if not sops or not uats:
            compliance[1]["results"][cid] = "na"
        else:
            first_uat_ts = _first_approved_at(uats)
            if first_uat_ts is None:
                # No UAT approved yet — pass (nothing violated)
                compliance[1]["results"][cid] = "pass"
            else:
                last_sop_ts = _last_approved_at(sops)
                sops_pct = stats["by_category"].get("SOPs", {}).get("pct", 0)
                if sops_pct < 100:
                    # UAT approved but SOPs not complete → fail regardless of timestamps
                    compliance[1]["results"][cid] = "fail"
                elif last_sop_ts is not None and last_sop_ts < first_uat_ts:
                    # Last SOP was approved before first UAT → correct order
                    compliance[1]["results"][cid] = "pass"
                else:
                    # SOPs done but no timestamps to verify order
                    compliance[1]["results"][cid] = "pass"

        # ── Rule 2: Config/Setup done before UATs ──
        config_items = [it for cat in CONFIG_CATS for it in checklist.get(cat, [])]
        if not config_items or not uats:
            compliance[2]["results"][cid] = "na"
        else:
            first_uat_ts = _first_approved_at(uats)
            if first_uat_ts is None:
                # No UAT approved yet
                compliance[2]["results"][cid] = "na"
            else:
                # Check: any config item still not done when UATs started?
                config_not_done = [
                    it for it in config_items
                    if it["status"] not in ("Approved", "N/A")
                ]
                if config_not_done:
                    # Config items still pending while UATs are approved → fail
                    compliance[2]["results"][cid] = "fail"
                else:
                    # All config done — verify order with timestamps if available
                    last_config_ts = _last_approved_at(config_items)
                    if last_config_ts is not None:
                        compliance[2]["results"][cid] = "pass" if last_config_ts < first_uat_ts else "fail"
                    else:
                        compliance[2]["results"][cid] = "pass"  # done but no timestamps

        # ── Rule 3: UATs complete before go-live ──
        uat_pct = stats["by_category"].get("UATs", {}).get("pct", None)
        if uat_pct is None or go_live_dt is None:
            compliance[3]["results"][cid] = "na"
        elif uat_pct == 100:
            # Verify last UAT was approved before go-live date
            last_uat_ts = _last_approved_at(uats)
            if last_uat_ts is not None:
                compliance[3]["results"][cid] = "pass" if last_uat_ts.date() <= go_live_dt else "fail"
            else:
                # 100% done but no timestamps — fall back to end_date
                uat_ends = []
                for it in uats:
                    try:
                        uat_ends.append(date.fromisoformat(it.get("end_date", "")))
                    except (ValueError, TypeError):
                        pass
                compliance[3]["results"][cid] = "pass" if (not uat_ends or max(uat_ends) <= go_live_dt) else "fail"
        else:
            compliance[3]["results"][cid] = "fail" if (days_left is not None and days_left <= 14) else "na"

        # ── Rule 4: No overdue items ──
        items_with_dates = 0
        has_overdue = False
        for items in checklist.values():
            for it in items:
                end = it.get("end_date", "")
                if end and it["status"] not in ("Approved", "N/A"):
                    items_with_dates += 1
                    try:
                        if date.fromisoformat(end) < today:
                            has_overdue = True
                    except (ValueError, TypeError):
                        pass
        if items_with_dates == 0:
            compliance[4]["results"][cid] = "na"
        else:
            compliance[4]["results"][cid] = "fail" if has_overdue else "pass"

        # ── Rule 5: On schedule ──
        if days_left is None:
            compliance[5]["results"][cid] = "na"
        elif days_left < 0:
            compliance[5]["results"][cid] = "fail" if stats["pct"] < 100 else "pass"
        elif days_left <= 14 and stats["pct"] < 50:
            compliance[5]["results"][cid] = "fail"
        elif days_left <= 30 and stats["pct"] < 25:
            compliance[5]["results"][cid] = "fail"
        else:
            compliance[5]["results"][cid] = "pass"

        # ── Rule 6: Master data within 5d of kick-off ──
        md_items = checklist.get("Master Data", []) + checklist.get("Master Data Setup", [])
        if kickoff_dt is None or not md_items:
            compliance[6]["results"][cid] = "na"
        else:
            last_md_ts = _last_approved_at(md_items)
            if last_md_ts is None:
                md_pct_val = stats["by_category"].get("Master Data", {}).get("pct", 0)
                compliance[6]["results"][cid] = "na" if md_pct_val < 100 else "pass"
            else:
                deadline = kickoff_dt + timedelta(days=5)
                compliance[6]["results"][cid] = "pass" if last_md_ts.date() <= deadline else "fail"

        # ── Rule 7: First UAT within 7d of kick-off ──
        if kickoff_dt is None or not uats:
            compliance[7]["results"][cid] = "na"
        else:
            first_uat_ts = _first_approved_at(uats)
            if first_uat_ts is None:
                compliance[7]["results"][cid] = "na"
            else:
                deadline = kickoff_dt + timedelta(days=7)
                compliance[7]["results"][cid] = "pass" if first_uat_ts.date() <= deadline else "fail"

    return compliance


def get_all_assignees(client):
    """Collect all unique assignee names from a client's checklist + team members."""
    names = set()
    for items in client.get("checklist", {}).values():
        for it in items:
            a = it.get("assignee", "").strip()
            if a:
                names.add(a)
    # Add all team members
    for role_members in st.session_state.get("team_members", {}).values():
        for m in role_members:
            names.add(m)
    return sorted(names)


def create_timeline_chart(client, selected_categories=None):
    """Create a roadmap-style timeline with card views grouped by category.

    Args:
        client: Client data dictionary
        selected_categories: List of category names to display (None = all categories)
    """
    tasks_data = []

    for cat, items in client.get("checklist", {}).items():
        # Filter by selected categories
        if selected_categories and cat not in selected_categories:
            continue

        for it in items:
            start = it.get("start_date", "")
            end = it.get("end_date", "")

            # Skip tasks without date range
            if not start or not end:
                continue

            try:
                start_dt = datetime.fromisoformat(start).date()
                end_dt = datetime.fromisoformat(end).date()

                # Ensure end is after start
                if end_dt < start_dt:
                    end_dt = start_dt

                tasks_data.append({
                    "Task": it["item"],
                    "Start": start_dt,
                    "Finish": end_dt,
                    "Category": cat,
                    "Status": it["status"],
                    "Assignee": it.get("assignee", "Unassigned"),
                    "Points": it["points"],
                    "Icon": CATEGORY_ICONS.get(cat, "📋"),
                })
            except (ValueError, TypeError):
                continue

    if not tasks_data:
        return None

    df = pd.DataFrame(tasks_data)

    # Sort by category order, then by start date within each category
    df["CategoryOrder"] = df["Category"].map(lambda x: CATEGORY_ORDER.index(x) if x in CATEGORY_ORDER else 999)
    df = df.sort_values(["CategoryOrder", "Start"])

    # Create figure
    fig = go.Figure()

    # Group tasks by category and assign y-positions
    # Each category gets its own vertical section
    y_position = 0
    y_tick_vals = []
    y_tick_labels = []
    category_y_ranges = {}  # Track y-range for each category for separator lines

    current_category = None
    card_height = 0.7
    vertical_gap = 0.3  # Gap between tasks within same category
    category_gap = 1.5  # Gap between different categories

    # Assign y-positions grouped by category
    for idx, row in df.iterrows():
        # Check if we're starting a new category
        if row["Category"] != current_category:
            if current_category is not None:
                # Add gap before new category
                y_position += category_gap

            current_category = row["Category"]
            category_start_y = y_position

            # Add category label
            y_tick_vals.append(y_position + card_height / 2)
            y_tick_labels.append(f"{CATEGORY_ICONS.get(current_category, '📋')} {current_category}")

        # Assign this task's y-position
        df.at[idx, "YPosition"] = y_position

        # Track category range
        if current_category not in category_y_ranges:
            category_y_ranges[current_category] = {"min": y_position, "max": y_position + card_height}
        else:
            category_y_ranges[current_category]["max"] = y_position + card_height

        # Move to next position
        y_position += card_height + vertical_gap

    # Draw category separator lines and background rectangles
    for cat, y_range in category_y_ranges.items():
        # Add semi-transparent background for category
        fig.add_shape(
            type="rect",
            x0=df["Start"].min(),
            x1=df["Finish"].max(),
            y0=y_range["min"] - vertical_gap,
            y1=y_range["max"] + vertical_gap / 2,
            fillcolor=CATEGORY_COLORS.get(cat, "#95A5A6"),
            opacity=0.05,
            line=dict(width=0),
            layer="below",
        )

    # Draw task cards
    for idx, row in df.iterrows():
        status_marker = STATUS_COLORS.get(row["Status"], "⚪")
        duration_days = (row["Finish"] - row["Start"]).days + 1

        # Task card text (truncated)
        task_short = row['Task'][:40] + "..." if len(row['Task']) > 40 else row['Task']

        hover_text = (
            f"<b>{row['Icon']} {row['Task']}</b><br>"
            f"<b>Category:</b> {row['Category']}<br>"
            f"<b>Status:</b> {status_marker} {row['Status']}<br>"
            f"<b>Assignee:</b> {row['Assignee']}<br>"
            f"<b>Points:</b> {row['Points']}<br>"
            f"<b>Duration:</b> {duration_days} days<br>"
            f"<b>Start:</b> {row['Start'].strftime('%b %d, %Y')}<br>"
            f"<b>End:</b> {row['Finish'].strftime('%b %d, %Y')}"
        )

        # Card position
        y_pos = row["YPosition"]
        y_bottom = y_pos
        y_top = y_pos + card_height

        # Add card as a rectangle
        fig.add_shape(
            type="rect",
            x0=row["Start"],
            x1=row["Finish"],
            y0=y_bottom,
            y1=y_top,
            fillcolor=CATEGORY_COLORS.get(row["Category"], "#95A5A6"),
            line=dict(color='rgba(255,255,255,0.6)', width=2),
            layer="below",
        )

        # Add card label (icon + truncated task name)
        mid_date = row["Start"] + (row["Finish"] - row["Start"]) / 2
        mid_y = y_bottom + card_height / 2

        fig.add_annotation(
            x=mid_date,
            y=mid_y,
            text=f"{status_marker} {task_short}",
            showarrow=False,
            font=dict(size=10, color='#ffffff'),
            bgcolor='rgba(0,0,0,0.3)',
            borderpad=4,
        )

        # Add invisible scatter point for hover
        fig.add_trace(go.Scatter(
            x=[mid_date],
            y=[mid_y],
            mode='markers',
            marker=dict(size=0.1, color='rgba(0,0,0,0)'),
            hovertemplate=hover_text + "<extra></extra>",
            showlegend=False,
        ))

    # Add today's date marker
    today = date.today()
    max_y = y_position
    fig.add_shape(
        type="line",
        x0=today,
        x1=today,
        y0=-0.5,
        y1=max_y,
        line=dict(color="cyan", width=2, dash="dash"),
    )
    fig.add_annotation(
        x=today,
        y=max_y,
        text="Today",
        showarrow=False,
        yanchor="bottom",
        font=dict(color="cyan", size=12, weight="bold"),
    )

    # Add go-live date marker if set
    if client.get("go_live_date"):
        try:
            go_live_dt = date.fromisoformat(client["go_live_date"])
            fig.add_shape(
                type="line",
                x0=go_live_dt,
                x1=go_live_dt,
                y0=-0.5,
                y1=max_y,
                line=dict(color="#e8d44d", width=3, dash="solid"),
            )
            fig.add_annotation(
                x=go_live_dt,
                y=max_y,
                text="Go-Live",
                showarrow=False,
                yanchor="bottom",
                font=dict(color="#e8d44d", size=12, weight="bold"),
            )
        except (ValueError, TypeError):
            pass

    # Update layout
    fig.update_layout(
        title={
            'text': "Go-Live Timeline Roadmap",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 20, 'color': '#ffffff'}
        },
        xaxis=dict(
            title="Timeline",
            type='date',
            gridcolor='rgba(255,255,255,0.1)',
            showgrid=True,
        ),
        yaxis=dict(
            title="Categories",
            showticklabels=True,
            tickvals=y_tick_vals,
            ticktext=y_tick_labels,
            range=[-1, max_y + 1],
            gridcolor='rgba(255,255,255,0.05)',
            showgrid=True,
        ),
        height=max(600, int(max_y * 50) + 150),
        plot_bgcolor='rgba(10,10,10,1)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#ffffff', size=11),
        hovermode='closest',
        showlegend=False,  # Hide legend since we show categories on y-axis
        margin=dict(l=250, r=60, t=80, b=60),
    )

    return fig


def create_external_timeline(client, selected_categories=None):
    """Create a category-level timeline: one bar per category spanning its full date range."""
    # Aggregate by category
    cat_data = {}
    for cat, items in client.get("checklist", {}).items():
        if selected_categories and cat not in selected_categories:
            continue
        for it in items:
            start = it.get("start_date", "")
            end = it.get("end_date", "")
            if not start or not end:
                continue
            try:
                start_dt = datetime.fromisoformat(start).date()
                end_dt = datetime.fromisoformat(end).date()
                if end_dt < start_dt:
                    end_dt = start_dt
                if cat not in cat_data:
                    cat_data[cat] = {
                        "earliest_start": start_dt,
                        "latest_end": end_dt,
                        "total": 0,
                        "done": 0,
                    }
                else:
                    if start_dt < cat_data[cat]["earliest_start"]:
                        cat_data[cat]["earliest_start"] = start_dt
                    if end_dt > cat_data[cat]["latest_end"]:
                        cat_data[cat]["latest_end"] = end_dt
                cat_data[cat]["total"] += 1
                if it.get("status") in ("Approved", "N/A"):
                    cat_data[cat]["done"] += 1
            except (ValueError, TypeError):
                continue

    if not cat_data:
        return None

    # Sort by category order
    sorted_cats = sorted(
        cat_data.keys(),
        key=lambda x: CATEGORY_ORDER.index(x) if x in CATEGORY_ORDER else 999,
    )

    fig = go.Figure()
    card_height = 0.8
    y_position = 0
    y_tick_vals = []
    y_tick_labels = []

    for cat in sorted_cats:
        d = cat_data[cat]
        icon = CATEGORY_ICONS.get(cat, "📋")
        color = CATEGORY_COLORS.get(cat, "#95A5A6")
        pct = int(d["done"] / d["total"] * 100) if d["total"] else 0
        duration = (d["latest_end"] - d["earliest_start"]).days + 1

        hover_text = (
            f"<b>{icon} {cat}</b><br>"
            f"<b>Tasks:</b> {d['total']} ({d['done']} done, {pct}%)<br>"
            f"<b>Start:</b> {d['earliest_start'].strftime('%b %d, %Y')}<br>"
            f"<b>End:</b> {d['latest_end'].strftime('%b %d, %Y')}<br>"
            f"<b>Duration:</b> {duration} days"
        )

        y_bottom = y_position
        y_top = y_position + card_height
        mid_date = d["earliest_start"] + (d["latest_end"] - d["earliest_start"]) / 2
        mid_y = y_bottom + card_height / 2

        # Background bar
        fig.add_shape(
            type="rect",
            x0=d["earliest_start"], x1=d["latest_end"],
            y0=y_bottom, y1=y_top,
            fillcolor=color, opacity=0.8,
            line=dict(color='rgba(255,255,255,0.4)', width=1),
            layer="below",
        )
        # Label
        label = f"{icon} {cat}  ·  {d['done']}/{d['total']}  ·  {d['earliest_start'].strftime('%b %d')} → {d['latest_end'].strftime('%b %d')}"
        fig.add_annotation(
            x=mid_date, y=mid_y,
            text=label,
            showarrow=False,
            font=dict(size=11, color='#ffffff'),
            bgcolor='rgba(0,0,0,0.3)',
            borderpad=4,
        )
        # Invisible hover point
        fig.add_trace(go.Scatter(
            x=[mid_date], y=[mid_y],
            mode='markers',
            marker=dict(size=0.1, color='rgba(0,0,0,0)'),
            hovertemplate=hover_text + "<extra></extra>",
            showlegend=False,
        ))

        y_tick_vals.append(mid_y)
        y_tick_labels.append(f"{icon} {cat}")
        y_position += card_height + 0.4

    max_y = y_position
    today = date.today()

    # Today line
    fig.add_shape(type="line", x0=today, x1=today, y0=-0.5, y1=max_y,
                  line=dict(color="cyan", width=2, dash="dash"))
    fig.add_annotation(x=today, y=max_y, text="Today", showarrow=False,
                       yanchor="bottom", font=dict(color="cyan", size=12, weight="bold"))

    # Go-live line
    if client.get("go_live_date"):
        try:
            go_live_dt = date.fromisoformat(client["go_live_date"])
            fig.add_shape(type="line", x0=go_live_dt, x1=go_live_dt, y0=-0.5, y1=max_y,
                          line=dict(color="#e8d44d", width=3, dash="solid"))
            fig.add_annotation(x=go_live_dt, y=max_y, text="Go-Live", showarrow=False,
                               yanchor="bottom", font=dict(color="#e8d44d", size=12, weight="bold"))
        except (ValueError, TypeError):
            pass

    fig.update_layout(
        title={'text': "Go-Live Timeline (External)", 'x': 0.5, 'xanchor': 'center',
               'font': {'size': 18, 'color': '#ffffff'}},
        xaxis=dict(title="Timeline", type='date', gridcolor='rgba(255,255,255,0.1)', showgrid=True),
        yaxis=dict(showticklabels=True, tickvals=y_tick_vals, ticktext=y_tick_labels,
                   range=[-0.5, max_y + 0.5], gridcolor='rgba(255,255,255,0.05)', showgrid=False),
        height=max(400, len(sorted_cats) * 60 + 150),
        plot_bgcolor='rgba(10,10,10,1)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#ffffff', size=11),
        hovermode='closest',
        showlegend=False,
        margin=dict(l=200, r=60, t=60, b=60),
    )
    return fig


# ─── Initialize Session State ───

if "clients" not in st.session_state:
    st.session_state.clients = load_all_clients()

if "active_client_id" not in st.session_state:
    st.session_state.active_client_id = None

if "view_mode" not in st.session_state:
    st.session_state.view_mode = "manager"

if "manager_sub" not in st.session_state:
    st.session_state.manager_sub = "clients"

if "template" not in st.session_state:
    st.session_state.template = load_template()

if "team_members" not in st.session_state:
    st.session_state.team_members = load_team_members()

if "db_templates" not in st.session_state:
    st.session_state.db_templates = load_db_templates()


def refresh_clients():
    st.session_state.clients = load_all_clients()


def refresh_team():
    st.session_state.team_members = load_team_members()


def refresh_templates():
    st.session_state.db_templates = load_db_templates()


# ─── Sidebar ───

with st.sidebar:
    st.markdown("## 🚀 Go-Live Tracker")
    st.caption("Jules · CS Configuration")
    st.divider()

    # ── Navigation ──
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.button(
            "📊 Manager",
            use_container_width=True,
            type="primary" if st.session_state.view_mode == "manager" else "secondary",
        ):
            st.session_state.view_mode = "manager"
            st.session_state.active_client_id = None
            st.rerun()
    with nav_col2:
        if st.button(
            "👤 Accounts",
            use_container_width=True,
            type="primary" if st.session_state.view_mode == "client" else "secondary",
        ):
            st.session_state.view_mode = "client"
            st.rerun()
    st.divider()

    if st.session_state.view_mode == "manager":
        sub_col1, sub_col2 = st.columns(2)
        with sub_col1:
            if st.button(
                "👥 Clients",
                use_container_width=True,
                type="primary" if st.session_state.manager_sub == "clients" else "secondary",
            ):
                st.session_state.manager_sub = "clients"
                st.rerun()
        with sub_col2:
            if st.button(
                "✅ Protocol",
                use_container_width=True,
                type="primary" if st.session_state.manager_sub == "compliance" else "secondary",
            ):
                st.session_state.manager_sub = "compliance"
                st.rerun()
        st.divider()

    if st.session_state.view_mode == "client":
        # ── New Client ──
        with st.expander("➕ **New Client**", expanded=False):
            new_name = st.text_input("Client name", key="new_name")
            col1, col2, col3 = st.columns(3)
            with col1:
                new_tier = st.selectbox("Tier", TIERS, key="new_tier")
            with col2:
                new_kickoff = st.date_input("Kick-off date", value=None, key="new_kickoff")
            with col3:
                new_date = st.date_input("Go-Live date", value=None, key="new_date")
            # ── Role Assignments ──
            st.markdown("**Team Roles**")
            role_selections = {}
            new_members_to_save = []

            for role in ROLES:
                label = ROLE_LABELS[role]
                members = st.session_state.team_members.get(role, [])
                options = ["(none)"] + members + ["-- Add new --"]
                sel = st.selectbox(label, options, key=f"new_role_{role}")

                if sel == "-- Add new --":
                    new_member = st.text_input(f"New {label} name", key=f"new_member_{role}")
                    if new_member.strip():
                        role_selections[role] = new_member.strip()
                        new_members_to_save.append((new_member.strip(), role))
                    else:
                        role_selections[role] = ""
                elif sel == "(none)":
                    role_selections[role] = ""
                else:
                    role_selections[role] = sel

            # ── Template Selection ──
            st.divider()
            st.markdown("**Template**")
            custom_csv = st.file_uploader(
                "Upload custom template CSV",
                type=["csv"],
                key="custom_csv",
                help="If a file is uploaded here, it will be used instead of the dropdown selection below.",
            )
            template_options = ["Default (file)"] + [t["name"] for t in st.session_state.db_templates]
            selected_template = st.selectbox(
                "Or select a saved template",
                template_options,
                key="new_template",
                disabled=(custom_csv is not None),
                help="Disabled when a custom CSV is uploaded above.",
            )

            if st.button("🚀 Create Client", use_container_width=True, type="primary"):
                if new_name.strip():
                    # Check for duplicate name
                    existing_names = [c["name"].lower() for c in st.session_state.clients]
                    if new_name.strip().lower() in existing_names:
                        st.warning("A client with this name already exists.")
                    else:
                        # Save any new team members first
                        for member_name, member_role in new_members_to_save:
                            save_team_member(member_name, member_role)
                        if new_members_to_save:
                            refresh_team()

                        # Resolve template
                        tpl = None
                        tpl_id = ""
                        if custom_csv is not None:
                            tpl = load_template(csv_source=custom_csv)
                        elif selected_template != "Default (file)":
                            # Find the DB template
                            for db_tpl in st.session_state.db_templates:
                                if db_tpl["name"] == selected_template:
                                    tpl = db_tpl["data"]
                                    tpl_id = db_tpl["id"]
                                    break
                        else:
                            tpl = st.session_state.template

                        if tpl:
                            # Clean role selections (remove empty)
                            roles = {k: v for k, v in role_selections.items() if v}
                            client = create_client(
                                new_name.strip(), new_tier, new_date,
                                roles.get("csm", ""), roles.get("cs_config", ""), tpl,
                                roles=roles, template_id=tpl_id,
                            )
                            client["kickoff_date"] = str(new_kickoff) if new_kickoff else ""
                            with st.spinner("Creating client…"):
                                save_client(client)
                                refresh_clients()
                            st.session_state.active_client_id = client["id"]
                            st.toast(f"✅ {new_name.strip()} created!", icon="🚀")
                            st.rerun()
                        else:
                            st.error("No valid template loaded.")
                else:
                    st.warning("Enter a client name.")

        st.divider()

        # ── Client List ──
        st.markdown("### Clients")

        if not st.session_state.clients:
            st.caption("No clients yet. Create one above.")
        else:
            for client in st.session_state.clients:
                stats = get_client_stats(client)
                is_active = client["id"] == st.session_state.active_client_id

                # Client button
                label = f"{'▸ ' if is_active else '  '}{client['name']}"
                col_btn, col_pct = st.columns([4, 1])
                with col_btn:
                    if st.button(
                        label,
                        key=f"client_{client['id']}",
                        use_container_width=True,
                        type="primary" if is_active else "secondary",
                    ):
                        st.session_state.active_client_id = client["id"]
                        st.session_state.view_mode = "client"
                        st.rerun()
                with col_pct:
                    color = "🟢" if stats["pct"] == 100 else "🟡" if stats["pct"] > 50 else "🔴"
                    st.markdown(f"<div style='text-align:center;padding-top:8px;font-size:13px;'>{color} {stats['pct']}%</div>", unsafe_allow_html=True)

                # Mini progress bar
                st.progress(stats["pct"] / 100)

        st.divider()

        # ── Template Management ──
        with st.expander("📋 **Templates**", expanded=False):
            st.caption("Manage Go-Live templates")

            # ── All available templates ──
            st.markdown("**Available templates**")

            # Default (file-based) template
            default_tpl = st.session_state.template
            default_cats = len(default_tpl) if default_tpl else 0
            default_items = sum(len(v) for v in default_tpl.values()) if default_tpl else 0
            col_n, col_dl = st.columns([3, 1])
            with col_n:
                st.caption(f"📋 **Default** — {default_cats} categories, {default_items} items")
            with col_dl:
                if TEMPLATE_PATH.exists():
                    with open(TEMPLATE_PATH, "rb") as f:
                        st.download_button(
                            "⬇️",
                            f.read(),
                            file_name="golive_template.csv",
                            mime="text/csv",
                            key="dl_default_tpl",
                        )

            # DB templates
            if st.session_state.db_templates:
                for tpl in st.session_state.db_templates:
                    tpl_data = tpl["data"] if isinstance(tpl["data"], dict) else {}
                    cat_count = len(tpl_data)
                    item_count = sum(len(v) for v in tpl_data.values())
                    col_n, col_dl, col_del = st.columns([3, 1, 1])
                    with col_n:
                        st.caption(f"📋 **{tpl['name']}** — {cat_count} categories, {item_count} items")
                    with col_dl:
                        # Build CSV from template data for download
                        rows = []
                        for cat, items in tpl_data.items():
                            for it in items:
                                row = {"category": cat, "item": it.get("item", ""), "points": it.get("points", 1)}
                                for role in ROLES:
                                    row[role] = "x" if it.get("default_role") == role else ""
                                rows.append(row)
                        if rows:
                            tpl_csv = pd.DataFrame(rows).to_csv(index=False)
                        else:
                            tpl_csv = ""
                        st.download_button(
                            "⬇️",
                            tpl_csv,
                            file_name=f"{tpl['name'].lower().replace(' ', '_')}_template.csv",
                            mime="text/csv",
                            key=f"dl_tpl_{tpl['id']}",
                        )
                    with col_del:
                        if st.button("🗑", key=f"del_tpl_{tpl['id']}"):
                            delete_template_from_db(tpl["id"])
                            refresh_templates()
                            st.rerun()
            else:
                st.caption("_No saved templates yet._")

            st.divider()

            # ── Upload new template ──
            st.markdown("**Upload a new template**")
            tpl_name = st.text_input("Template name", key="tpl_upload_name")
            tpl_file = st.file_uploader("Template CSV", type=["csv"], key="tpl_upload_file")
            if tpl_file is not None and tpl_name.strip():
                if st.button("💾 Save template", use_container_width=True):
                    parsed = load_template(csv_source=tpl_file)
                    if parsed:
                        if save_template_to_db(tpl_name.strip(), parsed):
                            refresh_templates()
                            st.success(f"Template '{tpl_name.strip()}' saved!")
                            st.rerun()


# ─── Main Content ───

# Find active client
active = None
if st.session_state.active_client_id:
    for c in st.session_state.clients:
        if c["id"] == st.session_state.active_client_id:
            active = c
            break

if st.session_state.view_mode == "manager" or active is None:
    # ─── Manager View ───
    clients = st.session_state.clients
    all_stats_raw = [get_client_stats(c) for c in clients]
    all_stats = list(zip(clients, all_stats_raw))

    def _client_status(client, stats):
        pct = stats["pct"]
        go_live = client.get("go_live_date", "")
        try:
            days_left = (date.fromisoformat(go_live) - date.today()).days if go_live else 999
        except (ValueError, TypeError):
            days_left = 999
        if days_left < 0:
            return "OVERDUE"
        if days_left <= 14 and pct < 60:
            return "BLOCKED"
        if days_left <= 30 and pct < 50:
            return "AT RISK"
        return "ON TRACK"

    statuses = [_client_status(c, s) for c, s in all_stats]

    n_total = len(clients)
    n_on_track = statuses.count("ON TRACK")
    n_at_risk = statuses.count("AT RISK")
    n_blocked = sum(1 for s in statuses if s in ("BLOCKED", "OVERDUE"))
    avg_pct = round(sum(s["pct"] for _, s in all_stats) / n_total) if n_total else 0

    # Pre-compute compliance for the header metric
    _compliance_rules = get_compliance_results(clients, all_stats_raw)
    _total_pass = sum(
        1 for rule in _compliance_rules
        for c in clients if rule["results"].get(c["id"]) == "pass"
    )
    _total_applicable = sum(
        1 for rule in _compliance_rules
        for c in clients if rule["results"].get(c["id"]) in ("pass", "fail")
    )
    compliance_pct = round(_total_pass / _total_applicable * 100) if _total_applicable else 100

    st.markdown("## Onboarding Command Center")
    st.caption("Manager view — all active clients")
    st.divider()

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("Active Clients", n_total)
    with col2:
        st.metric("On Track", n_on_track)
    with col3:
        st.metric("At Risk", n_at_risk)
    with col4:
        st.metric("Blocked", n_blocked)
    with col5:
        st.metric("Avg Progress", f"{avg_pct}%")
    with col6:
        st.metric("Protocol %", f"{compliance_pct}%")

    st.divider()

    if not clients:
        st.info("No clients yet. Create one from the sidebar.")
        st.stop()

    STATUS_META = {
        "ON TRACK": ("🟢", "#4CAF50"),
        "AT RISK":  ("🟡", "#e8d44d"),
        "BLOCKED":  ("🔴", "#CF6679"),
        "OVERDUE":  ("🔴", "#CF6679"),
    }

    # ── Sub-view driven by sidebar buttons ──
    if st.session_state.manager_sub == "clients":
        mgr_cols = st.columns(2)
        for i, (client, stats) in enumerate(all_stats):
            status = statuses[i]
            badge_emoji, badge_color = STATUS_META.get(status, ("⚪", "#888"))

            go_live = client.get("go_live_date", "")
            try:
                go_live_dt = date.fromisoformat(go_live) if go_live else None
                days_left = (go_live_dt - date.today()).days if go_live_dt else None
            except (ValueError, TypeError):
                go_live_dt = None
                days_left = None

            go_live_str = go_live_dt.strftime("%b %d, %Y") if go_live_dt else "—"
            days_str = (
                f"{days_left}d left" if days_left is not None and days_left >= 0
                else (f"{abs(days_left)}d overdue" if days_left is not None else "—")
            )

            # Categories: dynamic from client data, sorted by canonical order
            sorted_cats = sorted(
                stats["by_category"].items(),
                key=lambda x: CATEGORY_ORDER.index(x[0]) if x[0] in CATEGORY_ORDER else 999,
            )

            cat_rows_html = ""
            for cat, cat_s in sorted_cats:
                pct = cat_s["pct"]
                done = cat_s["done"]
                total = cat_s["total"]
                icon = CATEGORY_ICONS.get(cat, "📋")
                bar_color = CATEGORY_COLORS.get(cat, "#444")
                cat_rows_html += (
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:5px;">'
                    f'<span style="font-size:11px;color:#666;width:18px;text-align:center;">{icon}</span>'
                    f'<span style="font-size:11px;color:#aaa;width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{cat}</span>'
                    f'<div style="flex:1;background:#1e1e1e;border-radius:3px;height:6px;min-width:60px;">'
                    f'<div style="width:{pct}%;background:{bar_color};height:6px;border-radius:3px;"></div>'
                    f'</div>'
                    f'<span style="font-size:10px;color:#aaa;width:52px;text-align:right;">{done}/{total}</span>'
                    f'</div>'
                )

            # Process violations — orange banner
            violations = get_process_violations(client, stats)
            violations_banner = ""
            if violations:
                v_text = " &nbsp;·&nbsp; ".join(violations)
                violations_banner = (
                    f'<div style="background:#2a1500;padding:8px 14px;'
                    f'border-top:1px solid #7a3800;border-bottom:1px solid #7a3800;'
                    f'font-size:10px;color:#EA580C;font-weight:500;">'
                    f'<span style="background:#DC2626;color:#fff;font-size:9px;font-weight:700;'
                    f'padding:1px 7px;border-radius:10px;margin-right:8px;">{len(violations)}</span>'
                    f'{v_text}'
                    f'</div>'
                )

            roles = client.get("roles", {})
            csm = roles.get("csm", "—")
            tier = client.get("tier", "—")

            card_html = (
                f'<div style="background:#111111;border:1px solid #222;'
                f'border-left:3px solid {badge_color};border-radius:10px;'
                f'overflow:hidden;margin-bottom:16px;">'
                f'<div style="padding:16px 18px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px;">'
                f'<div>'
                f'<div style="font-size:15px;font-weight:700;color:#ffffff;">{client["name"]}</div>'
                f'<div style="font-size:11px;color:#555;margin-top:3px;">{tier} &nbsp;·&nbsp; CSM: {csm}</div>'
                f'</div>'
                f'<div style="text-align:right;">'
                f'<div style="display:inline-block;background:{badge_color}22;color:{badge_color};'
                f'font-size:10px;font-weight:700;padding:2px 10px;border-radius:20px;'
                f'border:1px solid {badge_color}55;margin-bottom:4px;">{badge_emoji} {status}</div>'
                f'<div style="font-size:11px;color:#555;">{go_live_str} &nbsp;·&nbsp; {days_str}</div>'
                f'</div>'
                f'</div>'
                f'<div style="margin-bottom:12px;">'
                f'<div style="display:flex;justify-content:space-between;margin-bottom:4px;">'
                f'<span style="font-size:11px;color:#666;">Overall</span>'
                f'<span style="font-size:11px;color:#ccc;font-weight:600;">{stats["pct"]}% &nbsp;({stats["done"]}/{stats["total"]} items)</span>'
                f'</div>'
                f'<div style="background:#1e1e1e;border-radius:4px;height:6px;">'
                f'<div style="width:{stats["pct"]}%;background:#e8d44d;height:6px;border-radius:4px;"></div>'
                f'</div>'
                f'</div>'
                f'</div>'
                f'{violations_banner}'
                f'<div style="padding:10px 18px 14px;border-top:1px solid #1a1a1a;">'
                f'{cat_rows_html}'
                f'</div>'
                f'</div>'
            )

            with mgr_cols[i % 2]:
                st.markdown(card_html, unsafe_allow_html=True)
                if st.button(
                    f"Open {client['name']} →",
                    key=f"mgr_open_{client['id']}",
                    use_container_width=True,
                ):
                    st.session_state.active_client_id = client["id"]
                    st.session_state.view_mode = "client"
                    st.rerun()

    elif st.session_state.manager_sub == "compliance":
        st.caption("Automated rule checks across all clients — Pass ✅ / Fail ❌ / N/A —")

        compliance = get_compliance_results(clients, all_stats_raw)

        # Build HTML table
        client_names = [c["name"] for c in clients]

        # Header row
        header_cells = '<th style="text-align:left;padding:8px 12px;color:#888;font-size:11px;font-weight:600;border-bottom:1px solid #222;">Rule</th>'
        for name in client_names:
            header_cells += f'<th style="text-align:center;padding:8px 12px;color:#888;font-size:11px;font-weight:600;border-bottom:1px solid #222;">{name}</th>'

        # Score row (pass count per client)
        score_per_client = {c["id"]: 0 for c in clients}
        total_rules = len(compliance)
        for rule in compliance:
            for client in clients:
                if rule["results"].get(client["id"]) == "pass":
                    score_per_client[client["id"]] += 1

        score_cells = '<td style="padding:8px 12px;font-size:11px;color:#666;font-weight:600;">Score</td>'
        for client in clients:
            score = score_per_client[client["id"]]
            score_color = "#4CAF50" if score == total_rules else "#e8d44d" if score >= total_rules // 2 else "#CF6679"
            score_cells += f'<td style="text-align:center;padding:8px 12px;"><span style="color:{score_color};font-weight:700;font-size:13px;">{score}/{total_rules}</span></td>'

        # Data rows
        data_rows = ""
        for rule in compliance:
            desc = rule.get("desc", "")
            row_cells = (
                f'<td style="padding:8px 12px;">'
                f'<div style="font-size:12px;color:#ccc;white-space:nowrap;">{rule["label"]}</div>'
                f'<div style="font-size:10px;color:#555;margin-top:2px;">{desc}</div>'
                f'</td>'
            )
            for client in clients:
                result = rule["results"].get(client["id"], "na")
                if result == "pass":
                    cell = '<span style="color:#4CAF50;font-size:16px;">✅</span>'
                    bg = "rgba(76,175,80,0.06)"
                elif result == "fail":
                    cell = '<span style="color:#CF6679;font-size:16px;">❌</span>'
                    bg = "rgba(207,102,121,0.08)"
                else:
                    cell = '<span style="color:#444;font-size:13px;">—</span>'
                    bg = "transparent"
                row_cells += f'<td style="text-align:center;padding:8px 12px;background:{bg};">{cell}</td>'
            data_rows += f"<tr>{row_cells}</tr>"

        table_html = f"""
        <div style="overflow-x:auto;">
        <table style="width:100%;border-collapse:collapse;background:#111;border-radius:10px;overflow:hidden;">
            <thead>
                <tr style="background:#0e0e0e;">{header_cells}</tr>
            </thead>
            <tbody>
                {data_rows}
                <tr style="background:#0e0e0e;border-top:1px solid #222;">{score_cells}</tr>
            </tbody>
        </table>
        </div>"""

        st.markdown(table_html, unsafe_allow_html=True)

    st.stop()


# ── Client Header ──
stats = get_client_stats(active)

col_title, col_actions = st.columns([5, 2])
with col_title:
    st.title(f"🚀 {active['name']}")
with col_actions:
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        if st.button("🗑 Delete", use_container_width=True):
            st.session_state.confirm_delete = True
    with col_a2:
        # Export current state as CSV
        export_rows = []
        for cat, items in active["checklist"].items():
            for it in items:
                export_rows.append({
                    "category": cat,
                    "item": it["item"],
                    "points": it["points"],
                    "status": it["status"],
                    "assignee": it.get("assignee", ""),
                    "start_date": it.get("start_date", ""),
                    "end_date": it.get("end_date", ""),
                    "notes": it.get("notes", ""),
                })
        export_df = pd.DataFrame(export_rows)
        st.download_button(
            "📥 Export",
            export_df.to_csv(index=False),
            file_name=f"{active['name'].lower().replace(' ', '_')}_golive.csv",
            mime="text/csv",
            use_container_width=True,
        )

# Delete confirmation
if st.session_state.get("confirm_delete"):
    st.warning(f"⚠️ Delete **{active['name']}** and all its data?")
    col_d1, col_d2, col_d3 = st.columns([1, 1, 4])
    with col_d1:
        if st.button("Yes, delete", type="primary"):
            if delete_client(active["id"]):
                st.session_state.active_client_id = None
                st.session_state.confirm_delete = False
                refresh_clients()
                st.rerun()
            else:
                st.session_state.confirm_delete = False
    with col_d2:
        if st.button("Cancel"):
            st.session_state.confirm_delete = False
            st.rerun()

# ── Client Info ──
with st.expander("📝 **Client Info**", expanded=False):
    col1, col2, col3 = st.columns(3)
    with col1:
        new_val = st.selectbox("Tier", TIERS, index=TIERS.index(active.get("tier", "Tier 1")), key="edit_tier")
        if new_val != active.get("tier"):
            active["tier"] = new_val
            save_client(active)
    with col2:
        kickoff = active.get("kickoff_date", "")
        try:
            default_kickoff = date.fromisoformat(kickoff) if kickoff else None
        except ValueError:
            default_kickoff = None
        new_kickoff_val = st.date_input("Kick-off Date", value=default_kickoff, key="edit_kickoff")
        if str(new_kickoff_val) != kickoff:
            active["kickoff_date"] = str(new_kickoff_val) if new_kickoff_val else ""
            save_client(active)
    with col3:
        go_live = active.get("go_live_date", "")
        try:
            default_date = date.fromisoformat(go_live) if go_live else None
        except ValueError:
            default_date = None
        new_val = st.date_input("Go-Live Date", value=default_date, key="edit_date")
        if str(new_val) != go_live:
            active["go_live_date"] = str(new_val) if new_val else ""
            save_client(active)

    # ── Role Assignments for this client ──
    st.markdown("**Team Roles**")
    client_roles = active.get("roles", {})
    role_cols = st.columns(len(ROLES))
    for idx, role in enumerate(ROLES):
        with role_cols[idx]:
            label = ROLE_LABELS[role]
            members = st.session_state.team_members.get(role, [])
            current_val = client_roles.get(role, "")
            # Build options: ensure current value is included
            opts = ["(none)"] + members
            if current_val and current_val not in members:
                opts.append(current_val)
            current_idx = opts.index(current_val) if current_val in opts else 0
            new_role_val = st.selectbox(label, opts, index=current_idx, key=f"edit_role_{role}")
            resolved = "" if new_role_val == "(none)" else new_role_val
            if resolved != client_roles.get(role, ""):
                if "roles" not in active:
                    active["roles"] = {}
                active["roles"][role] = resolved
                save_client(active)

    # ── Sync from template ──
    st.divider()
    st.markdown("**Sync from template**")
    st.caption("Adds missing categories and items from the default template. Never modifies existing data.")
    if st.button("🔄 Sync missing categories & items", use_container_width=True, key="sync_template_btn"):
        tpl = st.session_state.get("template") or load_template()
        if tpl:
            updated, added_cats, added_items = sync_template_categories(active, tpl)
            with st.spinner("Syncing…"):
                save_client(updated)
                refresh_clients()
            total_added = len(added_cats) + len(added_items)
            if total_added == 0:
                st.toast("Already up to date — nothing to add.", icon="✅")
            else:
                msg_parts = []
                if added_cats:
                    msg_parts.append(f"{len(added_cats)} new categories")
                if added_items:
                    msg_parts.append(f"{len(added_items)} new items")
                st.toast("Synced! " + " · ".join(msg_parts), icon="🔄")
            st.rerun()
        else:
            st.error("Could not load template.")


# ── Overall Stats ──
st.divider()

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
with col_m1:
    st.metric("Overall Progress", f"{stats['pct']}%", f"{stats['done']}/{stats['total']} items")
with col_m2:
    st.metric("Points Done", f"{stats['done_points']:.0f}", f"of {stats['total_points']:.0f}")
with col_m3:
    remaining = stats["total"] - stats["done"]
    st.metric("Remaining Items", remaining)
with col_m4:
    if active.get("go_live_date"):
        try:
            go_live_dt = date.fromisoformat(active["go_live_date"])
            days_left = (go_live_dt - date.today()).days
            st.metric("Days to Go-Live", days_left, "days" if days_left > 0 else "⚠️ OVERDUE")
        except ValueError:
            st.metric("Go-Live", "Not set")
    else:
        st.metric("Go-Live", "Not set")

st.progress(stats["pct"] / 100)
st.divider()


# ── View Tabs ──
tab_checklist, tab_ext, tab_int = st.tabs(["📋 Checklist", "📅 Timeline (External)", "🔍 Timeline (Internal)"])

with tab_checklist:
    # ── Category Filter ──
    filter_col1, filter_col2 = st.columns([3, 1])
    with filter_col2:
        status_filter = st.selectbox(
            "Filter by status",
            ["All"] + STATUSES,
            key="status_filter",
        )


    # ── Checklist by Category ──
    CATEGORY_ICONS = {
        "Master Data": "◈",
        "Master Data Setup": "⚙️",
        "Dashboard Setup": "📊",
        "Transaction Migration": "🔄",
        "External Emails": "✉️",
        "Internal Emails": "📨",
        "Views": "👁️",
        "Permissions & Access": "🔐",
        "Integrations": "🔗",
        "Documents": "📄",
        "Notifications (Knock)": "🔔",
        "Features": "✨",
        "SOPs": "📖",
        "UATs": "🧪",
        "Trainings": "🎓",
    }

    # Collect all assignee options for SelectboxColumn
    all_assignees = get_all_assignees(active)

    def date_to_str(val):
        """Normalise any date value to YYYY-MM-DD string (or empty string)."""
        if val is None:
            return ""
        try:
            if pd.isna(val):
                return ""
        except (TypeError, ValueError):
            pass
        if isinstance(val, str):
            return val[:10]
        if hasattr(val, "date") and callable(val.date):
            return val.date().isoformat()
        if hasattr(val, "isoformat"):
            return val.isoformat()[:10]
        return str(val)[:10]

    data_changed = False
    any_bulk_action = False
    unsaved_key = f"_unsaved_{active['id']}"

    for cat, items in active["checklist"].items():
        # Filter items
        if status_filter != "All":
            filtered = [i for i in items if i["status"] == status_filter]
            if not filtered:
                continue
        else:
            filtered = items

        # Category stats
        cat_stats = stats["by_category"].get(cat, {})
        icon = CATEGORY_ICONS.get(cat, "📋")
        pct = cat_stats.get("pct", 0)
        done = cat_stats.get("done", 0)
        total = cat_stats.get("total", 0)

        pct_color = "🟢" if pct == 100 else "🟡" if pct > 50 else "🔴"

        with st.expander(f"{icon} **{cat}** — {pct_color} {done}/{total} ({pct}%)", expanded=(pct < 100)):

            # Build dataframe for editing
            df_data = []
            for it in filtered:
                # Parse start_date and end_date
                raw_start = it.get("start_date", "")
                raw_end = it.get("end_date", "")
                try:
                    start_val = date.fromisoformat(raw_start) if raw_start else None
                except (ValueError, TypeError):
                    start_val = None
                try:
                    end_val = date.fromisoformat(raw_end) if raw_end else None
                except (ValueError, TypeError):
                    end_val = None

                df_data.append({
                    "Select": False,
                    "✓": it["status"] in ("Approved", "N/A"),
                    "Item": it["item"],
                    "Status": it["status"],
                    "Assignee": it.get("assignee", ""),
                    "Start Date": start_val,
                    "End Date": end_val,
                    "Points": it["points"],
                    "Notes": it.get("notes", ""),
                    "_id": it["id"],
                })

            df = pd.DataFrame(df_data)

            edited_df = st.data_editor(
                df.drop(columns=["_id"]),
                key=f"editor_{cat}_{active['id']}",
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Select": st.column_config.CheckboxColumn("", width="small"),
                    "✓": st.column_config.CheckboxColumn("✓", width="small"),
                    "Item": st.column_config.TextColumn("Item", width="large"),
                    "Status": st.column_config.SelectboxColumn(
                        "Status", options=STATUSES, width="medium",
                    ),
                    "Assignee": st.column_config.SelectboxColumn(
                        "Assignee", options=all_assignees, width="medium",
                    ),
                    "Start Date": st.column_config.DateColumn("Start", format="YYYY-MM-DD", width="small"),
                    "End Date": st.column_config.DateColumn("End", format="YYYY-MM-DD", width="small"),
                    "Points": st.column_config.NumberColumn("Pts", width="small", format="%.1f"),
                    "Notes": st.column_config.TextColumn("Notes", width="large"),
                },
                num_rows="dynamic",  # Allows adding/deleting rows
            )

            # Bulk action bar (shown when at least one row is selected)
            n_selected = int(edited_df["Select"].sum()) if "Select" in edited_df.columns else 0
            if n_selected > 0:
                st.caption(f"{n_selected} item(s) selected")
                ba_col1, ba_col2, ba_col3 = st.columns([3, 1, 1])
                with ba_col1:
                    bulk_status = st.selectbox(
                        "Set selected to:",
                        STATUSES,
                        key=f"bulk_status_{cat}_{active['id']}",
                        label_visibility="collapsed",
                    )
                with ba_col2:
                    apply_bulk = st.button("✓ Apply", key=f"bulk_apply_{cat}_{active['id']}", use_container_width=True)
                with ba_col3:
                    delete_bulk = st.button("🗑 Delete", key=f"bulk_delete_{cat}_{active['id']}", use_container_width=True)

                bd_col1, bd_col2, bd_col3 = st.columns([2, 2, 1])
                with bd_col1:
                    bulk_start = st.date_input(
                        "Start date",
                        value=None,
                        key=f"bulk_start_{cat}_{active['id']}",
                        label_visibility="collapsed",
                    )
                with bd_col2:
                    bulk_end = st.date_input(
                        "End date",
                        value=None,
                        key=f"bulk_end_{cat}_{active['id']}",
                        label_visibility="collapsed",
                    )
                with bd_col3:
                    apply_bulk_dates = st.button("📅 Dates", key=f"bulk_dates_{cat}_{active['id']}", use_container_width=True)
            else:
                apply_bulk = False
                delete_bulk = False
                bulk_status = None
                apply_bulk_dates = False
                bulk_start = None
                bulk_end = None

            # Check if data actually changed by comparing with original filtered items
            has_changes = False

            # Quick checks first
            if len(edited_df) != len(filtered):
                has_changes = True
            else:
                # Compare each row with original data
                for idx, row in edited_df.iterrows():
                    if idx >= len(filtered):
                        has_changes = True
                        break

                    original = filtered[idx]

                    # Compare each field (including ✓ checkbox which maps to Approved status)
                    original_checked = original["status"] in ("Approved", "N/A")
                    row_status = str(row["Status"]) if pd.notna(row["Status"]) else original["status"]
                    if (bool(row["✓"]) != original_checked or
                        original["item"] != str(row["Item"]) or
                        original["points"] != float(row["Points"]) or
                        original.get("assignee", "") != str(row["Assignee"] if pd.notna(row["Assignee"]) else "") or
                        original.get("notes", "") != str(row["Notes"] if pd.notna(row["Notes"]) else "") or
                        original["status"] != row_status or
                        date_to_str(original.get("start_date", "")) != date_to_str(row.get("Start Date")) or
                        date_to_str(original.get("end_date", "")) != date_to_str(row.get("End Date"))):
                        has_changes = True
                        break

            # Bulk actions bypass normal change detection and always auto-save
            if apply_bulk or delete_bulk or apply_bulk_dates:
                has_changes = True
                any_bulk_action = True

            if has_changes:
                new_items = []
                for idx, row in edited_df.iterrows():
                    is_selected = bool(row.get("Select", False))
                    if idx < len(filtered):
                        # Bulk delete: skip selected rows
                        if delete_bulk and is_selected:
                            continue
                        # Existing item
                        it = filtered[idx].copy()
                        it["item"] = row["Item"]
                        it["points"] = row["Points"]
                        it["assignee"] = row["Assignee"] if pd.notna(row["Assignee"]) else ""
                        it["notes"] = row["Notes"] if pd.notna(row["Notes"]) else ""
                        # Sync start_date and end_date (always YYYY-MM-DD)
                        it["start_date"] = date_to_str(row.get("Start Date"))
                        it["end_date"] = date_to_str(row.get("End Date"))
                        # Bulk date apply: override start/end for selected rows
                        if apply_bulk_dates and is_selected:
                            if bulk_start:
                                it["start_date"] = date_to_str(bulk_start)
                            if bulk_end:
                                it["end_date"] = date_to_str(bulk_end)
                        # Bulk apply overrides everything else for selected rows
                        prev_status = it["status"]
                        if apply_bulk and is_selected:
                            it["status"] = bulk_status
                            it["approved_at"] = datetime.now().isoformat() if bulk_status == "Approved" else ""
                        elif row["✓"] and prev_status not in ("Approved", "N/A"):
                            it["status"] = "Approved"
                            it["approved_at"] = datetime.now().isoformat()
                        elif not row["✓"] and prev_status in ("Approved", "N/A"):
                            it["status"] = "Not started"
                            it["approved_at"] = ""
                        else:
                            new_status = str(row["Status"]) if pd.notna(row["Status"]) else prev_status
                            it["status"] = new_status
                            if new_status == "Approved" and prev_status != "Approved":
                                it["approved_at"] = datetime.now().isoformat()
                            elif new_status != "Approved":
                                it["approved_at"] = ""
                        new_items.append(it)
                    else:
                        # New row added
                        new_items.append({
                            "id": str(uuid.uuid4())[:8],
                            "item": row["Item"] if pd.notna(row["Item"]) else "New item",
                            "points": float(row["Points"]) if pd.notna(row["Points"]) else 1.0,
                            "status": str(row["Status"]) if pd.notna(row["Status"]) else "Not started",
                            "assignee": row["Assignee"] if pd.notna(row["Assignee"]) else "",
                            "start_date": date_to_str(row.get("Start Date")),
                            "end_date": date_to_str(row.get("End Date")),
                            "notes": row["Notes"] if pd.notna(row["Notes"]) else "",
                        })

                # Merge edits back into the full item list
                if status_filter == "All":
                    active["checklist"][cat] = new_items
                else:
                    # Order-preserving merge: replace edited, skip deleted, keep others
                    edited_by_id = {}
                    for idx, it in enumerate(new_items):
                        if idx < len(filtered):
                            edited_by_id[filtered[idx]["id"]] = it

                    # IDs that were in filtered view but removed by user
                    deleted_ids = set()
                    for idx in range(len(filtered)):
                        if idx >= len(edited_df):
                            deleted_ids.add(filtered[idx]["id"])

                    # Truly new rows (added beyond original filtered set)
                    truly_new = new_items[len(filtered):]

                    # Rebuild in original order
                    rebuilt = []
                    for it in items:
                        if it["id"] in deleted_ids:
                            continue
                        elif it["id"] in edited_by_id:
                            rebuilt.append(edited_by_id[it["id"]])
                        else:
                            rebuilt.append(it)
                    rebuilt.extend(truly_new)
                    active["checklist"][cat] = rebuilt

                data_changed = True

    # Bulk actions (Apply / Delete selected) auto-save immediately
    if any_bulk_action:
        with st.spinner("Saving…"):
            save_client(active)
            refresh_clients()
        st.session_state[unsaved_key] = False
        st.toast("Saved!", icon="✅")
        st.rerun()

    # Inline edits accumulate in memory — show Save button
    if data_changed:
        st.session_state[unsaved_key] = True

    if st.session_state.get(unsaved_key):
        save_col1, save_col2 = st.columns([5, 1])
        with save_col1:
            st.info("You have unsaved changes in the checklist.")
        with save_col2:
            if st.button("💾 Save", type="primary", key="checklist_save_btn", use_container_width=True):
                with st.spinner("Saving…"):
                    save_client(active)
                    refresh_clients()
                st.session_state[unsaved_key] = False
                st.toast("Saved!", icon="✅")
                st.rerun()

with tab_ext:
    st.markdown("### 📅 Timeline (External)")
    st.caption("One bar per category — spans from earliest task start to latest task end")

    all_categories_ext = list(active.get("checklist", {}).keys())
    if all_categories_ext:
        col_fe1, col_fe2 = st.columns([3, 1])
        with col_fe1:
            sel_cats_ext = st.multiselect(
                "Filter by categories",
                options=all_categories_ext,
                default=all_categories_ext,
                key="ext_cat_filter",
                help="Select which categories to display",
            )
        with col_fe2:
            st.write("")
            if st.button("Select All", key="ext_select_all", use_container_width=True):
                st.rerun()
        ext_fig = create_external_timeline(active, selected_categories=sel_cats_ext if sel_cats_ext else None)
    else:
        ext_fig = create_external_timeline(active)

    if ext_fig is None:
        st.info("⏳ No tasks with date ranges yet. Add start and end dates to tasks in the Checklist tab to see them here.")
    else:
        st.plotly_chart(ext_fig, use_container_width=True)

with tab_int:
    st.markdown("### 🔍 Timeline (Internal)")
    st.caption("Detailed view — one bar per task, grouped by category")

    # Get all available categories from checklist
    all_categories = list(active.get("checklist", {}).keys())

    # Category filter
    if all_categories:
        col_filter1, col_filter2 = st.columns([3, 1])
        with col_filter1:
            selected_categories = st.multiselect(
                "Filter by categories",
                options=all_categories,
                default=all_categories,
                help="Select which categories to display on the timeline"
            )
        with col_filter2:
            st.write("")  # Spacer
            if st.button("Select All", key="int_select_all", use_container_width=True):
                st.rerun()

        # Create and display timeline chart with filtered categories
        timeline_fig = create_timeline_chart(active, selected_categories=selected_categories if selected_categories else None)
    else:
        # No categories available, show timeline without filter
        timeline_fig = create_timeline_chart(active)

    if timeline_fig is None:
        st.info("⏳ No tasks with date ranges yet. Add start and end dates to tasks in the Checklist tab to see them here.")
    else:
        st.plotly_chart(timeline_fig, use_container_width=True)

        # Timeline stats
        st.divider()
        col_t1, col_t2, col_t3 = st.columns(3)

        # Calculate timeline stats
        tasks_with_dates = 0
        earliest_start = None
        latest_end = None

        for cat, items in active["checklist"].items():
            for it in items:
                start = it.get("start_date", "")
                end = it.get("end_date", "")
                if start and end:
                    tasks_with_dates += 1
                    try:
                        start_dt = datetime.fromisoformat(start).date()
                        end_dt = datetime.fromisoformat(end).date()

                        if earliest_start is None or start_dt < earliest_start:
                            earliest_start = start_dt
                        if latest_end is None or end_dt > latest_end:
                            latest_end = end_dt
                    except (ValueError, TypeError):
                        continue

        with col_t1:
            st.metric("Tasks with Dates", f"{tasks_with_dates}/{stats['total']}")
        with col_t2:
            if earliest_start:
                st.metric("Timeline Start", earliest_start.strftime("%b %d, %Y"))
            else:
                st.metric("Timeline Start", "N/A")
        with col_t3:
            if latest_end:
                st.metric("Timeline End", latest_end.strftime("%b %d, %Y"))
                if active.get("go_live_date"):
                    try:
                        go_live_dt = date.fromisoformat(active["go_live_date"])
                        if latest_end > go_live_dt:
                            st.warning(f"⚠️ Timeline extends {(latest_end - go_live_dt).days} days beyond go-live date")
                    except ValueError:
                        pass
            else:
                st.metric("Timeline End", "N/A")


# ── Footer ──
st.divider()
st.caption("Jules Go-Live Tracker · CS Configuration Tool · Data stored in Supabase")

"""
Jules Go-Live Tracker
=====================
Streamlit app for CS team to track client onboarding checklists.

Usage:
  pip install streamlit pandas
  streamlit run app.py

Template: Edit golive_template.csv to change default checklist items.
"""

import streamlit as st
import pandas as pd
import json
import os
import uuid
from datetime import date, datetime
from pathlib import Path

# ─── Config ───
st.set_page_config(
    page_title="Jules Go-Live Tracker",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
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


# ─── Data Helpers ───

def load_template(csv_source=None):
    """Load checklist template from CSV.

    Args:
        csv_source: A file path (str/Path), a file-like object (from st.file_uploader),
                    or None to use the default template.
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

    template = {}
    for _, row in df.iterrows():
        cat = str(row["category"]).strip()
        if cat not in template:
            template[cat] = []
        template[cat].append({
            "item": str(row["item"]).strip(),
            "points": float(row.get("points", 1)),
            "default_assignee": str(row.get("default_assignee", "")).strip()
            if pd.notna(row.get("default_assignee")) else "",
        })
    return template


def create_client(name, tier, go_live_date, account_manager, tech_lead, template):
    """Create a new client dict from template."""
    checklist = {}
    for cat, items in template.items():
        checklist[cat] = []
        for it in items:
            checklist[cat].append({
                "id": str(uuid.uuid4())[:8],
                "item": it["item"],
                "points": it["points"],
                "status": "Not started",
                "assignee": it.get("default_assignee", ""),
                "notes": "",
            })

    return {
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "tier": tier,
        "go_live_date": str(go_live_date) if go_live_date else "",
        "account_manager": account_manager,
        "tech_lead": tech_lead,
        "created_at": datetime.now().isoformat(),
        "checklist": checklist,
    }


def save_client(client):
    """Save client data to JSON file."""
    path = DATA_DIR / f"{client['id']}.json"
    with open(path, "w") as f:
        json.dump(client, f, indent=2, default=str)


def load_all_clients():
    """Load all client JSON files."""
    clients = []
    for f in DATA_DIR.glob("*.json"):
        try:
            with open(f) as fh:
                clients.append(json.load(fh))
        except Exception:
            pass
    # Sort by creation date, newest first
    clients.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    return clients


def delete_client(client_id):
    """Delete a client JSON file. Returns True on success."""
    path = DATA_DIR / f"{client_id}.json"
    if path.exists():
        try:
            path.unlink()
            return True
        except OSError as e:
            st.error(f"Could not delete client file: {e}")
            return False
    return False


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


# ─── Initialize Session State ───

if "clients" not in st.session_state:
    st.session_state.clients = load_all_clients()

if "active_client_id" not in st.session_state:
    st.session_state.active_client_id = None

if "template" not in st.session_state:
    st.session_state.template = load_template()


def refresh_clients():
    st.session_state.clients = load_all_clients()


# ─── Sidebar ───

with st.sidebar:
    st.markdown("## 🚀 Go-Live Tracker")
    st.caption("Jules · CS Configuration")
    st.divider()

    # ── New Client ──
    with st.expander("➕ **New Client**", expanded=False):
        new_name = st.text_input("Client name", key="new_name")
        col1, col2 = st.columns(2)
        with col1:
            new_tier = st.selectbox("Tier", TIERS, key="new_tier")
        with col2:
            new_date = st.date_input("Go-Live date", value=None, key="new_date")
        new_am = st.text_input("Account Manager", key="new_am")
        new_tech = st.text_input("Tech Lead CS", key="new_tech")

        # Optional custom CSV
        custom_csv = st.file_uploader(
            "Custom template (optional)",
            type=["csv"],
            key="custom_csv",
            help="Upload a CSV to override the default template for this client only.",
        )

        if st.button("🚀 Create Client", use_container_width=True, type="primary"):
            if new_name.strip():
                # Check for duplicate name
                existing_names = [c["name"].lower() for c in st.session_state.clients]
                if new_name.strip().lower() in existing_names:
                    st.warning("A client with this name already exists.")
                # Use custom CSV if provided, otherwise default
                elif custom_csv is not None:
                    tpl = load_template(csv_source=custom_csv)
                else:
                    tpl = st.session_state.template

                if tpl:
                    client = create_client(new_name.strip(), new_tier, new_date, new_am, new_tech, tpl)
                    save_client(client)
                    refresh_clients()
                    st.session_state.active_client_id = client["id"]
                    st.rerun()
                else:
                    st.error("No valid template loaded.")
            else:
                st.warning("Enter a client name.")

    st.divider()

    # ── Template Management ──
    with st.expander("📋 **Template**", expanded=False):
        st.caption("Download or replace the default template")

        if TEMPLATE_PATH.exists():
            with open(TEMPLATE_PATH, "rb") as f:
                st.download_button(
                    "⬇️ Download current template",
                    f.read(),
                    file_name="golive_template.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

        new_tpl = st.file_uploader("Upload new default template", type=["csv"], key="new_tpl")
        if new_tpl is not None:
            if st.button("💾 Save as default", use_container_width=True):
                with open(TEMPLATE_PATH, "wb") as f:
                    f.write(new_tpl.getvalue())
                st.session_state.template = load_template()
                st.success("Template updated!")
                st.rerun()

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
                    st.rerun()
            with col_pct:
                color = "🟢" if stats["pct"] == 100 else "🟡" if stats["pct"] > 50 else "🔴"
                st.markdown(f"<div style='text-align:center;padding-top:8px;font-size:13px;'>{color} {stats['pct']}%</div>", unsafe_allow_html=True)

            # Mini progress bar
            st.progress(stats["pct"] / 100)


# ─── Main Content ───

# Find active client
active = None
if st.session_state.active_client_id:
    for c in st.session_state.clients:
        if c["id"] == st.session_state.active_client_id:
            active = c
            break

if active is None:
    st.markdown("""
    <div style="text-align:center; padding: 120px 20px; color: #444;">
        <div style="font-size: 64px; margin-bottom: 16px;">🚀</div>
        <div style="font-size: 20px; font-weight: 600; color: #888; margin-bottom: 8px;">
            Jules Go-Live Tracker
        </div>
        <div style="font-size: 14px;">
            Select a client from the sidebar or create a new one to get started.
        </div>
    </div>
    """, unsafe_allow_html=True)
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
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        new_val = st.selectbox("Tier", TIERS, index=TIERS.index(active.get("tier", "Tier 1")), key="edit_tier")
        if new_val != active.get("tier"):
            active["tier"] = new_val
            save_client(active)
    with col2:
        new_val = st.text_input("Account Manager", value=active.get("account_manager", ""), key="edit_am")
        if new_val != active.get("account_manager"):
            active["account_manager"] = new_val
            save_client(active)
    with col3:
        new_val = st.text_input("Tech Lead CS", value=active.get("tech_lead", ""), key="edit_tech")
        if new_val != active.get("tech_lead"):
            active["tech_lead"] = new_val
            save_client(active)
    with col4:
        go_live = active.get("go_live_date", "")
        try:
            default_date = date.fromisoformat(go_live) if go_live else None
        except ValueError:
            default_date = None
        new_val = st.date_input("Go-Live Date", value=default_date, key="edit_date")
        if str(new_val) != go_live:
            active["go_live_date"] = str(new_val) if new_val else ""
            save_client(active)


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
}

data_changed = False

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
            df_data.append({
                "✓": it["status"] in ("Approved", "N/A"),
                "Item": it["item"],
                "Status": it["status"],
                "Assignee": it.get("assignee", ""),
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
                "✓": st.column_config.CheckboxColumn("✓", width="small"),
                "Item": st.column_config.TextColumn("Item", width="large"),
                "Status": st.column_config.SelectboxColumn(
                    "Status", options=STATUSES, width="medium",
                ),
                "Assignee": st.column_config.TextColumn("Assignee", width="medium"),
                "Points": st.column_config.NumberColumn("Pts", width="small", format="%.1f"),
                "Notes": st.column_config.TextColumn("Notes", width="large"),
            },
            num_rows="dynamic",  # Allows adding/deleting rows
        )

        # Sync edits back (use string comparison to avoid dtype mismatch false positives)
        original_df = df.drop(columns=["_id"]).reset_index(drop=True)
        edited_compare = edited_df.reset_index(drop=True)
        has_changes = (
            len(edited_compare) != len(original_df)
            or not edited_compare.astype(str).equals(original_df.astype(str))
        )
        if has_changes:
            new_items = []
            for idx, row in edited_df.iterrows():
                if idx < len(filtered):
                    # Existing item
                    it = filtered[idx].copy()
                    it["item"] = row["Item"]
                    it["points"] = row["Points"]
                    it["assignee"] = row["Assignee"]
                    it["notes"] = row["Notes"]
                    # Checkbox overrides status
                    if row["✓"] and it["status"] not in ("Approved", "N/A"):
                        it["status"] = "Approved"
                    elif not row["✓"] and it["status"] in ("Approved", "N/A"):
                        it["status"] = "Not started"
                    else:
                        it["status"] = row["Status"]
                    new_items.append(it)
                else:
                    # New row added
                    new_items.append({
                        "id": str(uuid.uuid4())[:8],
                        "item": row["Item"] if pd.notna(row["Item"]) else "New item",
                        "points": row["Points"] if pd.notna(row["Points"]) else 1,
                        "status": row["Status"] if pd.notna(row["Status"]) else "Not started",
                        "assignee": row["Assignee"] if pd.notna(row["Assignee"]) else "",
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

# Auto-save on any change
if data_changed:
    save_client(active)
    refresh_clients()


# ── Footer ──
st.divider()
st.caption("Jules Go-Live Tracker · CS Configuration Tool · Data stored locally in `data/` folder")

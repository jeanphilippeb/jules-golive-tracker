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

        template[cat].append({
            "item": str(row["item"]).strip(),
            "points": float(row.get("points", 1)),
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

    # Define category colors
    category_colors = {
        "Master Data": "#FF6B6B",
        "Master Data Setup": "#4ECDC4",
        "Dashboard Setup": "#45B7D1",
        "Transaction Migration": "#FFA07A",
        "External Emails": "#98D8C8",
        "Internal Emails": "#6C5CE7",
        "Views": "#A8E6CF",
        "Permissions & Access": "#FFD93D",
        "Integrations": "#6BCF7F",
        "Documents": "#95A5A6",
        "Notifications (Knock)": "#F4A460",
    }

    # Category icons
    category_icons = {
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

    # Define category order (for y-axis grouping)
    category_order = [
        "Master Data",
        "Master Data Setup",
        "Dashboard Setup",
        "Transaction Migration",
        "External Emails",
        "Internal Emails",
        "Views",
        "Permissions & Access",
        "Integrations",
        "Documents",
        "Notifications (Knock)",
    ]

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
                    "Icon": category_icons.get(cat, "📋"),
                })
            except (ValueError, TypeError):
                continue

    if not tasks_data:
        return None

    df = pd.DataFrame(tasks_data)

    # Sort by category order, then by start date within each category
    df["CategoryOrder"] = df["Category"].map(lambda x: category_order.index(x) if x in category_order else 999)
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
            y_tick_labels.append(f"{category_icons.get(current_category, '📋')} {current_category}")

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
            fillcolor=category_colors.get(cat, "#95A5A6"),
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
            fillcolor=category_colors.get(row["Category"], "#95A5A6"),
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


# ─── Initialize Session State ───

if "clients" not in st.session_state:
    st.session_state.clients = load_all_clients()

if "active_client_id" not in st.session_state:
    st.session_state.active_client_id = None

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

    # ── New Client ──
    with st.expander("➕ **New Client**", expanded=False):
        new_name = st.text_input("Client name", key="new_name")
        col1, col2 = st.columns(2)
        with col1:
            new_tier = st.selectbox("Tier", TIERS, key="new_tier")
        with col2:
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
                        save_client(client)
                        refresh_clients()
                        st.session_state.active_client_id = client["id"]
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
    col1, col2 = st.columns(2)
    with col1:
        new_val = st.selectbox("Tier", TIERS, index=TIERS.index(active.get("tier", "Tier 1")), key="edit_tier")
        if new_val != active.get("tier"):
            active["tier"] = new_val
            save_client(active)
    with col2:
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
tab_checklist, tab_timeline = st.tabs(["📋 Checklist", "📅 Timeline"])

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
    }

    # Collect all assignee options for SelectboxColumn
    all_assignees = get_all_assignees(active)

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

                    # Helper to normalize dates for comparison
                    def date_to_str(val):
                        if pd.isna(val) or val is None:
                            return ""
                        if isinstance(val, str):
                            return val
                        if hasattr(val, 'isoformat'):
                            return val.isoformat()
                        return str(val)

                    # Compare each field
                    if (original["item"] != str(row["Item"]) or
                        original["points"] != float(row["Points"]) or
                        original.get("assignee", "") != str(row["Assignee"] if pd.notna(row["Assignee"]) else "") or
                        original.get("notes", "") != str(row["Notes"] if pd.notna(row["Notes"]) else "") or
                        original["status"] != str(row["Status"]) or
                        original.get("start_date", "") != date_to_str(row.get("Start Date")) or
                        original.get("end_date", "") != date_to_str(row.get("End Date"))):
                        has_changes = True
                        break

            if has_changes:
                new_items = []
                for idx, row in edited_df.iterrows():
                    if idx < len(filtered):
                        # Existing item
                        it = filtered[idx].copy()
                        it["item"] = row["Item"]
                        it["points"] = row["Points"]
                        it["assignee"] = row["Assignee"] if pd.notna(row["Assignee"]) else ""
                        it["notes"] = row["Notes"] if pd.notna(row["Notes"]) else ""
                        # Sync start_date and end_date
                        start_val = row.get("Start Date")
                        end_val = row.get("End Date")
                        it["start_date"] = str(start_val) if pd.notna(start_val) and start_val is not None else ""
                        it["end_date"] = str(end_val) if pd.notna(end_val) and end_val is not None else ""
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
                        start_val = row.get("Start Date")
                        end_val = row.get("End Date")
                        new_items.append({
                            "id": str(uuid.uuid4())[:8],
                            "item": row["Item"] if pd.notna(row["Item"]) else "New item",
                            "points": row["Points"] if pd.notna(row["Points"]) else 1,
                            "status": row["Status"] if pd.notna(row["Status"]) else "Not started",
                            "assignee": row["Assignee"] if pd.notna(row["Assignee"]) else "",
                            "start_date": str(start_val) if pd.notna(start_val) and start_val is not None else "",
                            "end_date": str(end_val) if pd.notna(end_val) and end_val is not None else "",
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

with tab_timeline:
    st.markdown("### 📅 Go-Live Timeline")
    st.caption("Visual timeline of all tasks grouped by category with date ranges")

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
            if st.button("Select All", use_container_width=True):
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

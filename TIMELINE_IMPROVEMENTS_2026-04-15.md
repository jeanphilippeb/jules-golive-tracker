# Go-Live Tracker Timeline Improvements

**Date:** 2026-04-15
**Summary:** Enhanced date range functionality and Gantt chart visualization

---

## Changes Made

### 1. ✅ Template CSV - Date Offset Columns

**File:** `golive_template.csv`

**Added columns:**
- `start_offset_days` - Days before go-live when task should start
- `end_offset_days` - Days before go-live when task should end

**How it works:**
- All tasks now have suggested timeline offsets (e.g., Master Data starts 56 days before go-live)
- When creating a new client WITH a go-live date, actual dates are automatically calculated
- When creating a client WITHOUT a go-live date, dates remain empty (can be filled manually)

**Example Timeline (8-week / 56-day project):**

| Category | Typical Timeline | Start Offset | End Offset |
|----------|-----------------|--------------|------------|
| Master Data | Weeks 1-2 | 56 days | 42-55 days |
| Master Data Setup | Weeks 3-4 | 42-49 days | 32-45 days |
| Dashboard Setup | Weeks 3-4 | 42 days | 33-40 days |
| Transaction Migration | Weeks 2-5 | 44-49 days | 35-47 days |
| External/Internal Emails | Weeks 5-6 | 35 days | 28 days |
| Views | Weeks 6-7 | 28 days | 21 days |
| Permissions & Access | Weeks 7-8 | 14-21 days | 10-19 days |
| Integrations | Weeks 1-8 (long) | 56 days | 14 days |
| Documents | Weeks 6-8 | 28 days | 10-14 days |
| Notifications | Weeks 7-8 | 12-14 days | 7-12 days |

### 2. ✅ Template Loading Logic

**File:** `app.py` (lines 177-187)

**Changes:**
- Updated `load_template()` function to read `start_offset_days` and `end_offset_days` columns
- Converts offset values to integers, handles missing/empty values gracefully
- Stores offsets in template data structure

**Code:**
```python
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
```

### 3. ✅ Client Creation - Auto Date Calculation

**File:** `app.py` (lines 208-227)

**Changes:**
- Updated `create_client()` function to calculate actual dates from offsets
- Only calculates dates if:
  1. A go-live date is provided
  2. The task has both start and end offset values
- Uses `timedelta` to subtract offset days from go-live date

**Code:**
```python
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
```

**Example:**
- Go-live date: `2026-06-30`
- Task: "Countries" with `start_offset_days=56`, `end_offset_days=54`
- Calculated dates:
  - Start: `2026-05-05` (June 30 - 56 days)
  - End: `2026-05-07` (June 30 - 54 days)

### 4. ✅ Enhanced Gantt Chart Visualization

**File:** `app.py` (lines 395-556, replacing old `create_timeline_chart` function)

**New Features:**

#### 4.1 Better Task Organization
- Tasks grouped by category with visual gaps between groups
- Categories appear in logical order (Master Data → Setup → Migration → etc.)
- Truncated task names for better readability (max 50 chars on y-axis)

#### 4.2 Today Marker
```python
fig.add_vline(
    x=today.isoformat(),
    line_dash="dash",
    line_color="cyan",
    line_width=2,
    annotation_text="Today",
    annotation_position="top",
)
```
- Cyan dashed line showing current date
- Helps visualize where project stands

#### 4.3 Go-Live Date Marker
```python
fig.add_vline(
    x=go_live_dt.isoformat(),
    line_dash="solid",
    line_color="#e8d44d",
    line_width=3,
    annotation_text="Go-Live",
    annotation_position="top",
)
```
- Yellow solid line showing target go-live date
- Only appears if client has go-live date set

#### 4.4 Category Legend
- Shows all categories with their colors
- Located on the right side of chart
- Grouped by category name
- Semi-transparent background for better visibility

#### 4.5 Enhanced Hover Tooltips
Now shows:
- Task name (bold)
- Category
- Status (with emoji)
- Assignee
- Points
- **Duration in days** (new!)
- Start date (formatted: "Jan 15, 2026")
- End date (formatted: "Jan 20, 2026")

#### 4.6 Better Layout
- Increased left margin (300px) for longer task names
- Increased right margin (200px) for legend
- Centered title with larger font
- Automatic height scaling based on number of tasks
- Smaller gaps between tasks in same category (0.2 vs 0.3)

#### 4.7 Visual Improvements
- Category gaps for better visual separation
- Numbered y-positions for precise alignment
- Improved grid styling
- Better color contrast on bars

---

## Usage Guide

### For New Clients

1. **With Go-Live Date:**
   - Create client and set go-live date
   - All tasks automatically get start/end dates based on template offsets
   - Dates appear immediately in Checklist and Timeline tabs

2. **Without Go-Live Date:**
   - Create client without setting go-live date
   - Tasks have empty date fields
   - Manually add dates in Checklist tab as needed
   - Or set go-live date later and manually calculate dates

### Editing Dates

- All dates remain editable in the Checklist tab
- Changes auto-save to Supabase
- Timeline updates immediately on refresh

### Timeline View

**Navigate to Timeline tab to see:**
- ✅ All tasks with dates as horizontal bars
- ✅ Color-coded by category
- ✅ "Today" marker (cyan dashed line)
- ✅ "Go-Live" marker (yellow solid line)
- ✅ Category legend on the right
- ✅ Detailed hover information
- ✅ Visual gaps between category groups

**Timeline Stats (bottom of Timeline tab):**
- Tasks with Dates: `X/Y` tasks scheduled
- Timeline Start: Earliest start date
- Timeline End: Latest end date
- Warning if timeline extends beyond go-live date

---

## Technical Details

### Data Flow

```
golive_template.csv (start_offset_days, end_offset_days)
          ↓
   load_template() → template dict with offsets
          ↓
   create_client(go_live_date) → calculate actual dates
          ↓
   Task items with start_date, end_date
          ↓
   create_timeline_chart() → Plotly Gantt chart
```

### Date Calculation Formula

```python
start_date = go_live_date - timedelta(days=start_offset_days)
end_date = go_live_date - timedelta(days=end_offset_days)
```

**Example:**
```
Go-live: 2026-08-01
Task: "Contacts"
  - start_offset_days: 56
  - end_offset_days: 48

Calculated:
  - start_date: 2026-08-01 - 56 days = 2026-06-06
  - end_date: 2026-08-01 - 48 days = 2026-06-14
  - Duration: 8 days
```

### Dependencies

No new dependencies added! Uses existing Plotly library.

---

## Testing Checklist

- [x] Syntax validation passes
- [ ] Create new client WITH go-live date → dates auto-populate
- [ ] Create new client WITHOUT go-live date → dates remain empty
- [ ] Edit dates in Checklist tab → changes save
- [ ] Timeline view shows all tasks with dates
- [ ] Timeline view shows "Today" marker
- [ ] Timeline view shows "Go-Live" marker
- [ ] Timeline legend displays correctly
- [ ] Hover tooltips show all information
- [ ] Category gaps appear correctly
- [ ] Export CSV includes start_date and end_date

---

## Backward Compatibility

✅ **Fully backward compatible!**

- Existing clients without dates continue to work
- Template CSV with empty/missing offset columns works fine
- Migration function from previous update still works
- Old `due_date` fields automatically convert to `end_date`

---

## Future Enhancements

Potential improvements for next iteration:

1. **Dependency Management**
   - Add `depends_on` field to tasks
   - Show dependency arrows on timeline
   - Auto-adjust dates based on dependencies

2. **Critical Path Analysis**
   - Highlight critical path tasks in red
   - Calculate project critical path
   - Show slack time for non-critical tasks

3. **Resource Leveling**
   - View timeline grouped by assignee
   - Detect resource conflicts
   - Suggest task redistribution

4. **Baseline Comparison**
   - Save original timeline as baseline
   - Compare actual vs planned
   - Show variance metrics

5. **Drag-to-Reschedule**
   - Interactive timeline editing
   - Drag bars to change dates
   - Auto-save changes

6. **Template Variants**
   - Different templates for different project sizes
   - 4-week, 8-week, 12-week variants
   - Tier-specific templates

---

## Support

For questions or issues:
- Check app logs in Streamlit console
- Verify CSV format matches expected columns
- Ensure dates are in ISO format (YYYY-MM-DD)
- Contact development team if issues persist

---

**Version:** 2.1.0 (Enhanced Timeline & Auto-Dating)
**Author:** Claude Code
**Last Updated:** 2026-04-15

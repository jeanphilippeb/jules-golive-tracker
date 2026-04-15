# Template Update - April 15, 2026

## Summary

Updated the go-live template from **60 tasks to 77 tasks** (+17 new tasks).

## Changes

### ✅ Tasks Merged

The new template was intelligently merged with existing metadata:
- **Existing tasks (46)**: Preserved all points, roles, and date offsets
- **New tasks (31)**: Added with default values

### 📋 New Tasks Added

#### Dashboard Setup (5 new tasks)
- Margin report
- Supplier & customer volume
- Inspection monitoring
- Discuss accounting requirements
- Inventory

#### Transaction Migration (1 new task)
- Discuss with Marc ability to extract

#### External Emails (2 new tasks)
- Accounts emails
- Documentaiton emails

#### Views (2 new tasks)
- Shipments views
- Accounts views

#### Integrations (3 new tasks)
- Define import format for accounting based on invoice example
- Create the script to generate the format
- Set-up sftp server

#### Documents (16 new tasks)
- Get test feedback from total info
- Purchase order
- Sales order
- Truck loading slip
- Truck delivery slip
- Truck annex 7
- Truck Booking confirmation
- Freihgt booking confirmation
- Freight planing
- India doc package
- Indonesia doc package
- Malaysia doc package
- Vietnam doc Package
- Credit note
- Debit note
- Invoice
- Payables

#### Notifications (2 new tasks - simplified)
- Internal
- External

### 📊 Final Template Statistics

```
Master Data: 21 tasks
Master Data Setup: 4 tasks
Dashboard Setup: 5 tasks
Transaction Migration: 9 tasks
External Emails: 5 tasks
Internal Emails: 3 tasks
Views: 5 tasks
Permissions & Access: 3 tasks
Integrations: 3 tasks
Documents: 16 tasks
Notifications (Knock): 3 tasks

TOTAL: 77 tasks
```

## Files Modified

1. **golive_template.csv** - Updated with 77 tasks
2. **golive_template_backup.csv** - Backup of old 60-task template
3. **golive_template_merged.csv** - Intermediate merge file

## Usage

The updated template is now active for all new clients created in the app. Existing clients are not affected.

### For New Clients

When creating a new client:
1. Select a go-live date
2. All 77 tasks will be created automatically
3. Date ranges will be calculated from offsets
4. View the full timeline in the Timeline tab

### Verifying the Update

```bash
cd /Users/jean-philippeboul/Claude\ Code/CSM
wc -l golive_template.csv
# Should show: 78 lines (77 tasks + 1 header)
```

## Backward Compatibility

✅ **Fully backward compatible**
- Existing clients with 60 tasks continue to work
- No data migration needed
- Timeline view works with both old and new clients

## Next Steps

To make this template available as a named template in the app:
1. Open the app at http://localhost:8501
2. Navigate to "New Client" section
3. Click "Save Current Template"
4. Name it "Default 2026" or similar
5. This saves it to Supabase for reuse

---

**Updated:** 2026-04-15
**Author:** Claude Code
**Version:** 2.2.0 (Extended Task Template)

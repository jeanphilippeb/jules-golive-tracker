# 🚀 Jules Go-Live Tracker

Checklist tool for the CS team to track client onboarding configuration.

## Quick Start (local)

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud (free)

1. Push this folder to a GitHub repo (public or private)
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set `app.py` as the main file
5. Deploy → you get a public URL

> ⚠️ On Streamlit Cloud, the `data/` folder resets on redeploy.
> For persistent data across deploys, switch to a Google Sheet or Supabase backend.
> For your use case (3-4 months per client), local JSON files work fine.

## How it works

### Template (CSV)

The default checklist is defined in `golive_template.csv`:

```csv
category,item,points,default_assignee
Master Data,Countries,1,Joel
Master Data,Contacts,8,Joel
External Emails,Purchase Emails,2.5,
...
```

**To modify the template:**
1. Download it from the app sidebar (📋 Template section)
2. Edit in Excel / Google Sheets
3. Re-upload via the app or replace the file in the repo

**Columns:**
- `category` — Group name (becomes an expandable section)
- `item` — Checklist item description
- `points` — Effort weight (for progress tracking)
- `default_assignee` — (optional) Pre-fill the assignee field

### Per-client custom template

When creating a new client, you can upload a **custom CSV** that overrides the default template for that specific client only.

### Data

Each client is saved as a JSON file in `data/`. To archive a completed client, just delete them from the app or remove the JSON file.

## File structure

```
├── app.py                  # Streamlit app
├── golive_template.csv     # Default checklist template (edit this!)
├── requirements.txt        # Python dependencies
├── data/                   # Client data (auto-created)
│   ├── abc123.json
│   └── def456.json
└── README.md
```

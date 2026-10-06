# 🏛️ Rangrag Archviz Studio — Outreach CRM & Dispatcher

A local full-stack SaaS CRM and automated outreach engine built for **Rangrag Archviz Studio** (founded by **Raj Shekhada**, specializing in high-end 3D architectural visualization, Chaos V-Ray, Corona, and D5 rendering).

- **Online Portfolio**: [https://rangragstudio.myportfolio.com/](https://rangragstudio.myportfolio.com/)
- **Instagram**: [@rangrag_studio](https://www.instagram.com/rangrag_studio/)
- **LinkedIn**: [Raj Shekhada](https://www.linkedin.com/in/raj-shekhada/)

---

## ⚡ Quick Start

### 1. Requirements
- Python 3.10+ (Tested on Python 3.14)
- Web Browser (Chrome, Edge, Firefox, Brave)

### 2. Launch the Application
Run the one-click startup runner:
```bash
python run.py
```
Or with `uvicorn`:
```bash
uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Open your browser to:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 🧩 Architectural Overview & Modules

```
f:\mail_system\
├── backend/
│   ├── app.py               # FastAPI application & REST endpoints
│   ├── models.py            # SQLite schema via SQLAlchemy ORM (leads, email_threads, campaign_logs, settings)
│   ├── csv_service.py       # Data cleaning, multi-email parsing, and fresh export
│   ├── gemini_service.py    # Google GenAI SDK (gemini-2.5-flash) dynamic peer-to-peer generator
│   ├── email_service.py     # Outbound SMTP dispatcher (random delays), IMAP reply scanner, auto follow-ups
│   └── templates.py         # Visual HTML & plaintext email templates with live portfolio CTAs
├── static/
│   ├── index.html           # Notion/Linear dark-mode SaaS UI
│   ├── css/style.css        # Premium design tokens, glassmorphism, responsive styles
│   └── js/app.js            # Frontend state controller, real-time polling, and modals
├── data/
│   ├── rangrag_crm.db       # SQLite local database
│   ├── fresh_architects_outreach_data.csv # Automatically generated clean dataset
│   └── sample_architects_raw.csv          # Sample dataset with intentional anomalies for testing
├── run.py                   # One-click startup script
├── test_system.py           # End-to-end verification test suite
└── requirements.txt         # Dependencies
```

---

## 🛠️ Feature Walkthrough

### Module A: Domain Mail Configuration & Live Handshake
- **Settings UI**: Configure custom domain SMTP and IMAP servers, ports, authentication credentials, and TLS/SSL toggles.
- **Handshake Diagnostics**: Real-time handshake test (`POST /api/settings/domain`) verifies connectivity to SMTP (250 OK) and IMAP (INBOX OK) before any campaigns run.
- **Zero-Risk Simulation Mode**: Enabled by default to allow testing the entire application without sending real emails or risking domain reputation.

### Module B: CSV Data Upload, Cleaning & Fresh Export
- **Dropzone**: Upload raw architect or interior designer CSV/Excel files.
- **Validation Pipeline**:
  - Drops rows with missing or dummy firm names.
  - Parses multi-email entries (e.g., `info@firm.com; contact@firm.com`) down to the primary clean address.
  - Strips spaces, normalizes syntax, and validates RFC compliant domains.
  - Formats phone numbers with country codes (e.g., `+91`).
  - Deduplicates by email and firm.
- **One-Click Export**: Automatically writes and offers download of `fresh_architects_outreach_data.csv`.

### Module C: AI Gemini Email Generator (Google GenAI)
- **Engine**: Powered by Google GenAI (`gemini-2.5-flash`).
- **Prompt Architecture**: Dynamically injects `{firm_name}`, `{city}`, and `{category}` to frame the outreach as a peer-to-peer partnership between 3D artist and architect.
- **Core Pillars Highlighted**:
  - 🏛️ Photorealistic 3D Renders (Chaos V-Ray, Corona, D5)
  - 🛋️ Luxury Interior Visualization & Material Styling
  - 🎬 Cinematic Architectural Walkthrough Animations
  - 🌐 360° Interactive Panoramas & VR Virtual Tours
- **Executive Signature**: Appends Raj Shekhada's official signature with live links to his portfolio, Instagram, and LinkedIn.

### Module D: Kanban Review Queue, Daily Limits & Randomized Sending
- **Kanban Board**: 4 real-time columns:
  1. `Pending AI`: Raw leads awaiting draft generation.
  2. `Ready to Review`: Drafts ready for inline inspection and editing.
  3. `Dispatched`: Successfully sent emails with delivery tracking.
  4. `Hot Leads (WhatsApp)`: Interested responses flagged for direct conversion.
- **Domain Reputation Protection**:
  - **Adjustable Daily Send Limit**: Slider from 10 to 50 emails/day.
  - **Randomized Jitter Delays**: Configurable sleep between sends (e.g., 30s to 60s) to emulate human sending patterns.
  - Real-time dispatcher banner with live countdown ticker and pause/resume/stop controls.

### Module E: IMAP Reply Monitoring & Automated Follow-ups
- **IMAP Scanner**: Scans domain inbox, matches sender against active leads, and categorizes replies:
  - `Interested`: High intent inquiries (portfolio requests, pricing questions).
  - `Not Interested`: Unsubscribe requests.
  - `Bounce`: Delivery failure notifications.
- **Automated Follow-ups**: Automatically triggers gentle follow-up drafts for leads dispatched >= 3 to 4 days ago with no response.

### Module F: Instant WhatsApp Handoff for Hot Leads
- When an architect replies showing interest, they are flagged as a **Hot Lead**.
- A high-visibility emerald green button generates an instant link to WhatsApp Web/Desktop:
  ```
  https://wa.me/[phone]?text=[pre-filled closing message with portfolio link]
  ```
- Tracks WhatsApp conversions directly in analytics.

### Module G: Live Analytics & Dashboard
- Visual metric cards for:
  - Total Clean Leads
  - Daily Quota Status
  - Emails Sent Today
  - Ready to Send
  - Deliverability / Bounce Rates
  - Reply Rates
  - Hot WhatsApp Leads Converted
- Real-time pipeline funnel and campaign audit log.

---

## 🧪 Testing the Pipeline
To run the automated test suite verifying all 6 modules:
```bash
python test_system.py
```
All tests should return `[OK]`.

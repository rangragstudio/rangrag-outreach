"""
Production FastAPI Application for Rangrag Archviz Studio CRM.
Exposes full RESTful API conforming to technical specifications:
- MODULE A: Domain Mail Configuration & Handshake Testing (/api/settings/domain)
- MODULE B: CSV Data Upload, Cleaning & Fresh Export (/api/upload-csv)
- MODULE C: AI Gemini Email Content Generator (/api/generate-drafts)
- MODULE D: Kanban Review Queue, Daily Limits & Randomized Sending (/api/campaign/send)
- MODULE E: IMAP Reply Monitoring & Automated Follow-ups (/api/campaign/monitor & /api/campaign/followup)
- MODULE F: Instant WhatsApp Handoff for Hot Leads (/api/leads/{id}/whatsapp-handoff)
- MODULE G: Live Analytics & Dashboard Metrics (/api/analytics)
"""

import os
import urllib.parse
from datetime import datetime, timezone, date
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.models import (
    init_database, get_db, Lead, EmailThread, CampaignLog, Setting, get_utc_now
)
from backend.csv_service import process_and_clean_csv
from backend.gemini_service import (
    create_lead_draft, batch_create_drafts, generate_ai_partnership_email
)
from backend.email_service import (
    test_domain_handshake,
    dispatch_engine,
    scan_imap_inbox,
    trigger_followup_scanner,
    get_setting_value,
    set_setting_value,
    log_campaign_event,
    classify_sentiment
)
from backend.templates import render_html_email, render_plain_text_email

app = FastAPI(
    title="Rangrag Archviz Studio CRM",
    description="SaaS Outreach & Partnership Engine for Raj Shekhada",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_database()

# ----------------- PYDANTIC REQUEST SCHEMAS -----------------

class DomainConfigRequest(BaseModel):
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_email: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    sender_name: str = "Raj Shekhada | Rangrag Archviz Studio"
    imap_server: str = "imap.gmail.com"
    imap_port: int = 993
    imap_email: str = ""
    imap_password: str = ""
    imap_use_ssl: bool = True
    simulation_mode: bool = True
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash"
    daily_send_limit: int = 40
    min_delay_seconds: int = 30
    max_delay_seconds: int = 60
    follow_up_days: int = 3
    raj_whatsapp_number: str = "+919876543210"

class GenerateDraftsRequest(BaseModel):
    lead_id: Optional[int] = None
    limit: int = 50

class ThreadEditRequest(BaseModel):
    subject: str
    body_text: str
    body_html: Optional[str] = None

class BatchApproveRequest(BaseModel):
    thread_ids: Optional[List[int]] = None
    all_drafts: bool = False

class SimulateReplyRequest(BaseModel):
    lead_id: int
    sentiment: str = "Interested"  # 'Interested', 'Not Interested', 'Neutral', 'Bounce'
    sample_text: Optional[str] = None

# ----------------- MODULE A: DOMAIN CONFIG & HANDSHAKE -----------------

@app.get("/api/settings")
def get_all_settings(db: Session = Depends(get_db)):
    settings_items = db.query(Setting).all()
    res = {s.key: s.value for s in settings_items}
    # Mask passwords
    if res.get("smtp_password"):
        res["smtp_password_masked"] = "••••••••"
    if res.get("imap_password"):
        res["imap_password_masked"] = "••••••••"
    if res.get("gemini_api_key"):
        raw = res["gemini_api_key"]
        res["gemini_api_key_masked"] = raw[:4] + "••••" + raw[-4:] if len(raw) > 8 else "••••••••"
    return res

@app.post("/api/settings/domain")
def configure_and_test_domain(payload: DomainConfigRequest, db: Session = Depends(get_db)):
    """
    Saves domain configuration and runs live handshake test for SMTP and IMAP.
    """
    # Preserve existing password if user sends masked value
    existing_smtp_pass = get_setting_value(db, "smtp_password", "")
    smtp_pass = payload.smtp_password if payload.smtp_password and "••" not in payload.smtp_password else existing_smtp_pass

    existing_imap_pass = get_setting_value(db, "imap_password", "")
    imap_pass = payload.imap_password if payload.imap_password and "••" not in payload.imap_password else existing_imap_pass

    existing_gemini_key = get_setting_value(db, "gemini_api_key", "")
    gemini_key = payload.gemini_api_key if payload.gemini_api_key and "••" not in payload.gemini_api_key else existing_gemini_key

    # Save to database
    set_setting_value(db, "smtp_server", payload.smtp_server)
    set_setting_value(db, "smtp_port", str(payload.smtp_port))
    set_setting_value(db, "smtp_email", payload.smtp_email)
    set_setting_value(db, "smtp_password", smtp_pass)
    set_setting_value(db, "smtp_use_tls", "true" if payload.smtp_use_tls else "false")
    set_setting_value(db, "sender_name", payload.sender_name)

    set_setting_value(db, "imap_server", payload.imap_server)
    set_setting_value(db, "imap_port", str(payload.imap_port))
    set_setting_value(db, "imap_email", payload.imap_email)
    set_setting_value(db, "imap_password", imap_pass)
    set_setting_value(db, "imap_use_ssl", "true" if payload.imap_use_ssl else "false")

    set_setting_value(db, "simulation_mode", "true" if payload.simulation_mode else "false")
    set_setting_value(db, "gemini_api_key", gemini_key or "")
    set_setting_value(db, "gemini_model", payload.gemini_model)
    set_setting_value(db, "daily_send_limit", str(payload.daily_send_limit))
    set_setting_value(db, "min_delay_seconds", str(payload.min_delay_seconds))
    set_setting_value(db, "max_delay_seconds", str(payload.max_delay_seconds))
    set_setting_value(db, "follow_up_days", str(payload.follow_up_days))
    set_setting_value(db, "raj_whatsapp_number", payload.raj_whatsapp_number)

    # Perform handshake verification
    handshake_result = test_domain_handshake(
        smtp_server=payload.smtp_server,
        smtp_port=payload.smtp_port,
        smtp_email=payload.smtp_email,
        smtp_password=smtp_pass,
        smtp_use_tls=payload.smtp_use_tls,
        imap_server=payload.imap_server,
        imap_port=payload.imap_port,
        imap_email=payload.imap_email,
        imap_password=imap_pass,
        imap_use_ssl=payload.imap_use_ssl,
        simulation_mode=payload.simulation_mode
    )

    log_campaign_event(
        db,
        "settings",
        f"Domain Mail configured. Handshake: SMTP [{handshake_result.get('smtp_status')}] | IMAP [{handshake_result.get('imap_status')}]. Simulation Mode: {payload.simulation_mode}",
        status="success" if handshake_result.get("success") else "warning"
    )

    return handshake_result

# ----------------- MODULE B: CSV UPLOAD, CLEANING & FRESH EXPORT -----------------

@app.post("/api/upload-csv")
async def upload_and_clean_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")
    
    file_bytes = await file.read()
    result = process_and_clean_csv(file_bytes, file.filename, db)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result

@app.get("/api/download/fresh-csv")
def download_fresh_csv():
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    file_path = os.path.join(data_dir, "fresh_architects_outreach_data.csv")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="fresh_architects_outreach_data.csv has not been generated yet. Please upload a raw CSV.")
    return FileResponse(file_path, filename="fresh_architects_outreach_data.csv", media_type="text/csv")

@app.get("/api/download/sample-csv")
def download_sample_csv():
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    file_path = os.path.join(data_dir, "sample_architects_raw.csv")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Sample CSV not found.")
    return FileResponse(file_path, filename="sample_architects_raw.csv", media_type="text/csv")

# ----------------- MODULE C: AI GEMINI GENERATOR -----------------

@app.post("/api/generate-drafts")
def generate_drafts(payload: GenerateDraftsRequest, db: Session = Depends(get_db)):
    if payload.lead_id:
        res = create_lead_draft(db, payload.lead_id)
        if not res.get("success"):
            raise HTTPException(status_code=400, detail=res.get("error"))
        return res
    else:
        return batch_create_drafts(db, limit=payload.limit)

# ----------------- MODULE D: KANBAN REVIEW QUEUE & OUTBOUND DISPATCH -----------------

@app.get("/api/kanban")
def get_kanban_board(db: Session = Depends(get_db)):
    """
    Returns columns for Kanban Board:
    - Pending AI
    - Ready to Review (Drafted)
    - Dispatched (Sent)
    - Hot Leads (WhatsApp)
    """
    leads = db.query(Lead).order_by(Lead.id.desc()).all()
    
    col_pending_ai = []
    col_ready_review = []
    col_dispatched = []
    col_hot_leads = []

    for lead in leads:
        lead_data = lead.to_dict()
        latest_thread = db.query(EmailThread).filter(EmailThread.lead_id == lead.id).order_by(EmailThread.id.desc()).first()
        lead_data["latest_thread"] = latest_thread.to_dict() if latest_thread else None

        if lead.is_hot or lead.status == "Interested":
            col_hot_leads.append(lead_data)
        elif lead.status in ["Dispatched", "Not Interested", "No Reply", "Bounced"]:
            col_dispatched.append(lead_data)
        elif lead.status == "Ready to Review" or (latest_thread and latest_thread.status in ["draft", "approved"]):
            col_ready_review.append(lead_data)
        else:
            col_pending_ai.append(lead_data)

    return {
        "pending_ai": col_pending_ai,
        "ready_to_review": col_ready_review,
        "dispatched": col_dispatched,
        "hot_leads": col_hot_leads
    }

@app.put("/api/threads/{thread_id}")
def update_email_thread(thread_id: int, payload: ThreadEditRequest, db: Session = Depends(get_db)):
    thread = db.query(EmailThread).filter(EmailThread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Draft not found")

    thread.subject = payload.subject
    thread.body_text = payload.body_text
    if payload.body_html:
        thread.body_html = payload.body_html
    else:
        # Re-render HTML with updated body text
        lead_dict = thread.lead.to_dict() if thread.lead else {}
        thread.body_html = render_html_email(lead_dict, payload.body_text, subject=payload.subject)

    thread.updated_at = get_utc_now()
    db.commit()
    log_campaign_event(db, "edit", f"Edited subject/body for thread #{thread_id} ({thread.subject})", lead_id=thread.lead_id, status="info")
    return {"success": True, "message": "Email draft updated successfully", "thread": thread.to_dict()}

@app.post("/api/threads/{thread_id}/approve")
def approve_single_thread(thread_id: int, db: Session = Depends(get_db)):
    thread = db.query(EmailThread).filter(EmailThread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    thread.status = "approved"
    thread.updated_at = get_utc_now()
    db.commit()
    log_campaign_event(db, "approve", f"Approved email draft #{thread_id} for automated dispatch", lead_id=thread.lead_id, status="success")
    return {"success": True, "message": "Approved for dispatch"}

@app.post("/api/threads/batch-approve")
def batch_approve_threads(payload: BatchApproveRequest, db: Session = Depends(get_db)):
    now = get_utc_now()
    if payload.all_drafts:
        updated = db.query(EmailThread).filter(EmailThread.status == "draft").update({"status": "approved", "updated_at": now})
        db.commit()
        log_campaign_event(db, "approve", f"Batch approved all {updated} drafts for sending", status="success")
        return {"success": True, "approved_count": updated}
    elif payload.thread_ids:
        updated = db.query(EmailThread).filter(EmailThread.id.in_(payload.thread_ids)).update({"status": "approved", "updated_at": now}, synchronize_session=False)
        db.commit()
        log_campaign_event(db, "approve", f"Batch approved {updated} selected drafts for sending", status="success")
        return {"success": True, "approved_count": updated}
    return {"success": True, "approved_count": 0}

@app.post("/api/campaign/send")
async def start_campaign_send():
    """Starts the automated outbound dispatch engine with randomized human-like delays."""
    return await dispatch_engine.start()

@app.post("/api/campaign/pause")
def pause_campaign_send():
    return dispatch_engine.pause()

@app.post("/api/campaign/resume")
def resume_campaign_send():
    return dispatch_engine.resume()

@app.post("/api/campaign/stop")
def stop_campaign_send():
    return dispatch_engine.stop()

@app.get("/api/campaign/status")
def get_campaign_status():
    return dispatch_engine.get_status()

# ----------------- MODULE E: IMAP MONITORING & FOLLOW-UPS -----------------

@app.get("/api/campaign/monitor")
def monitor_inbox(db: Session = Depends(get_db)):
    """Scans the connected IMAP domain inbox for unread responses and categorizes sentiment."""
    return scan_imap_inbox(db)

@app.post("/api/campaign/followup")
def trigger_automated_followups(db: Session = Depends(get_db)):
    """Automatically drafts polite follow-up emails for leads with no response after 3-4 days."""
    return trigger_followup_scanner(db)

@app.post("/api/campaign/simulate-reply")
def simulate_incoming_reply(payload: SimulateReplyRequest, db: Session = Depends(get_db)):
    """Simulates an inbound email reply to verify categorization and Hot Lead tagging."""
    lead = db.query(Lead).filter(Lead.id == payload.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    now = get_utc_now()
    sample_text = payload.sample_text
    if not sample_text:
        if payload.sentiment == "Interested":
            sample_text = (
                f"Hi Raj, thanks for reaching out. We actually have an ongoing luxury residential project "
                f"in {lead.city or 'our city'} that needs high-end 3D exterior visualization and walkthrough animation. "
                f"Could you share your pricing and schedule a quick call? My WhatsApp number is {lead.mobile or '+91 98250 11223'}."
            )
        elif payload.sentiment == "Not Interested":
            sample_text = "Thank you, but we handle all rendering in-house. Please unsubscribe us."
        else:
            sample_text = "Received, we will keep your portfolio on file."

    is_interested = payload.sentiment == "Interested"
    lead.status = "Interested" if is_interested else ("Not Interested" if payload.sentiment == "Not Interested" else "No Reply")
    if is_interested:
        lead.is_hot = True

    thread = db.query(EmailThread).filter(EmailThread.lead_id == lead.id).order_by(EmailThread.id.desc()).first()
    if thread:
        thread.reply_detected_at = now
        thread.reply_sentiment = payload.sentiment
        thread.reply_content = sample_text

    db.commit()

    log_campaign_event(
        db,
        "reply",
        f"[SIMULATION] Reply simulated from {lead.firm_name}: '{payload.sentiment}'. {'🔥 FLAGGED AS HOT LEAD!' if is_interested else ''}",
        lead_id=lead.id,
        status="success" if is_interested else "info"
    )

    return {
        "success": True,
        "lead_id": lead.id,
        "firm_name": lead.firm_name,
        "sentiment": payload.sentiment,
        "is_hot": lead.is_hot,
        "reply_content": sample_text
    }

# ----------------- MODULE F: INSTANT WHATSAPP HANDOFF -----------------

@app.post("/api/leads/{lead_id}/whatsapp-handoff")
def initiate_whatsapp_handoff(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead.whatsapp_converted = True
    lead.updated_at = get_utc_now()
    db.commit()

    # Normalize mobile
    mobile = lead.mobile or ""
    clean_mobile = "".join([c for c in mobile if c.isdigit() or c == "+"])
    if clean_mobile.startswith("+"):
        clean_mobile = clean_mobile[1:]
    elif len(clean_mobile) == 10:
        clean_mobile = f"91{clean_mobile}"

    contact_name = lead.contact_name or lead.firm_name
    city_str = f" in {lead.city}" if lead.city else ""

    closing_message = (
        f"Hi {contact_name}, Raj Shekhada here from Rangrag Archviz Studio! "
        f"Following up on your email response regarding 3D architectural visualization{city_str}. "
        f"We'd love to share our quick lookbook and discuss your project timeline. "
        f"Here's our portfolio: https://rangragstudio.myportfolio.com/ — when is a convenient time for a quick 5-min call?"
    )

    encoded_msg = urllib.parse.quote(closing_message)
    whatsapp_url = f"https://wa.me/{clean_mobile}?text={encoded_msg}" if clean_mobile else f"https://web.whatsapp.com/send?text={encoded_msg}"

    log_campaign_event(
        db,
        "whatsapp_click",
        f"Raj Shekhada initiated instant WhatsApp handoff for {lead.firm_name} ({clean_mobile})",
        lead_id=lead.id,
        status="success"
    )

    return {
        "success": True,
        "whatsapp_url": whatsapp_url,
        "clean_mobile": clean_mobile,
        "closing_message": closing_message
    }

# ----------------- MODULE G: LIVE ANALYTICS & DASHBOARD METRICS -----------------

@app.get("/api/analytics")
def get_analytics(db: Session = Depends(get_db)):
    total_clean_leads = db.query(Lead).count()
    pending_ai = db.query(Lead).filter(Lead.status == "Pending AI").count()
    ready_to_send = db.query(EmailThread).filter(EmailThread.status == "approved").count()
    
    today_start = datetime.combine(date.today(), datetime.min.time())
    sent_today = db.query(EmailThread).filter(
        EmailThread.status == "sent",
        EmailThread.sent_at >= today_start
    ).count()

    total_sent = db.query(EmailThread).filter(EmailThread.status == "sent").count()
    total_replies = db.query(EmailThread).filter(EmailThread.reply_detected_at.is_not(None)).count()
    interested_count = db.query(EmailThread).filter(EmailThread.reply_sentiment == "Interested").count()
    bounces = db.query(EmailThread).filter(
        (EmailThread.status == "failed") | (EmailThread.reply_sentiment == "Bounce")
    ).count()

    hot_leads = db.query(Lead).filter(Lead.is_hot == True).count()
    whatsapp_converted = db.query(Lead).filter(Lead.whatsapp_converted == True).count()

    daily_limit = int(get_setting_value(db, "daily_send_limit", "40"))
    remaining_quota = max(0, daily_limit - sent_today)

    deliverability_rate = 100.0 if total_sent == 0 else max(0.0, round(((total_sent - bounces) / total_sent) * 100, 1))
    reply_rate = 0.0 if total_sent == 0 else round((total_replies / total_sent) * 100, 1)

    # Conversion Funnel
    funnel = [
        {"stage": "Clean Leads", "count": total_clean_leads},
        {"stage": "Drafts Created", "count": total_clean_leads - pending_ai},
        {"stage": "Approved", "count": ready_to_send + total_sent},
        {"stage": "Dispatched", "count": total_sent},
        {"stage": "Replies Received", "count": total_replies},
        {"stage": "Hot WhatsApp Leads", "count": hot_leads}
    ]

    # Recent Logs
    logs = [l.to_dict() for l in db.query(CampaignLog).order_by(CampaignLog.id.desc()).limit(20).all()]

    return {
        "total_clean_leads": total_clean_leads,
        "pending_ai": pending_ai,
        "ready_to_send": ready_to_send,
        "sent_today": sent_today,
        "daily_limit": daily_limit,
        "remaining_quota": remaining_quota,
        "quota_status": f"{sent_today} / {daily_limit} ({round((sent_today / daily_limit) * 100 if daily_limit > 0 else 0)}%)",
        "total_sent": total_sent,
        "total_replies": total_replies,
        "interested_count": interested_count,
        "reply_rate": reply_rate,
        "bounces": bounces,
        "deliverability_rate": deliverability_rate,
        "hot_leads": hot_leads,
        "whatsapp_converted": whatsapp_converted,
        "simulation_mode": get_setting_value(db, "simulation_mode", "true") == "true",
        "funnel": funnel,
        "logs": logs
    }

# ----------------- LEADS & THREADS LISTINGS -----------------

@app.get("/api/leads")
def list_leads(
    status: Optional[str] = None,
    is_hot: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    query = db.query(Lead)
    if status:
        query = query.filter(Lead.status == status)
    if is_hot is not None:
        query = query.filter(Lead.is_hot == is_hot)
    if search:
        term = f"%{search}%"
        query = query.filter(
            (Lead.firm_name.ilike(term)) | (Lead.contact_name.ilike(term)) | (Lead.email.ilike(term)) | (Lead.city.ilike(term))
        )
    
    total = query.count()
    leads = query.order_by(Lead.is_hot.desc(), Lead.id.desc()).offset(offset).limit(limit).all()

    return {"leads": [l.to_dict() for l in leads], "total": total}

@app.get("/api/threads/{thread_id}")
def get_thread_detail(thread_id: int, db: Session = Depends(get_db)):
    thread = db.query(EmailThread).filter(EmailThread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread.to_dict()

# ----------------- STATIC ASSETS & FRONTEND -----------------

static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def serve_root():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Rangrag Archviz Studio Backend Live. Frontend UI in /static."}

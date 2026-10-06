"""
Email Service for Rangrag Archviz Studio CRM.
Handles:
1. Live SMTP and IMAP Handshake Testing (/api/settings/domain)
2. Asynchronous Outbound SMTP Dispatcher with Daily Quota & Randomized Human-like Delays (30-60s)
3. IMAP Inbound Reply Scanner & Sentiment Categorization ('Interested', 'Not Interested', 'No Reply')
4. Automated 3-4 Day Follow-up Dispatcher
"""

import asyncio
import smtplib
import imaplib
import email
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import random
import re
import logging
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.models import (
    SessionLocal, Lead, EmailThread, CampaignLog, Setting, get_utc_now
)

logger = logging.getLogger(__name__)

INTERESTED_KEYWORDS = [
    "interested", "share portfolio", "lookbook", "pricing", "rates",
    "send across", "send over", "let's connect", "lets connect", "call",
    "meeting", "discuss", "quotation", "render", "samples", "schedule",
    "love to see", "sounds good", "yes", "deck", "presentation", "collaborate",
    "available", "portfolio", "showcase", "quote", "cost", "let us talk"
]

NOT_INTERESTED_KEYWORDS = [
    "unsubscribe", "not interested", "stop", "remove", "do not contact",
    "don't contact", "no thanks", "no thank you", "wrong person", "spam",
    "not looking", "in-house team only", "leave me alone", "do not email"
]

BOUNCE_INDICATORS = [
    "mailer-daemon", "postmaster", "delivery status notification",
    "failure notice", "undelivered mail", "returned mail", "550 ",
    "address not found", "recipient rejected", "mail delivery failed"
]

def get_setting_value(db: Session, key: str, default: str = "") -> str:
    item = db.query(Setting).filter(Setting.key == key).first()
    return item.value if item else default

def set_setting_value(db: Session, key: str, value: str):
    item = db.query(Setting).filter(Setting.key == key).first()
    if item:
        item.value = str(value)
    else:
        db.add(Setting(key=key, value=str(value)))
    db.commit()

def log_campaign_event(db: Session, event_type: str, details: str, lead_id: Optional[int] = None, status: str = "info"):
    entry = CampaignLog(
        event_type=event_type,
        lead_id=lead_id,
        details=details,
        status=status,
        created_at=get_utc_now()
    )
    db.add(entry)
    db.commit()

# ----------------- MODULE A: DOMAIN MAIL TESTING & HANDSHAKE -----------------

def test_domain_handshake(
    smtp_server: str,
    smtp_port: int,
    smtp_email: str,
    smtp_password: str,
    smtp_use_tls: bool,
    imap_server: str,
    imap_port: int,
    imap_email: str,
    imap_password: str,
    imap_use_ssl: bool,
    simulation_mode: bool = False
) -> Dict[str, Any]:
    """
    Performs a live handshake test for SMTP and IMAP.
    If simulation_mode is enabled or credentials are empty, provides a simulated success report.
    """
    if simulation_mode or not smtp_password or not imap_password:
        return {
            "success": True,
            "mode": "simulation",
            "smtp_status": "Handshake Simulated (Zero Risk Test Mode)",
            "imap_status": "IMAP Simulated (Zero Risk Test Mode)",
            "message": "Domain credentials saved. Running in Zero-Risk Simulation Mode. Real emails will not be blasted until live mode is engaged."
        }

    results = {
        "success": True,
        "mode": "live",
        "smtp_status": "Unknown",
        "imap_status": "Unknown",
        "errors": []
    }

    # 1. Test SMTP Handshake
    try:
        if smtp_port == 465:
            smtp_client = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=12)
        else:
            smtp_client = smtplib.SMTP(smtp_server, smtp_port, timeout=12)
            if smtp_use_tls:
                smtp_client.starttls()

        if smtp_email and smtp_password:
            smtp_client.login(smtp_email, smtp_password)
        smtp_client.noop()
        smtp_client.quit()
        results["smtp_status"] = "Connected & Authenticated Successfully (250 OK)"
    except Exception as e:
        results["success"] = False
        results["smtp_status"] = f"Failed: {str(e)}"
        results["errors"].append(f"SMTP Error: {str(e)}")

    # 2. Test IMAP Handshake
    try:
        if imap_use_ssl:
            imap_client = imaplib.IMAP4_SSL(imap_server, imap_port, timeout=12)
        else:
            imap_client = imaplib.IMAP4(imap_server, imap_port, timeout=12)

        if imap_email and imap_password:
            imap_client.login(imap_email, imap_password)
        imap_client.select("INBOX")
        imap_client.logout()
        results["imap_status"] = "Connected & Authenticated Successfully (INBOX OK)"
    except Exception as e:
        results["success"] = False
        results["imap_status"] = f"Failed: {str(e)}"
        results["errors"].append(f"IMAP Error: {str(e)}")

    results["message"] = "Handshake verified!" if results["success"] else "Handshake encountered errors."
    return results

# ----------------- MODULE D: OUTBOUND DISPATCH ENGINE -----------------

class DispatchEngine:
    def __init__(self):
        self.is_running = False
        self.is_paused = False
        self.current_task: Optional[asyncio.Task] = None
        self.status_message = "Idle"
        self.current_sending_lead: Optional[str] = None
        self.countdown_seconds = 0

    def get_sent_today_count(self) -> int:
        db = SessionLocal()
        try:
            today_start = datetime.combine(date.today(), datetime.min.time())
            count = db.query(EmailThread).filter(
                EmailThread.status == "sent",
                EmailThread.sent_at >= today_start
            ).count()
            return count
        finally:
            db.close()

    def get_status(self) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            daily_limit = int(get_setting_value(db, "daily_send_limit", "40"))
            simulation = get_setting_value(db, "simulation_mode", "true") == "true"
            sent_today = self.get_sent_today_count()
            ready_to_send = db.query(EmailThread).filter(EmailThread.status == "approved").count()
            pending_review = db.query(EmailThread).filter(EmailThread.status == "draft").count()

            return {
                "is_running": self.is_running,
                "is_paused": self.is_paused,
                "status_message": self.status_message,
                "sent_today": sent_today,
                "daily_limit": daily_limit,
                "remaining_quota": max(0, daily_limit - sent_today),
                "ready_to_send": ready_to_send,
                "pending_review": pending_review,
                "current_sending_lead": self.current_sending_lead,
                "countdown_seconds": self.countdown_seconds,
                "simulation_mode": simulation
            }
        finally:
            db.close()

    async def start(self):
        if self.is_running:
            return {"success": False, "message": "Campaign dispatcher is already running"}
        self.is_running = True
        self.is_paused = False
        self.status_message = "Active Dispatching"
        self.current_task = asyncio.create_task(self._dispatch_loop())
        
        db = SessionLocal()
        log_campaign_event(db, "send", "Campaign dispatcher started", status="info")
        db.close()
        return {"success": True, "message": "Campaign dispatcher started"}

    def pause(self):
        self.is_paused = True
        self.status_message = "Paused"
        db = SessionLocal()
        log_campaign_event(db, "send", "Campaign dispatcher paused", status="info")
        db.close()
        return {"success": True, "message": "Campaign dispatcher paused"}

    def resume(self):
        self.is_paused = False
        self.status_message = "Active Dispatching"
        db = SessionLocal()
        log_campaign_event(db, "send", "Campaign dispatcher resumed", status="info")
        db.close()
        return {"success": True, "message": "Campaign dispatcher resumed"}

    def stop(self):
        self.is_running = False
        self.is_paused = False
        self.status_message = "Stopped"
        self.current_sending_lead = None
        self.countdown_seconds = 0
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
        db = SessionLocal()
        log_campaign_event(db, "send", "Campaign dispatcher stopped", status="info")
        db.close()
        return {"success": True, "message": "Campaign dispatcher stopped"}

    async def _dispatch_loop(self):
        while self.is_running:
            if self.is_paused:
                await asyncio.sleep(2)
                continue

            db = SessionLocal()
            try:
                daily_limit = int(get_setting_value(db, "daily_send_limit", "40"))
                sent_today = self.get_sent_today_count()

                # Quota check
                if sent_today >= daily_limit:
                    self.status_message = f"Daily limit reached ({sent_today}/{daily_limit}). Paused to protect domain health."
                    self.is_paused = True
                    log_campaign_event(db, "send", f"Daily quota limit reached ({sent_today}/{daily_limit}). Paused automatically.", status="warning")
                    await asyncio.sleep(30)
                    continue

                # Fetch next approved email
                thread = db.query(EmailThread).filter(EmailThread.status == "approved").order_by(EmailThread.id.asc()).first()
                if not thread:
                    self.status_message = "Queue clear. Waiting for approved drafts..."
                    self.current_sending_lead = None
                    await asyncio.sleep(5)
                    continue

                lead = thread.lead
                if not lead:
                    thread.status = "failed"
                    thread.error_message = "Lead missing"
                    db.commit()
                    continue

                self.current_sending_lead = f"{lead.firm_name} ({lead.email})"
                self.status_message = f"Preparing dispatch to {lead.firm_name}..."

                simulation = get_setting_value(db, "simulation_mode", "true") == "true"
                smtp_server = get_setting_value(db, "smtp_server", "smtp.gmail.com")
                smtp_port = int(get_setting_value(db, "smtp_port", "587"))
                smtp_email = get_setting_value(db, "smtp_email", "")
                smtp_password = get_setting_value(db, "smtp_password", "")
                smtp_use_tls = get_setting_value(db, "smtp_use_tls", "true") == "true"
                sender_name = get_setting_value(db, "sender_name", "Raj Shekhada | Rangrag Archviz Studio")

                now = get_utc_now()

                if simulation:
                    # Simulated natural dispatch
                    await asyncio.sleep(1.8)
                    thread.status = "sent"
                    thread.sent_at = now
                    lead.status = "Dispatched"
                    db.commit()
                    log_campaign_event(db, "send", f"[SIMULATION] Dispatched email to {lead.firm_name} ({lead.email})", lead_id=lead.id, status="success")
                else:
                    # Real Outbound SMTP Dispatch
                    try:
                        msg = MIMEMultipart("alternative")
                        msg["Subject"] = thread.subject
                        msg["From"] = f"{sender_name} <{smtp_email}>"
                        msg["To"] = lead.email
                        msg["Reply-To"] = smtp_email

                        msg.attach(MIMEText(thread.body_text, "plain", "utf-8"))
                        if thread.body_html:
                            msg.attach(MIMEText(thread.body_html, "html", "utf-8"))

                        def _send():
                            if smtp_port == 465:
                                server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=20)
                            else:
                                server = smtplib.SMTP(smtp_server, smtp_port, timeout=20)
                                if smtp_use_tls:
                                    server.starttls()
                            if smtp_email and smtp_password:
                                server.login(smtp_email, smtp_password)
                            server.sendmail(smtp_email, [lead.email], msg.as_string())
                            server.quit()

                        await asyncio.to_thread(_send)
                        thread.status = "sent"
                        thread.sent_at = now
                        lead.status = "Dispatched"
                        db.commit()
                        log_campaign_event(db, "send", f"Outbound email delivered to {lead.firm_name} ({lead.email})", lead_id=lead.id, status="success")
                    except Exception as e:
                        err = str(e)
                        logger.error(f"Failed to send email to {lead.email}: {err}")
                        thread.status = "failed"
                        thread.error_message = err
                        db.commit()
                        log_campaign_event(db, "send", f"Dispatch failed for {lead.firm_name} ({lead.email}): {err}", lead_id=lead.id, status="error")

                # Randomized Human-Like Jitter Delays (30 to 60 seconds)
                min_del = int(get_setting_value(db, "min_delay_seconds", "30"))
                max_del = int(get_setting_value(db, "max_delay_seconds", "60"))
                if max_del < min_del:
                    max_del = min_del + 10
                
                delay_sec = random.randint(min_del, max_del)
                self.status_message = f"Natural human-like cooldown: {delay_sec}s before next send..."

                for count in range(delay_sec, 0, -1):
                    if not self.is_running or self.is_paused:
                        break
                    self.countdown_seconds = count
                    await asyncio.sleep(1)

                self.countdown_seconds = 0

            except Exception as outer_err:
                logger.error(f"Dispatch loop error: {outer_err}")
                await asyncio.sleep(5)
            finally:
                db.close()

# Singleton Dispatcher
dispatch_engine = DispatchEngine()

# ----------------- MODULE E: IMAP MONITORING & AUTO FOLLOW-UPS -----------------

def clean_subject_or_sender(val: Any) -> str:
    if not val:
        return ""
    fragments = decode_header(val)
    res = []
    for frag, enc in fragments:
        if isinstance(frag, bytes):
            res.append(frag.decode(enc or "utf-8", errors="ignore"))
        else:
            res.append(str(frag))
    return " ".join(res)

def classify_sentiment(text: str) -> str:
    lower = text.lower()
    for b in BOUNCE_INDICATORS:
        if b in lower:
            return "Bounce"
    for ni in NOT_INTERESTED_KEYWORDS:
        if ni in lower:
            return "Not Interested"
    for i in INTERESTED_KEYWORDS:
        if i in lower:
            return "Interested"
    return "No Reply"

def scan_imap_inbox(db: Session) -> Dict[str, Any]:
    """
    Scans the connected IMAP domain inbox for unread/recent messages,
    cross-references against sent leads, and categorizes sentiment.
    """
    simulation = get_setting_value(db, "simulation_mode", "true") == "true"
    imap_server = get_setting_value(db, "imap_server", "imap.gmail.com")
    imap_port = int(get_setting_value(db, "imap_port", "993"))
    imap_email = get_setting_value(db, "imap_email", "")
    imap_password = get_setting_value(db, "imap_password", "")
    imap_use_ssl = get_setting_value(db, "imap_use_ssl", "true") == "true"

    if simulation or not imap_email or not imap_password:
        return {
            "success": True,
            "mode": "simulation",
            "message": "Inbox scan completed in safe simulation mode. To test response handling, trigger 'Simulate Lead Reply'.",
            "scanned": 0,
            "replies_detected": 0,
            "bounces_detected": 0
        }

    try:
        if imap_use_ssl:
            client = imaplib.IMAP4_SSL(imap_server, imap_port, timeout=15)
        else:
            client = imaplib.IMAP4(imap_server, imap_port, timeout=15)

        client.login(imap_email, imap_password)
        client.select("INBOX")

        status, msg_nums = client.search(None, "ALL")
        if status != "OK":
            client.logout()
            return {"success": False, "error": "Failed to read IMAP folder"}

        ids = msg_nums[0].split()
        recent_ids = ids[-30:] if len(ids) > 30 else ids

        # Fetch active sent leads
        active_leads = {l.email.lower(): l for l in db.query(Lead).filter(Lead.status.in_(["Dispatched", "Pending AI", "Ready to Review"])).all()}
        
        replies_count = 0
        bounces_count = 0

        for mid in reversed(recent_ids):
            try:
                res, data = client.fetch(mid, "(RFC822)")
                if res != "OK":
                    continue

                raw_msg = email.message_from_bytes(data[0][1])
                from_hdr = clean_subject_or_sender(raw_msg.get("From", ""))
                subj_hdr = clean_subject_or_sender(raw_msg.get("Subject", ""))

                found_emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", from_hdr.lower())
                sender = found_emails[0] if found_emails else ""

                body = ""
                if raw_msg.is_multipart():
                    for part in raw_msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode(errors="ignore")
                            break
                else:
                    body = raw_msg.get_payload(decode=True).decode(errors="ignore")

                if sender in active_leads:
                    lead = active_leads[sender]
                    sentiment = classify_sentiment(f"{subj_hdr} {body}")
                    now = get_utc_now()

                    # Find thread
                    thread = db.query(EmailThread).filter(EmailThread.lead_id == lead.id).order_by(EmailThread.id.desc()).first()

                    if sentiment == "Bounce":
                        bounces_count += 1
                        lead.status = "Bounced"
                        if thread:
                            thread.reply_sentiment = "Bounce"
                            thread.error_message = "Bounced Delivery"
                        log_campaign_event(db, "bounce", f"Bounce detected from {lead.firm_name} ({sender})", lead_id=lead.id, status="error")
                    else:
                        replies_count += 1
                        is_interested = sentiment == "Interested"
                        lead.status = "Interested" if is_interested else "Not Interested"
                        if is_interested:
                            lead.is_hot = True

                        if thread:
                            thread.reply_detected_at = now
                            thread.reply_sentiment = sentiment
                            thread.reply_content = body[:1500]

                        log_campaign_event(
                            db,
                            "reply",
                            f"Reply received from {lead.firm_name} ({sender}) — Tagged '{sentiment}' {'🔥 HOT LEAD!' if is_interested else ''}",
                            lead_id=lead.id,
                            status="success" if is_interested else "info"
                        )
                    db.commit()

            except Exception as e:
                logger.error(f"Error parsing IMAP message: {e}")
                continue

        client.logout()
        return {
            "success": True,
            "mode": "live",
            "scanned": len(recent_ids),
            "replies_detected": replies_count,
            "bounces_detected": bounces_count
        }
    except Exception as e:
        return {"success": False, "error": f"IMAP connection failed: {str(e)}"}

def trigger_followup_scanner(db: Session) -> Dict[str, Any]:
    """
    Checks leads dispatched >= follow_up_days ago (3-4 days) with no reply,
    and automatically drafts follow-up emails.
    """
    follow_up_days = int(get_setting_value(db, "follow_up_days", "3"))
    cutoff = get_utc_now() - timedelta(days=follow_up_days)

    # Leads dispatched with no reply and no existing follow-up
    candidate_leads = db.query(Lead).join(EmailThread).filter(
        Lead.status == "Dispatched",
        EmailThread.status == "sent",
        EmailThread.sent_at <= cutoff,
        EmailThread.reply_detected_at.is_(None)
    ).all()

    from backend.gemini_service import create_lead_draft
    generated_count = 0

    for lead in candidate_leads:
        has_followup = db.query(EmailThread).filter(
            EmailThread.lead_id == lead.id,
            EmailThread.email_type == "followup_1"
        ).first()

        if not has_followup:
            res = create_lead_draft(db, lead.id, is_followup=True)
            if res.get("success"):
                generated_count += 1
                log_campaign_event(
                    db,
                    "followup",
                    f"Automated follow-up drafted for {lead.firm_name} (No response after {follow_up_days} days)",
                    lead_id=lead.id,
                    status="info"
                )

    return {
        "success": True,
        "eligible_leads": len(candidate_leads),
        "followups_created": generated_count
    }

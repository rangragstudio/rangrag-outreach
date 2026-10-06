"""
IMAP Inbox Monitor, Reply Classifier & Automated Follow-Up Engine.
Monitors incoming email replies, classifies sentiment (Interested, Not Interested, Bounce),
tags Hot Leads, and generates scheduled follow-ups for non-respondents.
"""

import imaplib
import email
from email.header import decode_header
import re
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

from backend.database import get_db_connection, get_settings, log_event
from backend.ai_generator import generate_draft_for_lead

logger = logging.getLogger(__name__)

INTERESTED_KEYWORDS = [
    "interested", "share your portfolio", "lookbook", "pricing", "rates",
    "send across", "send over", "let's connect", "lets connect", "call",
    "meeting", "discuss", "quotation", "render", "samples", "schedule",
    "love to see", "sounds good", "yes", "deck", "presentation", "collaborate",
    "available", "portfolio", "showcase", "cost", "quote"
]

NOT_INTERESTED_KEYWORDS = [
    "unsubscribe", "not interested", "stop", "remove", "do not contact",
    "don't contact", "no thanks", "no thank you", "wrong person", "spam",
    "not looking", "in-house team only", "leave me alone"
]

BOUNCE_INDICATORS = [
    "mailer-daemon", "postmaster", "delivery status notification",
    "failure notice", "undelivered mail", "returned mail", "550 ",
    "address not found", "recipient rejected", "mail delivery failed"
]

def clean_header_str(val: Any) -> str:
    if not val:
        return ""
    decoded_fragments = decode_header(val)
    parts = []
    for frag, encoding in decoded_fragments:
        if isinstance(frag, bytes):
            parts.append(frag.decode(encoding or "utf-8", errors="ignore"))
        else:
            parts.append(str(frag))
    return " ".join(parts)

def classify_reply_sentiment(body_text: str, subject: str = "") -> str:
    """
    Classifies an incoming reply text as 'interested', 'not_interested', or 'neutral'.
    """
    text_lower = f"{subject.lower()} {body_text.lower()}"

    # Check bounce first
    for b in BOUNCE_INDICATORS:
        if b in text_lower:
            return "bounce"

    # Check not interested
    for ni in NOT_INTERESTED_KEYWORDS:
        if ni in text_lower:
            return "not_interested"

    # Check interested
    for i in INTERESTED_KEYWORDS:
        if i in text_lower:
            return "interested"

    return "neutral"

def scan_inbox_sync() -> Dict[str, Any]:
    """
    Connects to IMAP server, checks recent inbox messages, and matches against CRM leads.
    """
    settings = get_settings()
    simulation = settings.get("simulation_mode", "true") == "true"
    imap_host = settings.get("imap_host", "imap.gmail.com")
    imap_port = int(settings.get("imap_port", 993))
    imap_user = settings.get("imap_username", "")
    imap_pass = settings.get("imap_password", "")
    use_ssl = settings.get("imap_use_ssl", "true") == "true"

    if not imap_user or not imap_pass or simulation:
        return {
            "success": True,
            "mode": "simulation" if simulation else "unconfigured",
            "message": "IMAP running in simulated / offline mode. Use 'Simulate Lead Reply' to test the reply detection pipeline without live IMAP.",
            "processed_count": 0,
            "replies_detected": 0,
            "bounces_detected": 0
        }

    try:
        if use_ssl:
            mail = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=20)
        else:
            mail = imaplib.IMAP4(imap_host, imap_port, timeout=20)

        mail.login(imap_user, imap_pass)
        mail.select("INBOX")

        # Search for recent messages
        status, messages = mail.search(None, "ALL")
        if status != "OK":
            mail.logout()
            return {"success": False, "error": "Failed to search inbox"}

        msg_ids = messages[0].split()
        # Look at the most recent 30 messages
        recent_ids = msg_ids[-30:] if len(msg_ids) > 30 else msg_ids

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all leads with sent emails
        cursor.execute("SELECT id, email, firm_name, phone FROM leads WHERE status IN ('sent', 'draft_generated');")
        leads_map = {row["email"].lower(): dict(row) for row in cursor.fetchall()}

        replies_found = 0
        bounces_found = 0

        for mid in reversed(recent_ids):
            try:
                res, data = mail.fetch(mid, "(RFC822)")
                if res != "OK":
                    continue
                
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)

                from_header = clean_header_str(msg.get("From", ""))
                subject_header = clean_header_str(msg.get("Subject", ""))

                # Extract sender email address
                from_emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", from_header.lower())
                sender_email = from_emails[0] if from_emails else ""

                # Extract body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        if content_type == "text/plain":
                            body = part.get_payload(decode=True).decode(errors="ignore")
                            break
                else:
                    body = msg.get_payload(decode=True).decode(errors="ignore")

                now = datetime.now(timezone.utc).isoformat()

                # Check if it matches a lead
                if sender_email in leads_map:
                    lead = leads_map[sender_email]
                    lead_id = lead["id"]
                    sentiment = classify_reply_sentiment(body, subject_header)

                    if sentiment == "bounce":
                        bounces_found += 1
                        cursor.execute("UPDATE leads SET status = 'bounced', updated_at = ? WHERE id = ?;", (now, lead_id))
                        cursor.execute("UPDATE emails SET status = 'failed', error_message = 'Email Bounced', updated_at = ? WHERE lead_id = ?;", (now, lead_id))
                        log_event(event_type="bounce", lead_id=lead_id, details=f"Bounce detected for {lead['firm_name']} ({sender_email})", status="error")
                    else:
                        replies_found += 1
                        is_hot = 1 if sentiment == "interested" else 0
                        lead_status = "replied_interested" if sentiment == "interested" else ("replied_not_interested" if sentiment == "not_interested" else "replied_neutral")

                        cursor.execute("""
                            UPDATE leads SET status = ?, is_hot = ?, updated_at = ?
                            WHERE id = ?;
                        """, (lead_status, is_hot, now, lead_id))

                        cursor.execute("""
                            UPDATE emails SET replied_at = ?, reply_content = ?, reply_sentiment = ?, updated_at = ?
                            WHERE lead_id = ?;
                        """, (now, body[:1000], sentiment, now, lead_id))

                        event_tag = "hot_lead" if is_hot else "reply"
                        log_event(
                            event_type=event_tag,
                            lead_id=lead_id,
                            details=f"Reply received from {lead['firm_name']}: Classified as '{sentiment}'. {'🔥 HOT LEAD FLAGGED!' if is_hot else ''}",
                            status="success" if is_hot else "info"
                        )

            except Exception as e:
                logger.error(f"Error parsing email message {mid}: {e}")
                continue

        conn.commit()
        conn.close()
        mail.logout()

        return {
            "success": True,
            "mode": "live",
            "processed_count": len(recent_ids),
            "replies_detected": replies_found,
            "bounces_detected": bounces_found
        }

    except Exception as e:
        return {"success": False, "error": f"IMAP connection error: {str(e)}"}

def check_and_create_automated_followups() -> Dict[str, Any]:
    """
    Checks for leads whose initial email was sent >= follow_up_days ago,
    who haven't replied, and automatically drafts a gentle follow-up.
    """
    settings = get_settings()
    follow_up_days = int(settings.get("follow_up_days", 3))
    cutoff_time = (datetime.now(timezone.utc) - timedelta(days=follow_up_days)).isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Find leads sent before cutoff, no reply, and no existing follow-up email
    cursor.execute("""
        SELECT l.*, e.sent_at, e.id as initial_email_id
        FROM leads l
        JOIN emails e ON l.id = e.lead_id
        WHERE l.status = 'sent'
          AND e.sent_at IS NOT NULL
          AND e.sent_at <= ?
          AND e.replied_at IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM emails fup 
              WHERE fup.lead_id = l.id AND fup.email_type = 'follow_up_1'
          );
    """, (cutoff_time,))

    eligible_leads = [dict(r) for r in cursor.fetchall()]
    conn.close()

    followups_generated = 0
    for lead in eligible_leads:
        res = generate_draft_for_lead(lead["id"], is_followup=True)
        if res.get("success"):
            followups_generated += 1
            log_event(
                event_type="follow_up",
                lead_id=lead["id"],
                details=f"Automated follow-up drafted for {lead['firm_name']} (sent {follow_up_days}+ days ago with no reply)",
                status="info"
            )

    return {
        "success": True,
        "eligible_leads_count": len(eligible_leads),
        "followups_generated": followups_generated
    }

def simulate_reply(lead_id: int, sentiment: str = "interested", sample_text: Optional[str] = None) -> Dict[str, Any]:
    """
    Simulates an incoming reply from a lead to demonstrate the sentiment classifier,
    Hot Lead flagging, and WhatsApp handoff workflows.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads WHERE id = ?;", (lead_id,))
    lead_row = cursor.fetchone()
    if not lead_row:
        conn.close()
        return {"success": False, "error": "Lead not found"}

    lead = dict(lead_row)
    now = datetime.now(timezone.utc).isoformat()

    if not sample_text:
        if sentiment == "interested":
            sample_text = (
                f"Hi Raj, thanks for reaching out! We actually have a residential project and a commercial tower "
                f"in {lead.get('city', 'Ahmedabad')} coming up for presentation next week. We'd love to see your lookbook "
                f"and discuss exterior render pricing. Please share your phone or WhatsApp number so we can coordinate."
            )
        elif sentiment == "not_interested":
            sample_text = "Thanks Raj, but we currently handle all our rendering in-house. Please unsubscribe us from further emails."
        else:
            sample_text = "Could you tell us a bit more about your delivery turnaround times?"

    is_hot = 1 if sentiment == "interested" else 0
    lead_status = "replied_interested" if sentiment == "interested" else ("replied_not_interested" if sentiment == "not_interested" else "replied_neutral")

    cursor.execute("""
        UPDATE leads SET status = ?, is_hot = ?, updated_at = ?
        WHERE id = ?;
    """, (lead_status, is_hot, now, lead_id))

    cursor.execute("""
        UPDATE emails SET replied_at = ?, reply_content = ?, reply_sentiment = ?, updated_at = ?
        WHERE lead_id = ?;
    """, (now, sample_text, sentiment, now, lead_id))

    conn.commit()
    conn.close()

    log_event(
        event_type="hot_lead" if is_hot else "reply",
        lead_id=lead_id,
        details=f"[SIMULATION] Reply simulated from {lead['firm_name']}: Classified as '{sentiment}'. {'🔥 FLAGGED AS HOT LEAD!' if is_hot else ''}",
        status="success" if is_hot else "info"
    )

    return {
        "success": True,
        "lead_id": lead_id,
        "firm_name": lead["firm_name"],
        "sentiment": sentiment,
        "is_hot": is_hot,
        "reply_content": sample_text
    }

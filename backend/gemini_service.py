"""
Gemini AI Email Content Generator for Rangrag Archviz Studio.
Uses Google GenAI SDK (gemini-2.5-flash) to craft bespoke, peer-to-peer partnership emails
highlighting 3D Rendering, Architectural Animation, Interior Visualization, 360° Views & VR.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from backend.models import (
    Lead, EmailThread, Setting, CampaignLog, get_utc_now
)
from backend.templates import (
    render_html_email,
    render_plain_text_email,
    generate_default_personalized_body,
    generate_default_followup_body
)

logger = logging.getLogger(__name__)

PORTFOLIO_URL = "https://rangragstudio.myportfolio.com/"
INSTAGRAM_URL = "https://www.instagram.com/rangrag_studio/"
LINKEDIN_URL = "https://www.linkedin.com/in/raj-shekhada/"

OFFICIAL_SIGNATURE_TEXT = f"""
Best regards,

Raj Shekhada
Founder & 3D Visualization Specialist | Rangrag Archviz Studio
Portfolio: {PORTFOLIO_URL}
Instagram: {INSTAGRAM_URL}
LinkedIn: {LINKEDIN_URL}
"""

def generate_ai_partnership_email(
    api_key: str,
    model_name: str,
    lead: Lead,
    is_followup: bool = False
) -> Dict[str, Any]:
    """
    Calls Google GenAI SDK (gemini-2.5-flash) with dynamic recipient context.
    Falls back gracefully to the official studio template if API key is not configured.
    """
    lead_dict = lead.to_dict()
    firm = lead.firm_name
    contact = lead.contact_name or "Principal Architect"
    city = lead.city or "your city"
    category = lead.category or "Architecture & Interior Design"

    if not api_key:
        if is_followup:
            subj = f"Quick follow-up: 3D viz collaboration for {firm}"
            body_p = generate_default_followup_body(lead_dict)
        else:
            subj = f"3D Viz Partnership for {firm} — Rangrag Archviz Studio"
            body_p = generate_default_personalized_body(lead_dict)

        return {
            "subject": subj,
            "personalized_paragraphs": body_p,
            "is_ai": False
        }

    try:
        client = genai.Client(api_key=api_key)

        if is_followup:
            prompt = f"""You are Raj Shekhada, founder of "Rangrag Archviz Studio" (expert in V-Ray, Corona, and D5 rendering).
Write a polite, concise peer-to-peer follow-up outreach email to:
- Firm Name: {firm}
- Contact Person: {contact}
- City: {city}
- Category: {category}

Highlight: Checking in to see if they have upcoming concept presentations or design competitions where our 3D exterior renders, interior styling, or walkthrough animations could save their design team bottleneck rendering hours.
Return a clean JSON object with keys 'subject' and 'body_paragraphs' (do not include salutation 'Hi' or signature 'Best regards').
JSON Schema:
{{
  "subject": "Concise follow-up subject mentioning {firm}",
  "body_paragraphs": "2 concise paragraphs separated by \\n\\n"
}}"""
        else:
            prompt = f"""You are Raj Shekhada, founder and principal 3D artist at "Rangrag Archviz Studio" (high-end architectural visualization studio).
Write a tailored, peer-to-peer partnership collaboration email to:
- Firm: {firm}
- Contact Person: {contact}
- City: {city}
- Specialty: {category}

Key Requirements:
1. Tone: Peer-to-peer collaboration (architect/visualizer to architect/designer), NOT spammy or salesy.
2. Acknowledge their distinguished architectural/interior work in {city}.
3. Frame Rangrag Archviz as a specialized visual extension to their team to eliminate bottleneck rendering times during tight design deadlines.
4. Highlight core visual offerings: Photorealistic 3D Renders (Chaos V-Ray, Corona, D5), Luxury Interior Visualization, Cinematic Architectural Walkthrough Animations, and 360° Interactive Panoramas & VR Virtual Tours.
5. Offer a frictionless review of the studio lookbook or a 5-minute visual review.

Output strictly valid JSON with keys 'subject' and 'body_paragraphs'. Do NOT include salutation ('Hi {contact}') or closing ('Best regards'), as the system wraps those.
{{
  "subject": "Bespoke subject line mentioning {firm} or {city}",
  "body_paragraphs": "2 rich, persuasive paragraphs separated by \\n\\n"
}}"""

        response = client.models.generate_content(
            model=model_name or "gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7,
            ),
        )

        res_data = json.loads(response.text.strip())
        return {
            "subject": res_data.get("subject", f"3D Viz Partnership for {firm} — Rangrag Archviz"),
            "personalized_paragraphs": res_data.get("body_paragraphs", generate_default_personalized_body(lead_dict)),
            "is_ai": True
        }

    except Exception as e:
        logger.error(f"Gemini API generation error: {e}")
        fallback_body = generate_default_followup_body(lead_dict) if is_followup else generate_default_personalized_body(lead_dict)
        return {
            "subject": f"3D Viz Partnership for {firm} — Rangrag Archviz",
            "personalized_paragraphs": fallback_body,
            "is_ai": False,
            "error": str(e)
        }

def create_lead_draft(db: Session, lead_id: int, is_followup: bool = False) -> Dict[str, Any]:
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return {"success": False, "error": f"Lead {lead_id} not found"}

    api_key_item = db.query(Setting).filter(Setting.key == "gemini_api_key").first()
    model_item = db.query(Setting).filter(Setting.key == "gemini_model").first()

    api_key = api_key_item.value if api_key_item else ""
    model_name = model_item.value if model_item else "gemini-2.5-flash"

    content = generate_ai_partnership_email(api_key, model_name, lead, is_followup=is_followup)
    
    lead_dict = lead.to_dict()
    subject = content["subject"]
    paragraphs = content["personalized_paragraphs"]

    body_text = render_plain_text_email(lead_dict, paragraphs)
    body_html = render_html_email(lead_dict, paragraphs, subject=subject)

    now = get_utc_now()
    thread = EmailThread(
        lead_id=lead.id,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        email_type="followup_1" if is_followup else "initial",
        status="draft",
        created_at=now,
        updated_at=now
    )
    db.add(thread)
    
    lead.status = "Ready to Review"
    lead.updated_at = now
    db.commit()

    # Log event
    log_entry = CampaignLog(
        event_type="ai_generate",
        lead_id=lead.id,
        details=f"Drafted {'AI (Gemini 2.5 Flash)' if content.get('is_ai') else 'Studio Master Template'} email for {lead.firm_name}",
        status="success",
        created_at=now
    )
    db.add(log_entry)
    db.commit()

    return {
        "success": True,
        "thread_id": thread.id,
        "lead_id": lead.id,
        "subject": subject,
        "is_ai": content.get("is_ai", False),
        "status": "Ready to Review"
    }

def batch_create_drafts(db: Session, limit: int = 50) -> Dict[str, Any]:
    """
    Finds leads in 'Pending AI' status and creates email drafts for them.
    """
    leads = db.query(Lead).filter(Lead.status == "Pending AI").limit(limit).all()
    created = 0
    errors = []

    for l in leads:
        res = create_lead_draft(db, l.id)
        if res.get("success"):
            created += 1
        else:
            errors.append(f"Lead {l.id}: {res.get('error')}")

    return {
        "success": True,
        "total_attempted": len(leads),
        "drafts_created": created,
        "errors": errors
    }

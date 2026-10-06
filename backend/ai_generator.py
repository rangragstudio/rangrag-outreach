"""
AI Custom Email Generator for Rangrag Archviz Studio using Google Gemini (google-genai SDK).
Generates bespoke, peer-to-peer collaboration emails tailored to specific architecture and interior design firms.
"""

import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
from google import genai
from google.genai import types

from backend.database import get_db_connection, get_settings, log_event
from backend.templates import (
    render_html_email,
    render_plain_text_email,
    generate_default_personalized_body,
    generate_default_followup_body
)

logger = logging.getLogger(__name__)

def generate_ai_content(lead: Dict[str, Any], is_followup: bool = False) -> Dict[str, Any]:
    """
    Calls Google Gemini using google-genai SDK to generate bespoke outreach copy.
    Falls back cleanly to high-fidelity rule-based copy if API key is not configured.
    """
    settings = get_settings()
    api_key = settings.get("gemini_api_key", "").strip()
    model_name = settings.get("gemini_model", "gemini-2.5-flash").strip()

    firm_name = lead.get("firm_name", "your studio")
    contact_name = lead.get("contact_name") or "there"
    city = lead.get("city", "your city")
    category = lead.get("category", "Architecture & Interior Design")
    website = lead.get("website", "")

    # Fallback default if API key is missing or fails
    if not api_key:
        if is_followup:
            subject = f"Following up: 3D viz collaboration for {firm_name}"
            body = generate_default_followup_body(lead)
        else:
            subject = f"3D Viz Collaboration for {firm_name} — Rangrag Archviz"
            body = generate_default_personalized_body(lead)

        return {
            "subject": subject,
            "personalized_message": body,
            "subject_alternatives": [
                f"Quick collaboration note: 3D viz partnership for {firm_name}",
                f"Visualizing your upcoming designs in {city} — Rangrag Archviz",
                f"{contact_name}, quick note regarding architectural visualization for {firm_name}"
            ],
            "is_ai_generated": False
        }

    # Prompt engineering for Gemini
    try:
        client = genai.Client(api_key=api_key)

        if is_followup:
            prompt = f"""You are Raj Shekhada, founder and principal 3D artist at "Rangrag Archviz Studio" (specializing in photorealistic 3D architectural rendering, V-Ray, Corona, and D5 rendering).
Write a brief, polite, peer-to-peer follow-up email to:
- Firm Name: {firm_name}
- Contact Person: {contact_name}
- Location: {city}
- Category: {category}

The tone should be warm, professional, respectful of their busy schedule, and focused on offering assistance for upcoming presentation deadlines or concept pitches.
Highlight Rangrag Studio's core strengths: Photorealistic exterior/interior renders, cinematic walkthrough animations, and 360° VR.

Return a valid JSON object strictly matching this schema:
{{
  "subject": "Compelling concise follow-up subject line",
  "personalized_message": "2 short paragraphs of body text (DO NOT include greeting like 'Hi' or sign-off like 'Best regards', as our template wraps those automatically)",
  "subject_alternatives": ["Alternative 1", "Alternative 2"]
}}"""
        else:
            prompt = f"""You are Raj Shekhada, founder and principal 3D visualizer at "Rangrag Archviz Studio" (portfolio: https://rangragstudio.myportfolio.com/, Instagram: @rangrag_studio).
You are writing a bespoke, peer-to-peer collaboration outreach email to an architectural/interior design firm.
Recipient Information:
- Firm Name: {firm_name}
- Contact Person: {contact_name}
- City: {city}
- Category: {category}
- Website: {website}

Guidelines:
1. Tone: Collaborative, peer-to-peer (fellow visual artist to architect/designer), NOT generic marketing fluff.
2. Acknowledge and appreciate their design reputation in {city}.
3. Position Rangrag Archviz Studio as an agile extension of their in-house design team:
   - Eliminating bottleneck rendering times during crunch deadlines.
   - Core capabilities: High-end 3D Renders (Chaos V-Ray, Corona, D5), Luxury Interior Visualization, Cinematic 4K Walkthrough Animations, and 360° Interactive Panoramas / VR tours.
   - Fast turnaround times, photorealistic lighting, and seamless revision rounds.
4. Output Format: DO NOT include greetings (like "Hi John") or signatures (like "Raj Shekhada"), because our master template already wraps them in an executive visual card. Only provide the body paragraphs.

Return a valid JSON object strictly matching this schema:
{{
  "subject": "High-converting, non-spammy subject line mentioning their firm or city",
  "personalized_message": "2 engaging, peer-to-peer collaboration paragraphs (separated by \\n\\n)",
  "subject_alternatives": ["Alternative Subject 1", "Alternative Subject 2"]
}}"""

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7,
            ),
        )

        text_response = response.text.strip()
        data = json.loads(text_response)

        return {
            "subject": data.get("subject", f"3D Viz Collaboration for {firm_name} — Rangrag Archviz"),
            "personalized_message": data.get("personalized_message", generate_default_personalized_body(lead)),
            "subject_alternatives": data.get("subject_alternatives", []),
            "is_ai_generated": True
        }

    except Exception as e:
        logger.error(f"Gemini API generation error: {str(e)}")
        # Graceful fallback to default template
        fallback_body = generate_default_followup_body(lead) if is_followup else generate_default_personalized_body(lead)
        fallback_subject = f"Following up: 3D viz collaboration for {firm_name}" if is_followup else f"3D Viz Collaboration for {firm_name} — Rangrag Archviz"
        return {
            "subject": fallback_subject,
            "personalized_message": fallback_body,
            "subject_alternatives": [
                f"Quick collaboration note: 3D viz partnership for {firm_name}",
                f"Visualizing your upcoming designs in {city} — Rangrag Archviz"
            ],
            "is_ai_generated": False,
            "error_note": str(e)
        }

def generate_draft_for_lead(lead_id: int, is_followup: bool = False) -> Dict[str, Any]:
    """
    Generates a draft for a specific lead and stores it in the 'emails' table.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads WHERE id = ?;", (lead_id,))
    lead_row = cursor.fetchone()
    if not lead_row:
        conn.close()
        return {"success": False, "error": f"Lead with id {lead_id} not found"}

    lead = dict(lead_row)
    ai_result = generate_ai_content(lead, is_followup=is_followup)

    subject = ai_result["subject"]
    body_text = render_plain_text_email(lead, ai_result["personalized_message"])
    body_html = render_html_email(lead, ai_result["personalized_message"], subject=subject)
    now = datetime.now(timezone.utc).isoformat()
    email_type = "follow_up_1" if is_followup else "initial"

    cursor.execute("""
        INSERT INTO emails (lead_id, subject, body_text, body_html, email_type, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'pending_review', ?, ?);
    """, (lead_id, subject, body_text, body_html, email_type, now, now))
    email_id = cursor.lastrowid

    # Update lead status
    cursor.execute("UPDATE leads SET status = 'draft_generated', updated_at = ? WHERE id = ?;", (now, lead_id))

    conn.commit()
    conn.close()

    log_event(
        event_type="generate",
        lead_id=lead_id,
        details=f"Generated {'AI' if ai_result.get('is_ai_generated') else 'custom'} draft for {lead.get('firm_name')} ({lead.get('email')})",
        status="success"
    )

    return {
        "success": True,
        "email_id": email_id,
        "lead_id": lead_id,
        "subject": subject,
        "subject_alternatives": ai_result.get("subject_alternatives", []),
        "is_ai_generated": ai_result.get("is_ai_generated", False),
        "status": "pending_review"
    }

def batch_generate_drafts(limit: int = 50) -> Dict[str, Any]:
    """
    Generates drafts in batch for leads that do not have an active draft or haven't been sent to yet.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT l.* FROM leads l
        LEFT JOIN emails e ON l.id = e.lead_id
        WHERE e.id IS NULL AND l.status = 'clean'
        LIMIT ?;
    """, (limit,))
    leads_to_process = [dict(r) for r in cursor.fetchall()]
    conn.close()

    generated_count = 0
    errors = []

    for lead in leads_to_process:
        res = generate_draft_for_lead(lead["id"])
        if res.get("success"):
            generated_count += 1
        else:
            errors.append(res.get("error"))

    return {
        "success": True,
        "total_attempted": len(leads_to_process),
        "generated_count": generated_count,
        "errors": errors
    }

"""
Automated SMTP Sender Engine with Randomized Human-like Delays and Daily Limits.
Protects domain reputation with simulation mode, jitter delays, and quota controls.
"""

import asyncio
import smtplib
import random
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, date
from typing import Dict, Any, Optional

from backend.database import get_db_connection, get_settings, log_event

logger = logging.getLogger(__name__)

class SenderEngine:
    def __init__(self):
        self.is_running = False
        self.is_paused = False
        self.current_task: Optional[asyncio.Task] = None
        self.current_email_info: Optional[Dict[str, Any]] = None
        self.next_send_countdown: int = 0
        self.status_message: str = "Idle"

    def get_sent_count_today(self) -> int:
        today_str = date.today().isoformat()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count FROM emails
            WHERE status = 'sent' AND date(sent_at) = ?;
        """, (today_str,))
        row = cursor.fetchone()
        conn.close()
        return row["count"] if row else 0

    def get_status(self) -> Dict[str, Any]:
        settings = get_settings()
        daily_limit = int(settings.get("daily_send_limit", 40))
        sent_today = self.get_sent_count_today()
        remaining_quota = max(0, daily_limit - sent_today)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM emails WHERE status = 'approved';")
        approved_count = cursor.fetchone()["count"]
        cursor.execute("SELECT COUNT(*) as count FROM emails WHERE status = 'pending_review';")
        pending_review_count = cursor.fetchone()["count"]
        conn.close()

        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "status_message": self.status_message,
            "sent_today": sent_today,
            "daily_limit": daily_limit,
            "remaining_quota": remaining_quota,
            "approved_in_queue": approved_count,
            "pending_review": pending_review_count,
            "simulation_mode": settings.get("simulation_mode", "true") == "true",
            "current_email": self.current_email_info,
            "next_send_countdown": self.next_send_countdown
        }

    async def start(self):
        if self.is_running:
            return {"success": False, "message": "Sender is already running"}
        self.is_running = True
        self.is_paused = False
        self.status_message = "Active"
        self.current_task = asyncio.create_task(self._run_loop())
        log_event(event_type="send", details="Outreach sender engine started", status="info")
        return {"success": True, "message": "Sender started successfully"}

    def stop(self):
        self.is_running = False
        self.is_paused = False
        self.status_message = "Stopped"
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
        log_event(event_type="send", details="Outreach sender engine stopped", status="info")
        return {"success": True, "message": "Sender stopped"}

    def pause(self):
        self.is_paused = True
        self.status_message = "Paused"
        log_event(event_type="send", details="Outreach sender engine paused", status="info")
        return {"success": True, "message": "Sender paused"}

    def resume(self):
        self.is_paused = False
        self.status_message = "Active"
        log_event(event_type="send", details="Outreach sender engine resumed", status="info")
        return {"success": True, "message": "Sender resumed"}

    async def _run_loop(self):
        while self.is_running:
            if self.is_paused:
                await asyncio.sleep(2)
                continue

            settings = get_settings()
            daily_limit = int(settings.get("daily_send_limit", 40))
            sent_today = self.get_sent_count_today()

            if sent_today >= daily_limit:
                self.status_message = f"Daily limit reached ({sent_today}/{daily_limit}). Pausing until tomorrow."
                self.is_paused = True
                log_event(event_type="send", details=f"Daily quota reached ({sent_today}/{daily_limit}). Paused sender.", status="warning")
                await asyncio.sleep(60)
                continue

            # Fetch the next approved email
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.*, l.email as lead_email, l.firm_name, l.contact_name
                FROM emails e
                JOIN leads l ON e.lead_id = l.id
                WHERE e.status = 'approved'
                ORDER BY e.id ASC
                LIMIT 1;
            """)
            next_email = cursor.fetchone()
            conn.close()

            if not next_email:
                self.status_message = "No approved emails waiting in queue. Waiting for approvals..."
                self.current_email_info = None
                await asyncio.sleep(5)
                continue

            email_dict = dict(next_email)
            self.current_email_info = {
                "id": email_dict["id"],
                "firm_name": email_dict["firm_name"],
                "lead_email": email_dict["lead_email"],
                "subject": email_dict["subject"]
            }

            # Dispatch send
            success, err_msg = await self._send_single_email(email_dict, settings)

            # Randomized human-like delay
            min_delay = int(settings.get("min_delay_seconds", 30))
            max_delay = int(settings.get("max_delay_seconds", 60))
            if max_delay < min_delay:
                max_delay = min_delay + 10
            
            delay = random.randint(min_delay, max_delay)
            self.status_message = f"Email to {email_dict['firm_name']} {'sent' if success else 'failed'}. Cooling down for {delay}s..."

            # Countdown ticker
            for remaining in range(delay, 0, -1):
                if not self.is_running or self.is_paused:
                    break
                self.next_send_countdown = remaining
                await asyncio.sleep(1)

            self.next_send_countdown = 0

    async def _send_single_email(self, email_data: Dict[str, Any], settings: Dict[str, str]) -> (bool, Optional[str]):
        email_id = email_data["id"]
        lead_id = email_data["lead_id"]
        recipient = email_data["lead_email"]
        subject = email_data["subject"]
        body_text = email_data["body_text"]
        body_html = email_data["body_html"]
        simulation = settings.get("simulation_mode", "true") == "true"

        now = datetime.now(timezone.utc).isoformat()
        conn = get_db_connection()
        cursor = conn.cursor()

        if simulation:
            # Simulate real network transmission delay
            await asyncio.sleep(1.5)
            cursor.execute("UPDATE emails SET status = 'sent', sent_at = ?, updated_at = ? WHERE id = ?;", (now, now, email_id))
            cursor.execute("UPDATE leads SET status = 'sent', updated_at = ? WHERE id = ?;", (now, lead_id))
            conn.commit()
            conn.close()

            log_event(
                event_type="send",
                lead_id=lead_id,
                details=f"[SIMULATION] Successfully sent to {email_data['firm_name']} ({recipient})",
                status="success"
            )
            return True, None

        # Real SMTP Transmission
        smtp_host = settings.get("smtp_host", "smtp.gmail.com")
        smtp_port = int(settings.get("smtp_port", 587))
        smtp_user = settings.get("smtp_username", "")
        smtp_pass = settings.get("smtp_password", "")
        sender_email = settings.get("smtp_sender_email", smtp_user)
        sender_name = settings.get("smtp_sender_name", "Raj Shekhada | Rangrag Archviz Studio")
        use_tls = settings.get("smtp_use_tls", "true") == "true"

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{sender_name} <{sender_email}>"
            msg["To"] = recipient
            msg["Reply-To"] = sender_email

            part1 = MIMEText(body_text, "plain", "utf-8")
            part2 = MIMEText(body_html, "html", "utf-8")
            msg.attach(part1)
            msg.attach(part2)

            # Connect and send
            def _smtp_call():
                if smtp_port == 465:
                    server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20)
                else:
                    server = smtplib.SMTP(smtp_host, smtp_port, timeout=20)
                    if use_tls:
                        server.starttls()

                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)

                server.sendmail(sender_email, [recipient], msg.as_string())
                server.quit()

            await asyncio.to_thread(_smtp_call)

            cursor.execute("UPDATE emails SET status = 'sent', sent_at = ?, updated_at = ? WHERE id = ?;", (now, now, email_id))
            cursor.execute("UPDATE leads SET status = 'sent', updated_at = ? WHERE id = ?;", (now, lead_id))
            conn.commit()
            conn.close()

            log_event(
                event_type="send",
                lead_id=lead_id,
                details=f"Live SMTP email delivered to {email_data['firm_name']} ({recipient})",
                status="success"
            )
            return True, None

        except Exception as e:
            err_msg = str(e)
            logger.error(f"SMTP send failure for email {email_id}: {err_msg}")
            cursor.execute("UPDATE emails SET status = 'failed', error_message = ?, updated_at = ? WHERE id = ?;", (err_msg, now, email_id))
            conn.commit()
            conn.close()

            log_event(
                event_type="send",
                lead_id=lead_id,
                details=f"SMTP transmission error to {recipient}: {err_msg}",
                status="error"
            )
            return False, err_msg

    async def send_test_email(self, target_email: str) -> Dict[str, Any]:
        """
        Sends an immediate single test email to the user's personal address to verify SMTP setup.
        """
        settings = get_settings()
        simulation = settings.get("simulation_mode", "true") == "true"
        
        sample_lead = {
            "firm_name": "Rangrag Studio Test",
            "contact_name": "Raj Shekhada",
            "email": target_email,
            "city": "Ahmedabad",
            "category": "Architecture & 3D Visualization"
        }
        from backend.templates import generate_default_personalized_body, render_plain_text_email, render_html_email
        msg_body = generate_default_personalized_body(sample_lead)
        subject = "[TEST] Rangrag Archviz Studio — Collaboration Showcase Test"
        body_text = render_plain_text_email(sample_lead, msg_body)
        body_html = render_html_email(sample_lead, msg_body, subject=subject)

        if simulation:
            return {
                "success": True,
                "mode": "simulation",
                "message": f"Simulation test email generated for {target_email}. Everything looks ready! Turn off simulation mode in Settings when ready for live sending."
            }

        # Real SMTP
        smtp_host = settings.get("smtp_host", "smtp.gmail.com")
        smtp_port = int(settings.get("smtp_port", 587))
        smtp_user = settings.get("smtp_username", "")
        smtp_pass = settings.get("smtp_password", "")
        sender_email = settings.get("smtp_sender_email", smtp_user)
        sender_name = settings.get("smtp_sender_name", "Raj Shekhada | Rangrag Archviz Studio")
        use_tls = settings.get("smtp_use_tls", "true") == "true"

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{sender_name} <{sender_email}>"
            msg["To"] = target_email

            msg.attach(MIMEText(body_text, "plain", "utf-8"))
            msg.attach(MIMEText(body_html, "html", "utf-8"))

            def _smtp_call():
                if smtp_port == 465:
                    server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
                else:
                    server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
                    if use_tls:
                        server.starttls()
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(sender_email, [target_email], msg.as_string())
                server.quit()

            await asyncio.to_thread(_smtp_call)
            return {"success": True, "mode": "live", "message": f"Live test email sent successfully to {target_email}!"}
        except Exception as e:
            return {"success": False, "mode": "live", "error": f"SMTP test failed: {str(e)}"}

# Global singleton engine instance
sender_engine = SenderEngine()

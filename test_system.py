"""
Verification and Test Suite for Rangrag Archviz Studio CRM.
Validates:
1. Database Initialization
2. CSV Cleaning & Fresh Export
3. Gemini AI Draft Generation
4. Domain Mail Handshake
5. Instant WhatsApp Handoff
6. Analytics Metrics
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.models import init_database, SessionLocal, Lead, EmailThread, Setting
from backend.csv_service import process_and_clean_csv
from backend.gemini_service import create_lead_draft
from backend.email_service import test_domain_handshake
from fastapi.testclient import TestClient
from backend.app import app

def run_tests():
    print(">> [1/6] Testing Database Initialization...")
    init_database()
    db = SessionLocal()
    settings_count = db.query(Setting).count()
    print(f"   [OK] Database initialized. Default settings entries: {settings_count}")

    print(">> [2/6] Testing CSV Cleaning & fresh_architects_outreach_data.csv Generation...")
    sample_csv_path = os.path.join(os.path.dirname(__file__), "data", "sample_architects_raw.csv")
    with open(sample_csv_path, "rb") as f:
        file_bytes = f.read()
    
    clean_result = process_and_clean_csv(file_bytes, "sample_architects_raw.csv", db)
    assert clean_result["success"], f"CSV clean failed: {clean_result}"
    print(f"   [OK] Raw Rows: {clean_result['total_rows']}, Valid Clean: {clean_result['valid_leads_count']}, Bad Emails Filtered: {clean_result['dropped_invalid_email']}, Duplicates Dropped: {clean_result['dropped_duplicates']}")
    
    fresh_csv_path = os.path.join(os.path.dirname(__file__), "data", "fresh_architects_outreach_data.csv")
    assert os.path.exists(fresh_csv_path), "fresh_architects_outreach_data.csv was not generated!"
    print(f"   [OK] Verified fresh_architects_outreach_data.csv exists at {fresh_csv_path}")

    print(">> [3/6] Testing AI / Custom Email Generation for First Clean Lead...")
    first_lead = db.query(Lead).filter(Lead.status == "Pending AI").first()
    assert first_lead is not None, "No pending lead found"
    draft_res = create_lead_draft(db, first_lead.id)
    assert draft_res["success"], f"Draft creation failed: {draft_res}"
    thread = db.query(EmailThread).filter(EmailThread.id == draft_res["thread_id"]).first()
    assert "https://rangragstudio.myportfolio.com/" in thread.body_text
    assert "https://www.instagram.com/rangrag_studio/" in thread.body_text
    assert "Raj Shekhada" in thread.body_text
    print(f"   [OK] Draft created for '{first_lead.firm_name}': Subject: {thread.subject}")
    print(f"   [OK] Official signature and live portfolio links verified.")

    print(">> [4/6] Testing Domain Mail Handshake (Simulation Mode)...")
    handshake = test_domain_handshake(
        smtp_server="smtp.gmail.com", smtp_port=587, smtp_email="", smtp_password="",
        smtp_use_tls=True, imap_server="imap.gmail.com", imap_port=993, imap_email="",
        imap_password="", imap_use_ssl=True, simulation_mode=True
    )
    assert handshake["success"], f"Handshake failed: {handshake}"
    print(f"   [OK] Handshake test verified: {handshake['smtp_status']}")

    print(">> [5/6] Testing FastAPI REST Endpoints via TestClient...")
    client = TestClient(app)
    
    # Analytics
    r_analytics = client.get("/api/analytics")
    assert r_analytics.status_code == 200, r_analytics.text
    analytics_data = r_analytics.json()
    print(f"   [OK] /api/analytics returned {analytics_data['total_clean_leads']} total leads, Quota: {analytics_data['quota_status']}")

    # Kanban
    r_kanban = client.get("/api/kanban")
    assert r_kanban.status_code == 200
    kanban_data = r_kanban.json()
    print(f"   [OK] /api/kanban returned columns: Pending AI ({len(kanban_data['pending_ai'])}), Ready ({len(kanban_data['ready_to_review'])}), Dispatched ({len(kanban_data['dispatched'])}), Hot ({len(kanban_data['hot_leads'])})")

    # Simulate Reply & Hot Lead WhatsApp Handoff
    print(">> [6/6] Testing Reply Simulation & WhatsApp Handoff...")
    r_sim = client.post("/api/campaign/simulate-reply", json={
        "lead_id": first_lead.id,
        "sentiment": "Interested",
        "sample_text": "Hi Raj, we have an ongoing luxury villa project in Mumbai needing exterior renders and walkthrough animation. Please share your lookbook!"
    })
    assert r_sim.status_code == 200
    assert r_sim.json()["is_hot"] == True
    print(f"   [OK] Reply simulated. Lead tagged as Hot Lead: {r_sim.json()['is_hot']}")

    r_wa = client.post(f"/api/leads/{first_lead.id}/whatsapp-handoff")
    assert r_wa.status_code == 200
    wa_data = r_wa.json()
    assert "https://wa.me/" in wa_data["whatsapp_url"] or "https://web.whatsapp.com/" in wa_data["whatsapp_url"]
    assert "Raj Shekhada" in wa_data["closing_message"]
    print(f"   [OK] Instant WhatsApp Handoff URL generated: {wa_data['whatsapp_url'][:65]}...")

    db.close()
    print("\n=======================================================")
    print("   ALL 6 CORE MODULE TESTS PASSED FLAWLESSLY! [SUCCESS]")
    print("=======================================================\n")

if __name__ == "__main__":
    run_tests()

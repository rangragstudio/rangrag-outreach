"""
SQLite Database and ORM layer for Rangrag Archviz Studio CRM.
Handles leads, emails, campaign logs, and system settings with thread safety.
"""

import sqlite3
import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "rangrag_crm.db")

def get_db_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Leads table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        firm_name TEXT NOT NULL,
        contact_name TEXT,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        city TEXT,
        state TEXT,
        category TEXT,
        website TEXT,
        source TEXT,
        status TEXT DEFAULT 'clean',
        is_hot INTEGER DEFAULT 0,
        whatsapp_converted INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    # Emails / Outreach Drafts table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER NOT NULL,
        subject TEXT NOT NULL,
        body_text TEXT NOT NULL,
        body_html TEXT NOT NULL,
        email_type TEXT DEFAULT 'initial',
        status TEXT DEFAULT 'pending_review',
        sent_at TEXT,
        scheduled_at TEXT,
        error_message TEXT,
        opened_at TEXT,
        replied_at TEXT,
        reply_content TEXT,
        reply_sentiment TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
    );
    """)

    # Campaign Activity Log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS campaign_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        lead_id INTEGER,
        details TEXT,
        status TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # Settings Key-Value Store
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)

    # Initialize default settings if not exists
    default_settings = {
        "gemini_api_key": "",
        "gemini_model": "gemini-2.5-flash",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": "587",
        "smtp_username": "",
        "smtp_password": "",
        "smtp_use_tls": "true",
        "smtp_sender_name": "Raj Shekhada | Rangrag Archviz Studio",
        "smtp_sender_email": "rangragstudio@gmail.com",
        "imap_host": "imap.gmail.com",
        "imap_port": "993",
        "imap_username": "",
        "imap_password": "",
        "imap_use_ssl": "true",
        "daily_send_limit": "40",
        "min_delay_seconds": "30",
        "max_delay_seconds": "60",
        "follow_up_days": "3",
        "simulation_mode": "true",  # Safely starts in simulation mode so users never accidentally blast real emails
        "raj_whatsapp_number": "+919876543210",
        "portfolio_url": "https://rangragstudio.myportfolio.com/",
        "instagram_url": "https://www.instagram.com/rangrag_studio/",
        "linkedin_url": "https://www.linkedin.com/in/raj-shekhada/"
    }

    for k, v in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?);", (k, v))

    conn.commit()
    conn.close()

def get_settings() -> Dict[str, str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings;")
    rows = cursor.fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}

def update_settings(updates: Dict[str, str]):
    conn = get_db_connection()
    cursor = conn.cursor()
    for k, v in updates.items():
        cursor.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value;",
            (k, str(v))
        )
    conn.commit()
    conn.close()

def log_event(event_type: str, lead_id: Optional[int] = None, details: str = "", status: str = "info"):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        "INSERT INTO campaign_logs (event_type, lead_id, details, status, created_at) VALUES (?, ?, ?, ?, ?);",
        (event_type, lead_id, details, status, now)
    )
    conn.commit()
    conn.close()

def get_logs(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT l.*, ld.firm_name, ld.email
        FROM campaign_logs l
        LEFT JOIN leads ld ON l.lead_id = ld.id
        ORDER BY l.id DESC
        LIMIT ?;
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

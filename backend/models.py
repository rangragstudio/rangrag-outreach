"""
SQLAlchemy ORM Models for Rangrag Archviz Studio CRM.
Tables: leads, campaign_logs, settings, email_threads.
"""

from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, scoped_session
import os

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "rangrag_crm.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)

SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()

def get_utc_now():
    return datetime.now(timezone.utc)

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    firm_name = Column(String(255), nullable=False, index=True)
    contact_name = Column(String(255), nullable=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    mobile = Column(String(50), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    category = Column(String(150), nullable=True, default="Architecture & Interior Design")
    website = Column(String(255), nullable=True)
    source = Column(String(255), nullable=True, default="CSV Upload")
    
    # Status lifecycle: 'Pending AI', 'Ready to Review', 'Dispatched', 'Interested', 'Not Interested', 'No Reply', 'Bounced'
    status = Column(String(50), default="Pending AI", index=True)
    is_hot = Column(Boolean, default=False, index=True)
    whatsapp_converted = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    # Relationships
    email_threads = relationship("EmailThread", back_populates="lead", cascade="all, delete-orphan")
    logs = relationship("CampaignLog", back_populates="lead")

    def to_dict(self):
        return {
            "id": self.id,
            "firm_name": self.firm_name,
            "contact_name": self.contact_name or "",
            "email": self.email,
            "mobile": self.mobile or "",
            "city": self.city or "",
            "state": self.state or "",
            "category": self.category or "Architecture & Interior Design",
            "website": self.website or "",
            "status": self.status,
            "is_hot": bool(self.is_hot),
            "whatsapp_converted": bool(self.whatsapp_converted),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class EmailThread(Base):
    __tablename__ = "email_threads"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    body_text = Column(Text, nullable=False)
    body_html = Column(Text, nullable=True)
    email_type = Column(String(50), default="initial")  # 'initial', 'followup_1'
    status = Column(String(50), default="draft", index=True)  # 'draft', 'approved', 'sent', 'failed'
    
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    reply_detected_at = Column(DateTime, nullable=True)
    reply_sentiment = Column(String(50), nullable=True)  # 'Interested', 'Not Interested', 'No Reply', 'Bounce'
    reply_content = Column(Text, nullable=True)

    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    # Relationships
    lead = relationship("Lead", back_populates="email_threads")

    def to_dict(self):
        lead_dict = self.lead.to_dict() if self.lead else {}
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "subject": self.subject,
            "body_text": self.body_text,
            "body_html": self.body_html,
            "email_type": self.email_type,
            "status": self.status,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "error_message": self.error_message,
            "reply_detected_at": self.reply_detected_at.isoformat() if self.reply_detected_at else None,
            "reply_sentiment": self.reply_sentiment,
            "reply_content": self.reply_content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "lead": lead_dict
        }

class CampaignLog(Base):
    __tablename__ = "campaign_logs"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)
    details = Column(Text, nullable=False)
    status = Column(String(50), default="info")  # 'info', 'success', 'warning', 'error'
    created_at = Column(DateTime, default=get_utc_now)

    lead = relationship("Lead", back_populates="logs")

    def to_dict(self):
        return {
            "id": self.id,
            "event_type": self.event_type,
            "lead_id": self.lead_id,
            "firm_name": self.lead.firm_name if self.lead else None,
            "details": self.details,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)

def init_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    default_settings = {
        "gemini_api_key": "",
        "gemini_model": "gemini-2.5-flash",
        "smtp_server": "smtp.gmail.com",
        "smtp_port": "587",
        "smtp_email": "",
        "smtp_password": "",
        "smtp_use_tls": "true",
        "sender_name": "Raj Shekhada | Rangrag Archviz Studio",
        "imap_server": "imap.gmail.com",
        "imap_port": "993",
        "imap_email": "",
        "imap_password": "",
        "imap_use_ssl": "true",
        "daily_send_limit": "40",
        "min_delay_seconds": "30",
        "max_delay_seconds": "60",
        "follow_up_days": "3",
        "simulation_mode": "true",  # Safeguard simulation mode
        "raj_whatsapp_number": "+919876543210",
        "portfolio_url": "https://rangragstudio.myportfolio.com/",
        "instagram_url": "https://www.instagram.com/rangrag_studio/",
        "linkedin_url": "https://www.linkedin.com/in/raj-shekhada/"
    }

    for k, v in default_settings.items():
        existing = db.query(Setting).filter(Setting.key == k).first()
        if not existing:
            db.add(Setting(key=k, value=v))
    db.commit()
    db.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

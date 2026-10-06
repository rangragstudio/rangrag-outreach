"""
CSV Data Upload, Cleaning and Fresh Export Pipeline for Rangrag Archviz Studio.
Validates columns (firm_name, email, city, state, category, mobile),
cleans multi-emails, strips whitespaces, validates syntax,
and writes 'fresh_architects_outreach_data.csv'.
"""

import io
import re
import os
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.models import (
    Lead, CampaignLog, get_utc_now
)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
DUMMY_DOMAINS = {"example.com", "test.com", "sample.com", "dummy.com", "domain.com", "mailinator.com"}

COLUMN_MAPPING_RULES = {
    "firm_name": ["firm_name", "firm", "company", "company_name", "studio_name", "studio", "business_name", "architect_firm", "name"],
    "email": ["email", "e-mail", "email_address", "mail", "contact_email", "primary_email", "work_email"],
    "contact_name": ["contact_name", "contact_person", "person_name", "principal", "architect", "founder", "lead_architect", "contact"],
    "mobile": ["mobile", "phone", "whatsapp", "contact_no", "phone_number", "telephone", "tel", "cell"],
    "city": ["city", "location", "town", "district"],
    "state": ["state", "province", "region"],
    "category": ["category", "type", "specialization", "industry", "profession", "niche"],
    "website": ["website", "site", "web", "url", "portfolio"]
}

def detect_column(col_list: List[str], target: str) -> Optional[str]:
    lower_map = {c.strip().lower(): c for c in col_list}
    for candidate in COLUMN_MAPPING_RULES.get(target, []):
        if candidate in lower_map:
            return lower_map[candidate]
        for c_lower, orig in lower_map.items():
            if candidate in c_lower:
                return orig
    return None

def extract_primary_clean_email(raw_val: Any) -> Optional[str]:
    if not raw_val or pd.isna(raw_val):
        return None
    val_str = str(raw_val).strip().lower()
    # Split multi-emails separated by commas, semicolons, slashes, spaces
    parts = re.split(r"[,;/\s]+", val_str)
    for p in parts:
        clean_p = p.strip().strip(".<>[]\"'")
        if not clean_p or "@" not in clean_p:
            continue
        if EMAIL_REGEX.match(clean_p):
            domain = clean_p.split("@")[-1]
            if domain not in DUMMY_DOMAINS and "." in domain:
                return clean_p
    return None

def normalize_mobile(raw_phone: Any) -> Optional[str]:
    if not raw_phone or pd.isna(raw_phone):
        return None
    digits = re.sub(r"[^\d+]", "", str(raw_phone).strip())
    if not digits:
        return None
    if re.match(r"^[6-9]\d{9}$", digits):
        return f"+91{digits}"
    if digits.startswith("+") and len(digits) >= 10:
        return digits
    if len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    return digits if len(digits) >= 7 else None

def process_and_clean_csv(file_bytes: bytes, filename: str, db: Session) -> Dict[str, Any]:
    try:
        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            try:
                df = pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(io.BytesIO(file_bytes), encoding="latin-1")
    except Exception as e:
        return {"success": False, "error": f"Could not parse file: {str(e)}"}

    total_rows = len(df)
    cols = df.columns.tolist()

    firm_col = detect_column(cols, "firm_name")
    email_col = detect_column(cols, "email")
    contact_col = detect_column(cols, "contact_name")
    mobile_col = detect_column(cols, "mobile")
    city_col = detect_column(cols, "city")
    state_col = detect_column(cols, "state")
    cat_col = detect_column(cols, "category")
    web_col = detect_column(cols, "website")

    if not email_col:
        return {"success": False, "error": "No email column detected. Ensure a column named 'email', 'e-mail' or 'mail' exists."}

    valid_leads = []
    dropped_missing_firm = 0
    dropped_invalid_email = 0
    dropped_duplicates = 0
    seen_emails = set()

    # Pre-fetch existing emails from DB to avoid collision
    existing_emails = {e[0].lower() for e in db.query(Lead.email).all()}

    for idx, row in df.iterrows():
        # 1. Firm Name check
        firm_raw = row.get(firm_col) if firm_col else ""
        firm_clean = str(firm_raw).strip() if firm_raw and not pd.isna(firm_raw) else ""
        if not firm_clean or firm_clean.lower() in ["nan", "null", "none", "n/a", "-"]:
            dropped_missing_firm += 1
            continue

        # 2. Email Cleaning & Syntax Check
        email_raw = row.get(email_col)
        clean_email = extract_primary_clean_email(email_raw)
        if not clean_email:
            dropped_invalid_email += 1
            continue

        # 3. Deduplication check
        if clean_email in seen_emails or clean_email in existing_emails:
            dropped_duplicates += 1
            continue

        seen_emails.add(clean_email)

        # 4. Optional fields
        contact_raw = row.get(contact_col) if contact_col else ""
        contact_clean = str(contact_raw).strip() if contact_raw and not pd.isna(contact_raw) and str(contact_raw).lower() not in ["nan", "null", "none"] else "Principal Architect"

        mobile_raw = row.get(mobile_col) if mobile_col else ""
        mobile_clean = normalize_mobile(mobile_raw) or ""

        city_raw = row.get(city_col) if city_col else ""
        city_clean = str(city_raw).strip() if city_raw and not pd.isna(city_raw) and str(city_raw).lower() not in ["nan", "null", "none"] else "your city"

        state_raw = row.get(state_col) if state_col else ""
        state_clean = str(state_raw).strip() if state_raw and not pd.isna(state_raw) and str(state_raw).lower() not in ["nan", "null", "none"] else ""

        cat_raw = row.get(cat_col) if cat_col else ""
        cat_clean = str(cat_raw).strip() if cat_raw and not pd.isna(cat_raw) and str(cat_raw).lower() not in ["nan", "null", "none"] else "Architecture & Interior Design"

        web_raw = row.get(web_col) if web_col else ""
        web_clean = str(web_raw).strip() if web_raw and not pd.isna(web_raw) and str(web_raw).lower() not in ["nan", "null", "none"] else ""

        lead_item = {
            "firm_name": firm_clean,
            "contact_name": contact_clean,
            "email": clean_email,
            "mobile": mobile_clean,
            "city": city_clean,
            "state": state_clean,
            "category": cat_clean,
            "website": web_clean
        }
        valid_leads.append(lead_item)

    # Export clean dataset to fresh_architects_outreach_data.csv
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(data_dir, exist_ok=True)
    fresh_csv_path = os.path.join(data_dir, "fresh_architects_outreach_data.csv")

    clean_df = pd.DataFrame(valid_leads)
    clean_df.to_csv(fresh_csv_path, index=False, encoding="utf-8")

    # Insert into database
    now = get_utc_now()
    inserted_records = []
    for vl in valid_leads:
        new_lead = Lead(
            firm_name=vl["firm_name"],
            contact_name=vl["contact_name"],
            email=vl["email"],
            mobile=vl["mobile"],
            city=vl["city"],
            state=vl["state"],
            category=vl["category"],
            website=vl["website"],
            source=filename,
            status="Pending AI",
            is_hot=False,
            whatsapp_converted=False,
            created_at=now,
            updated_at=now
        )
        db.add(new_lead)
        inserted_records.append(new_lead)

    db.commit()

    # Log campaign event
    log_entry = CampaignLog(
        event_type="upload",
        details=f"Cleaned {filename}: {total_rows} raw rows &rarr; {len(valid_leads)} valid leads imported. Dropped {dropped_missing_firm} missing firm, {dropped_invalid_email} invalid emails, {dropped_duplicates} duplicates.",
        status="success",
        created_at=now
    )
    db.add(log_entry)
    db.commit()

    return {
        "success": True,
        "total_rows": total_rows,
        "valid_leads_count": len(valid_leads),
        "dropped_missing_firm": dropped_missing_firm,
        "dropped_invalid_email": dropped_invalid_email,
        "dropped_duplicates": dropped_duplicates,
        "download_url": "/api/download/fresh-csv",
        "sample": valid_leads[:8]
    }

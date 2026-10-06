"""
Data Cleaning, Validation, and Fresh CSV Generator for Rangrag Archviz Studio.
Filters raw architect/interior designer leads, parses multi-emails, normalizes phone/WhatsApp numbers,
and generates 'fresh_architects_outreach_data.csv'.
"""

import os
import re
import csv
import io
import pandas as pd
from typing import Dict, Any, List, Tuple
from datetime import datetime, timezone
from backend.database import get_db_connection, log_event

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
DUMMY_DOMAINS = {"example.com", "test.com", "sample.com", "dummy.com", "domain.com", "mailinator.com"}

COLUMN_SYNONYMS = {
    "firm_name": ["firm_name", "firm", "company", "company_name", "studio_name", "studio", "business_name", "architect_firm", "agency", "name"],
    "contact_name": ["contact_name", "contact_person", "person_name", "principal", "founder", "architect", "lead_architect", "owner", "contact"],
    "email": ["email", "e-mail", "email_address", "mail", "contact_email", "primary_email", "emails", "work_email"],
    "phone": ["phone", "mobile", "whatsapp", "contact_no", "phone_number", "telephone", "tel", "cell"],
    "city": ["city", "location", "town", "district", "address_city"],
    "state": ["state", "province", "region"],
    "category": ["category", "type", "specialization", "industry", "profession", "designation", "niche"],
    "website": ["website", "site", "web", "url", "portfolio", "domain"]
}

def detect_column_mapping(columns: List[str]) -> Dict[str, str]:
    mapping = {}
    lower_cols = {col.strip().lower(): col for col in columns}

    for target_field, synonyms in COLUMN_SYNONYMS.items():
        for syn in synonyms:
            if syn in lower_cols:
                mapping[target_field] = lower_cols[syn]
                break
            # Check for partial matches
            for col_lower, original_col in lower_cols.items():
                if syn in col_lower and target_field not in mapping:
                    mapping[target_field] = original_col
                    break
    return mapping

def clean_and_parse_email(raw_email: Any) -> Optional[str]:
    if not raw_email or pd.isna(raw_email):
        return None
    raw_str = str(raw_email).strip().lower()

    # Split on multiple possible delimiters: semicolon, comma, slash, whitespace
    candidates = re.split(r"[,;/\s]+", raw_str)
    for cand in candidates:
        cand = cand.strip().strip(".<>[]\"'")
        if not cand or "@" not in cand:
            continue
        if EMAIL_REGEX.match(cand):
            domain = cand.split("@")[-1]
            if domain not in DUMMY_DOMAINS and len(domain.split(".")) >= 2:
                return cand
    return None

def normalize_phone(raw_phone: Any) -> Optional[str]:
    if not raw_phone or pd.isna(raw_phone):
        return None
    phone_str = str(raw_phone).strip()
    # Remove unwanted punctuation
    digits_only = re.sub(r"[^\d+]", "", phone_str)
    if not digits_only:
        return None
    # If 10 digits (common in India where Raj is based), prepend +91
    if re.match(r"^[6-9]\d{9}$", digits_only):
        return f"+91{digits_only}"
    if digits_only.startswith("+") and len(digits_only) >= 10:
        return digits_only
    if len(digits_only) == 12 and digits_only.startswith("91"):
        return f"+{digits_only}"
    if len(digits_only) >= 7:
        return digits_only
    return None

def clean_leads_data(file_content: bytes, filename: str) -> Dict[str, Any]:
    """
    Parses, validates, and cleans raw CSV or Excel content.
    Generates 'fresh_architects_outreach_data.csv' and syncs to SQLite.
    """
    try:
        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(file_content))
        else:
            # Handle UTF-8 with BOM or latin-1 encodings
            try:
                df = pd.read_csv(io.BytesIO(file_content), encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(io.BytesIO(file_content), encoding="latin-1")
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse file: {str(e)}"
        }

    total_rows = len(df)
    mapping = detect_column_mapping(df.columns.tolist())

    if "email" not in mapping:
        return {
            "success": False,
            "error": "Could not identify an 'Email' column in the uploaded file. Please ensure there is a column named 'email', 'mail', or 'contact_email'."
        }

    valid_leads = []
    rejected_rows = []
    seen_emails = set()
    seen_firms = set()

    missing_firm_count = 0
    invalid_email_count = 0
    duplicates_count = 0

    for idx, row in df.iterrows():
        # Extract firm name
        firm_raw = row.get(mapping.get("firm_name")) if "firm_name" in mapping else None
        firm_name = str(firm_raw).strip() if firm_raw and not pd.isna(firm_raw) else ""
        
        # If firm name is missing or dummy
        if not firm_name or firm_name.lower() in ["nan", "null", "none", "n/a", "-"]:
            missing_firm_count += 1
            rejected_rows.append({"row": idx + 1, "reason": "Missing Firm Name", "data": dict(row)})
            continue

        # Extract and parse email
        email_raw = row.get(mapping.get("email"))
        clean_email = clean_and_parse_email(email_raw)

        if not clean_email:
            invalid_email_count += 1
            rejected_rows.append({"row": idx + 1, "firm": firm_name, "reason": "Invalid or missing email syntax", "data": dict(row)})
            continue

        # Check duplicate by email
        if clean_email in seen_emails:
            duplicates_count += 1
            rejected_rows.append({"row": idx + 1, "firm": firm_name, "reason": f"Duplicate email ({clean_email})", "data": dict(row)})
            continue

        # Contact Name
        contact_raw = row.get(mapping.get("contact_name")) if "contact_name" in mapping else None
        contact_name = str(contact_raw).strip() if contact_raw and not pd.isna(contact_raw) and str(contact_raw).strip().lower() not in ["nan", "none", "n/a"] else "Principal Architect"

        # Phone / WhatsApp
        phone_raw = row.get(mapping.get("phone")) if "phone" in mapping else None
        phone = normalize_phone(phone_raw)

        # City
        city_raw = row.get(mapping.get("city")) if "city" in mapping else None
        city = str(city_raw).strip() if city_raw and not pd.isna(city_raw) and str(city_raw).strip().lower() not in ["nan", "none", "n/a"] else "your city"

        # State
        state_raw = row.get(mapping.get("state")) if "state" in mapping else None
        state = str(state_raw).strip() if state_raw and not pd.isna(state_raw) and str(state_raw).strip().lower() not in ["nan", "none", "n/a"] else ""

        # Category
        category_raw = row.get(mapping.get("category")) if "category" in mapping else None
        category = str(category_raw).strip() if category_raw and not pd.isna(category_raw) and str(category_raw).strip().lower() not in ["nan", "none", "n/a"] else "Architecture & Interior Design"

        # Website
        web_raw = row.get(mapping.get("website")) if "website" in mapping else None
        website = str(web_raw).strip() if web_raw and not pd.isna(web_raw) and str(web_raw).strip().lower() not in ["nan", "none", "n/a"] else ""

        seen_emails.add(clean_email)
        seen_firms.add(firm_name.lower())

        lead_record = {
            "firm_name": firm_name,
            "contact_name": contact_name,
            "email": clean_email,
            "phone": phone or "",
            "city": city,
            "state": state,
            "category": category,
            "website": website,
            "source": filename
        }
        valid_leads.append(lead_record)

    # Save to fresh_architects_outreach_data.csv in /data directory
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(data_dir, exist_ok=True)
    fresh_csv_path = os.path.join(data_dir, "fresh_architects_outreach_data.csv")

    clean_df = pd.DataFrame(valid_leads)
    clean_df.to_csv(fresh_csv_path, index=False, encoding="utf-8")

    # Persist into SQLite DB
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    inserted_count = 0
    updated_count = 0

    for lead in valid_leads:
        try:
            cursor.execute("""
                INSERT INTO leads (firm_name, contact_name, email, phone, city, state, category, website, source, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'clean', ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    firm_name = excluded.firm_name,
                    contact_name = excluded.contact_name,
                    phone = COALESCE(NULLIF(excluded.phone, ''), leads.phone),
                    city = excluded.city,
                    state = excluded.state,
                    category = excluded.category,
                    website = excluded.website,
                    updated_at = excluded.updated_at;
            """, (
                lead["firm_name"], lead["contact_name"], lead["email"], lead["phone"],
                lead["city"], lead["state"], lead["category"], lead["website"], lead["source"],
                now, now
            ))
            if cursor.rowcount > 0:
                inserted_count += 1
        except Exception:
            pass

    conn.commit()
    conn.close()

    log_event(
        event_type="import",
        details=f"Uploaded {filename}: {total_rows} total rows, {len(valid_leads)} cleaned & valid, {invalid_email_count} bad emails, {missing_firm_count} missing firms, {duplicates_count} duplicates dropped.",
        status="success"
    )

    return {
        "success": True,
        "total_rows": total_rows,
        "valid_count": len(valid_leads),
        "missing_firm_count": missing_firm_count,
        "invalid_email_count": invalid_email_count,
        "duplicates_count": duplicates_count,
        "download_url": "/api/download/fresh-csv",
        "sample_preview": valid_leads[:10],
        "rejected_sample": rejected_rows[:5]
    }

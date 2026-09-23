"""Parser for Bank Mandiri / Livin' by Mandiri transaction notification emails.

Extracts structured key-value transaction fields from Mandiri mBanking notification emails
(QRIS, Transfer, Pembayaran, Top-Up, etc.) into conformed ParsedTransaction objects.
"""

import re
import hashlib
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from finance_hub.models import (
    Institution,
    TransactionType,
    ParsedTransaction,
    NotificationPayload,
)
from finance_hub.classifier import classify_transaction

# Indonesian month name map
MONTH_MAP = {
    "jan": "01", "januari": "01", "january": "01",
    "feb": "02", "februari": "02", "february": "02",
    "mar": "03", "maret": "03", "march": "03",
    "apr": "04", "april": "04",
    "mei": "05", "may": "05",
    "jun": "06", "juni": "06", "june": "06",
    "jul": "07", "juli": "07", "july": "07",
    "agu": "08", "agustus": "08", "aug": "08", "august": "08",
    "sep": "09", "september": "09",
    "okt": "10", "oktober": "10", "oct": "10", "october": "10",
    "nov": "11", "november": "11",
    "des": "12", "desember": "12", "dec": "12", "december": "12",
}


def parse_mandiri_email_amount(val_str: str) -> float:
    """Parse Indonesian Rupiah amount string like 'Rp 15.000,00' or '15.000' to float."""
    cleaned = val_str.replace("Rp", "").replace("IDR", "").strip()
    # Check if there is comma decimal (e.g. 15.000,00)
    if "," in cleaned:
        parts = cleaned.split(",")
        integer_part = parts[0].replace(".", "").replace(" ", "").strip()
        dec_part = parts[1].strip() if len(parts) > 1 else "0"
        try:
            return float(f"{integer_part}.{dec_part}")
        except ValueError:
            return 0.0
    else:
        # e.g. 15.000 or 15000
        integer_part = cleaned.replace(".", "").replace(" ", "").strip()
        try:
            return float(integer_part)
        except ValueError:
            return 0.0


def parse_mandiri_email_datetime(tanggal_str: str, jam_str: str = "") -> str:
    """
    Parse date and time strings from Mandiri email into ISO 8601 string.
    Supports DD/MM/YYYY, DD-MM-YYYY, and 'DD Month YYYY'.
    """
    date_clean = tanggal_str.strip()
    time_clean = jam_str.strip() if jam_str else "00:00:00"

    # Match DD/MM/YYYY or DD-MM-YYYY
    m_num = re.search(r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', date_clean)
    if m_num:
        day, month, year = m_num.groups()
        iso_date = f"{year}-{int(month):02d}-{int(day):02d}"
    else:
        # Match e.g. 03 Juni 2025 or 3 Jun 2025
        m_word = re.search(r'(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})', date_clean)
        if m_word:
            day, month_word, year = m_word.groups()
            month_code = MONTH_MAP.get(month_word.lower(), "01")
            iso_date = f"{year}-{month_code}-{int(day):02d}"
        else:
            iso_date = datetime.now().strftime("%Y-%m-%d")

    # Time parsing HH:MM:SS or HH:MM
    m_time = re.search(r'(\d{1,2}):(\d{2})(?::(\d{2}))?', time_clean)
    if m_time:
        hr, mn, sc = m_time.groups()
        sc = sc or "00"
        iso_time = f"{int(hr):02d}:{mn}:{sc}"
    else:
        iso_time = "00:00:00"

    return f"{iso_date}T{iso_time}"


def extract_mandiri_email_fields(text: str) -> Dict[str, str]:
    """
    Extract key-value pairs from Mandiri transaction email text.
    Handles colon-separated lines, markdown table rows, or HTML table extracts.
    """
    fields: Dict[str, str] = {}
    lines = text.splitlines()

    for line in lines:
        cleaned_line = line.strip().strip("|").strip()
        if not cleaned_line:
            continue

        # Look for pattern: Key : Value or Key | Value
        # e.g. "Jenis Transaksi : QRIS Payment" or "| **Jenis Transaksi** | QRIS Payment |"
        m = re.match(r'^\*?\*?([^:|*]+?)\*?\*?\s*[:|]\s*(.+)$', cleaned_line)
        if m:
            raw_key = m.group(1).strip().strip("*").strip()
            raw_val = m.group(2).strip().strip("|").strip().strip("*").strip()
            norm_key = re.sub(r'[^a-z0-9]+', '_', raw_key.lower()).strip('_')
            fields[norm_key] = raw_val

    return fields


class MandiriEmailParser:
    """Parser specifically optimized for Mandiri mBanking / Livin' email receipts."""

    institution = Institution.MANDIRI

    def can_parse(self, sender: str, subject: str, body: str) -> bool:
        """Check if message is a Mandiri transaction notification email."""
        s_lower = sender.lower()
        sub_lower = subject.lower()
        b_lower = body.lower()

        # Mandiri sender or Livin markers
        is_mandiri_sender = (
            "mandiri" in s_lower
            or "livin" in s_lower
            or "bankmandiri" in s_lower
        )
        is_tx_subject = (
            "notifikasi transaksi" in sub_lower
            or "transaction notification" in sub_lower
            or "struk transaksi" in sub_lower
            or "bukti transaksi" in sub_lower
            or "livin" in sub_lower
        )
        has_mandiri_body = (
            "bank mandiri" in b_lower
            or "livin' by mandiri" in b_lower
            or "mandiri mbanking" in b_lower
            or "nasabah mandiri" in b_lower
        )

        return (is_mandiri_sender or has_mandiri_body) and (is_tx_subject or "jenis transaksi" in b_lower)

    def parse(
        self,
        sender: str,
        subject: str,
        body: str,
        message_id: Optional[str] = None,
        email_date: Optional[str] = None,
    ) -> Optional[ParsedTransaction]:
        """
        Parse Mandiri email body into conformed ParsedTransaction.
        Returns None if transaction was failed or non-financial.
        """
        fields = extract_mandiri_email_fields(body)

        # 1. Check Status
        status_val = fields.get("status", "").lower()
        if status_val and not any(ok in status_val for ok in ["berhasil", "sukses", "success", "settled", "selesai"]):
            # Failed or rejected transaction
            return None

        # 2. Extract Transaction Type & Payment Method
        raw_tx_type = fields.get("jenis_transaksi", "").lower()
        tx_type = TransactionType.EXPENSE
        payment_method = "TRANSFER"

        if "qris" in raw_tx_type:
            payment_method = "QRIS"
            tx_type = TransactionType.EXPENSE
        elif "transfer masuk" in raw_tx_type or "penerimaan" in raw_tx_type or "dana masuk" in raw_tx_type:
            payment_method = "BI_FAST" if "bi-fast" in raw_tx_type or "bifast" in raw_tx_type else "BANK_TRANSFER"
            tx_type = TransactionType.INCOME
        elif "transfer" in raw_tx_type or "kirim uang" in raw_tx_type:
            payment_method = "BI_FAST" if "bi-fast" in raw_tx_type or "bifast" in raw_tx_type else "BANK_TRANSFER"
            tx_type = TransactionType.TRANSFER
        elif "pembayaran" in raw_tx_type or "payment" in raw_tx_type or "tagihan" in raw_tx_type:
            payment_method = "BILL_PAYMENT"
            tx_type = TransactionType.EXPENSE
        elif "top up" in raw_tx_type or "topup" in raw_tx_type:
            payment_method = "E_WALLET"
            tx_type = TransactionType.TRANSFER
        elif "pembelian" in raw_tx_type or "debit" in raw_tx_type:
            payment_method = "DEBIT"
            tx_type = TransactionType.EXPENSE

        # 3. Extract Amount
        amount_raw = fields.get("nominal", "") or fields.get("jumlah", "") or fields.get("total", "")
        if amount_raw:
            amount = parse_mandiri_email_amount(amount_raw)
        else:
            # Fallback regex search in body
            m_amt = re.search(r'(?:Rp|IDR)\s*([\d.,]+)', body, re.IGNORECASE)
            amount = parse_mandiri_email_amount(m_amt.group(1)) if m_amt else 0.0

        if amount <= 0.0:
            return None

        # 4. Extract Merchant / Counterparty
        merchant = (
            fields.get("merchant")
            or fields.get("nama_merchant")
            or fields.get("nama_penerima")
            or fields.get("penerima")
            or fields.get("tujuan")
            or fields.get("tujuan_transfer")
            or fields.get("nama_pengirim")
            or fields.get("pengirim")
            or fields.get("penyedia_jasa")
            or "Mandiri Transaction"
        )
        # Clean extra formatting
        merchant = re.sub(r'^(di|ke|dari)\s+', '', merchant, flags=re.IGNORECASE).strip()
        merchant = merchant.strip(" *#|")

        # Transfer to investments (Bibit, Stockbit, RDN) should count as SAVINGS / EXPENSE
        if tx_type == TransactionType.TRANSFER and any(k in merchant.lower() for k in ["bibit", "stockbit", "rdn", "investasi"]):
            tx_type = TransactionType.EXPENSE

        # 5. Extract Date & Time
        tanggal_raw = fields.get("tanggal", "") or fields.get("tgl", "")
        jam_raw = fields.get("jam", "") or fields.get("waktu", "")
        if tanggal_raw:
            timestamp = parse_mandiri_email_datetime(tanggal_raw, jam_raw)
        elif email_date:
            timestamp = email_date
        else:
            timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        # 6. Extract Account Number
        rek_raw = fields.get("no_rekening", "") or fields.get("rekening_sumber", "") or fields.get("dari_rekening", "")
        if rek_raw:
            # Keep last 4 digits
            digits = re.findall(r'\d+', rek_raw)
            if digits:
                last_digits = digits[-1][-4:]
                account_name = f"Mandiri ***{last_digits}"
            else:
                account_name = "Mandiri Tabungan"
        else:
            account_name = "Mandiri Tabungan"

        # 7. Extract Reference Number
        ref_no = fields.get("no_referensi", "") or fields.get("nomor_referensi", "") or fields.get("ref_no", "") or ""
        ref_no = ref_no.strip()

        # 8. Compute Deterministic Raw Hash
        # Priority: Reference Number > Message-ID > Content Token
        if ref_no:
            token = f"email|mandiri|ref:{ref_no}|{amount:.2f}|{timestamp[:10]}"
        elif message_id:
            token = f"email|mandiri|msg:{message_id}|{amount:.2f}|{timestamp}"
        else:
            token = f"email|mandiri|{merchant.lower()}|{amount:.2f}|{timestamp}"

        raw_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        # 9. Classify into 50/30/20 Budgeting Rule
        category, subcategory, bucket = classify_transaction(merchant, body, tx_type)

        notes = f"Email receipt: Mandiri Livin' ({payment_method})"
        if ref_no:
            notes += f" [Ref: {ref_no}]"

        return ParsedTransaction(
            raw_hash=raw_hash,
            source_institution=self.institution,
            transaction_type=tx_type,
            amount=amount,
            merchant=merchant,
            category=category,
            subcategory=subcategory,
            account_name=account_name,
            timestamp=timestamp,
            raw_text=body[:1000],  # preserve original text preview
            budget_bucket=bucket,
            payment_method=payment_method,
            notes=notes,
            source_device="gmail",
        )

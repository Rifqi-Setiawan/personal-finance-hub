"""Parser for Bank Mandiri / Livin' by Mandiri transaction notification emails.

Extracts structured key-value transaction fields from Mandiri mBanking notification emails
(QRIS, Transfer, Pembayaran, Top-Up, etc.) into conformed ParsedTransaction objects.
"""

import re
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime

from finance_hub.models import (
    Institution,
    TransactionType,
    ParsedTransaction,
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
    if "," in cleaned:
        parts = cleaned.split(",")
        integer_part = parts[0].replace(".", "").replace(" ", "").strip()
        dec_part = parts[1].strip() if len(parts) > 1 else "0"
        try:
            return float(f"{integer_part}.{dec_part}")
        except ValueError:
            return 0.0
    else:
        integer_part = cleaned.replace(".", "").replace(" ", "").strip()
        try:
            return float(integer_part)
        except ValueError:
            return 0.0


def parse_mandiri_email_datetime(tanggal_str: str, jam_str: str = "") -> str:
    """Parse date and time strings from Mandiri email into ISO 8601 string."""
    date_clean = tanggal_str.strip()
    time_clean = jam_str.replace("WIB", "").replace("WITA", "").replace("WIT", "").strip() if jam_str else "00:00:00"

    m_num = re.search(r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', date_clean)
    if m_num:
        day, month, year = m_num.groups()
        iso_date = f"{year}-{int(month):02d}-{int(day):02d}"
    else:
        m_word = re.search(r'(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})', date_clean)
        if m_word:
            day, month_word, year = m_word.groups()
            month_code = MONTH_MAP.get(month_word.lower()[:3], "01")
            iso_date = f"{year}-{month_code}-{int(day):02d}"
        else:
            iso_date = datetime.now().strftime("%Y-%m-%d")

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
    Handles colon-separated lines, markdown table rows, whitespace-separated rows,
    and multi-line block sections (e.g. Penerima, Sumber Dana).
    """
    fields: Dict[str, str] = {}
    lines = [line.strip().strip("|").strip() for line in text.splitlines() if line.strip()]

    known_patterns = [
        ("nominal_transaksi", r"^(?:nominal\s*transaksi|total\s*transaksi|total\s*bayar|total)\s*[:\s]\s*(.+)$"),
        ("nominal", r"^(?:nominal|jumlah)\s*[:\s]\s*(.+)$"),
        ("tanggal", r"^(?:tanggal|tgl)\s*[:\s]\s*(.+)$"),
        ("jam", r"^(?:jam|waktu)\s*[:\s]\s*(\d{1,2}:\d{2}(?::\d{2})?.*)$"),
        ("no_ref_qris", r"^(?:no\.?\s*ref\.?\s*qris)\s*[:\s]\s*(.+)$"),
        ("no_referensi", r"^(?:no\.?\s*ref(?:erensi)?)\s*[:\s]\s*(.+)$"),
        ("merchant_pan", r"^(?:merchant\s*pan)\s*[:\s]\s*(.+)$"),
        ("customer_pan", r"^(?:customer\s*pan)\s*[:\s]\s*(.+)$"),
        ("pengakuisisi", r"^(?:pengakuisisi)\s*[:\s]\s*(.+)$"),
        ("terminal_id", r"^(?:terminal\s*id)\s*[:\s]\s*(.+)$"),
        ("jenis_transaksi", r"^(?:jenis\s*transaksi)\s*[:\s]\s*(.+)$"),
        ("status", r"^(?:status)\s*[:\s]\s*(.+)$"),
        ("no_rekening", r"^(?:no\.?\s*rek(?:ening)?|rekening\s*sumber|dari\s*rekening)\s*[:\s]\s*(.+)$"),
        ("merchant", r"^(?:nama\s*merchant|merchant|tujuan\s*transfer|nama\s*penerima|penerima|tujuan)\s*[:\s]\s*(.+)$"),
    ]

    i = 0
    while i < len(lines):
        line = lines[i]

        # 1. Match known patterns first
        matched_known = False
        for key, pat in known_patterns:
            m_k = re.match(pat, line, re.IGNORECASE)
            if m_k:
                fields[key] = m_k.group(1).strip().strip("|*")
                matched_known = True
                break

        if matched_known:
            i += 1
            continue

        # 2. Colon or pipe separated (e.g. "Jenis Transaksi : QRIS Payment")
        m_colon = re.match(r'^\*?\*?([^:|*]+?)\*?\*?\s*[:|]\s*(.+)$', line)
        if m_colon:
            raw_key = m_colon.group(1).strip().strip("*").strip()
            raw_val = m_colon.group(2).strip().strip("|").strip().strip("*").strip()
            norm_key = re.sub(r'[^a-z0-9]+', '_', raw_key.lower()).strip('_')
            fields[norm_key] = raw_val
            i += 1
            continue

        # 3. Block headers (e.g. "Penerima\nES TEH MANIS SOLO NISSA\nDEPOK - ID")
        line_clean = line.strip("*# ").lower()
        if line_clean in ("penerima", "tujuan", "merchant", "tujuan transfer"):
            if i + 1 < len(lines):
                fields["merchant"] = lines[i + 1].strip()
                if i + 2 < len(lines) and (" - id" in lines[i + 2].lower() or "kota" in lines[i + 2].lower()):
                    fields["merchant_location"] = lines[i + 2].strip()
            i += 1
            continue

        # 4. Source fund block (e.g. "Sumber Dana\nMUHAMMAD RIFQI SETIA\n****5369")
        if line_clean in ("sumber dana", "rekening sumber", "dari rekening"):
            if i + 2 < len(lines) and ("*" in lines[i + 2] or re.search(r'\d{4}', lines[i + 2])):
                fields["no_rekening"] = lines[i + 2].strip()
            elif i + 1 < len(lines) and ("*" in lines[i + 1] or re.search(r'\d{4}', lines[i + 1])):
                fields["no_rekening"] = lines[i + 1].strip()
            i += 1
            continue

        i += 1

    return fields


class MandiriEmailParser:
    """Parser specifically optimized for Mandiri mBanking / Livin' email receipts."""

    institution = Institution.MANDIRI

    def can_parse(self, sender: str, subject: str, body: str) -> bool:
        """Check if message is a Mandiri transaction notification email."""
        s_lower = sender.lower()
        sub_lower = subject.lower()
        b_lower = body.lower()

        is_mandiri_sender = (
            "mandiri" in s_lower
            or "livin" in s_lower
            or "bankmandiri" in s_lower
        )
        is_tx_subject = (
            "notifikasi transaksi" in sub_lower
            or "pembayaran berhasil" in sub_lower
            or "transfer berhasil" in sub_lower
            or "transaksi berhasil" in sub_lower
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

        return (is_mandiri_sender or has_mandiri_body) and (
            is_tx_subject
            or "detail transaksi anda" in b_lower
            or "jenis transaksi" in b_lower
            or "nominal transaksi" in b_lower
        )

    def parse(
        self,
        sender: str,
        subject: str,
        body: str,
        message_id: Optional[str] = None,
        email_date: Optional[str] = None,
    ) -> Optional[ParsedTransaction]:
        """Parse Mandiri email body into conformed ParsedTransaction."""
        fields = extract_mandiri_email_fields(body)
        b_lower = body.lower()

        # 1. Check Status
        status_val = fields.get("status", "").lower()
        if "gagal" in b_lower and "berhasil" not in b_lower and "pembayaran berhasil" not in subject.lower():
            return None
        if status_val and not any(ok in status_val for ok in ["berhasil", "sukses", "success", "settled", "selesai"]):
            return None

        # 2. Extract Transaction Type & Payment Method
        raw_tx_type = fields.get("jenis_transaksi", "").lower()
        tx_type = TransactionType.EXPENSE
        payment_method = "TRANSFER"

        # Detect QR / QRIS
        if "qris" in raw_tx_type or "dengan qr" in b_lower or "no_ref_qris" in fields or "merchant_pan" in fields:
            payment_method = "QRIS"
            tx_type = TransactionType.EXPENSE
        elif "transfer masuk" in raw_tx_type or "penerimaan" in raw_tx_type or "dana masuk" in raw_tx_type or "uang masuk" in b_lower:
            payment_method = "BI_FAST" if ("bi-fast" in raw_tx_type or "bifast" in raw_tx_type or "bi-fast" in b_lower) else "BANK_TRANSFER"
            tx_type = TransactionType.INCOME
        elif "transfer" in raw_tx_type or "kirim uang" in raw_tx_type or "transfer berhasil" in subject.lower():
            payment_method = "BI_FAST" if ("bi-fast" in raw_tx_type or "bifast" in raw_tx_type or "bi-fast" in b_lower) else "BANK_TRANSFER"
            tx_type = TransactionType.TRANSFER
        elif "pembayaran" in raw_tx_type or "payment" in raw_tx_type or "tagihan" in raw_tx_type or "pembayaran berhasil" in subject.lower():
            payment_method = "QRIS" if ("qr" in b_lower or "qris" in b_lower) else "BILL_PAYMENT"
            tx_type = TransactionType.EXPENSE
        elif "top up" in raw_tx_type or "topup" in raw_tx_type:
            payment_method = "E_WALLET"
            tx_type = TransactionType.TRANSFER
        elif "pembelian" in raw_tx_type or "debit" in raw_tx_type:
            payment_method = "DEBIT"
            tx_type = TransactionType.EXPENSE

        # 3. Extract Amount
        amount_raw = (
            fields.get("nominal_transaksi")
            or fields.get("nominal")
            or fields.get("jumlah")
            or fields.get("total_transaksi")
            or fields.get("total_bayar")
            or fields.get("total")
        )
        if amount_raw:
            amount = parse_mandiri_email_amount(amount_raw)
        else:
            m_amt = re.search(r'(?:Nominal Transaksi|Nominal|Rp|IDR)\s*[:\s]*([\d.,]+)', body, re.IGNORECASE)
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

        if tx_type == TransactionType.TRANSFER and any(k in merchant.lower() for k in ["bibit", "stockbit", "rdn", "investasi"]):
            tx_type = TransactionType.EXPENSE

        # 5. Extract Date & Time
        tanggal_raw = fields.get("tanggal", "") or fields.get("tgl", "")
        jam_raw = fields.get("jam", "") or fields.get("waktu", "")
        if tanggal_raw:
            timestamp = parse_mandiri_email_datetime(tanggal_raw, jam_raw)
        elif email_date:
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(email_date)
                timestamp = dt.strftime("%Y-%m-%dT%H:%M:%S")
            except Exception:
                timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        else:
            timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        # 6. Extract Account Number
        rek_raw = fields.get("no_rekening", "") or fields.get("rekening_sumber", "") or fields.get("dari_rekening", "")
        if rek_raw:
            digits = re.findall(r'\d+', rek_raw)
            if digits:
                last_digits = digits[-1][-4:]
                account_name = f"Mandiri ***{last_digits}"
            else:
                account_name = "Mandiri Tabungan"
        else:
            account_name = "Mandiri Tabungan"

        # 7. Extract Reference Number
        ref_no = (
            fields.get("no_referensi")
            or fields.get("no_ref_qris")
            or fields.get("nomor_referensi")
            or fields.get("ref_no")
            or ""
        )
        ref_no = ref_no.strip()

        # 8. Compute Deterministic Raw Hash
        if ref_no:
            token = f"email|mandiri|ref:{ref_no}|{amount:.2f}|{timestamp[:10]}"
        elif message_id:
            token = f"email|mandiri|msg:{message_id}|{amount:.2f}|{timestamp}"
        else:
            token = f"email|mandiri|{merchant.lower()}|{amount:.2f}|{timestamp}"

        raw_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        # 9. Classify into 50/30/20 Budgeting Rule
        classify_context = f"{merchant} {fields.get('merchant_location', '')} {raw_tx_type} {payment_method}"
        category, subcategory, bucket = classify_transaction(merchant, classify_context, tx_type)

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
            raw_text=body[:1000],
            budget_bucket=bucket,
            payment_method=payment_method,
            notes=notes,
            source_device="gmail",
        )

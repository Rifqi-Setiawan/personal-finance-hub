"""Base parser classes and utility functions for extracting transaction details."""

from abc import ABC, abstractmethod
from typing import Optional, Tuple
import re
from datetime import datetime, timezone

from finance_hub.models import Institution, TransactionType, ParsedTransaction, NotificationPayload


PROMO_AND_FAILED_PATTERNS = [
    # 1. Failed / Insufficient balance transactions
    r'g(?:a|ak|k)\s+bisa\s+bayar',
    r'tidak\s+(?:dapat|bisa)\s+(?:diproses|dibayar)',
    r'saldonya?\s+kurang',
    r'saldo\s+tidak\s+cukup',
    r'\bgagal\b',
    r'\bdibatalkan\b',
    r'\bkadaluarsa\b',
    r'\bexpired\b',
    # 2. Marketing / Cashback / Discount promos
    r'dapatkan\s+cashback',
    r'cashback\s+s\.?d\.?',
    r'\bcashback\b',
    r'diskon\s+s\.?d\.?',
    r'dapat\s+diskon',
    r'\bdiskon\b',
    r'\bpromo\b',
    r'\bvoucher\b',
    r'bayar\s+semua\s+tagihan\s+diskon',
    r'yuk,?\s+coba\s+sekarang',
    r'klik\s+buat\s+top\s+up',
    r'gratis\s+ongkir',
    r'\bkupon\s+diskon\b',
    r'\bvoucher\s+diskon\b',
    r'\bspaylater\b',
    r'\bgopaylater\b',
    r'ajukan\s+pinjaman',
    r'klaim\s+hadiah',
    r'amankan\s+voucher',
    r'penawaran\s+spesial',
    r'khusus\s+buat\s+kamu',
    # 3. Security / OTP
    r'kode\s+otp',
    r'jangan\s+berikan\s+kode',
    r'login\s+baru\s+terdeteksi',
]


def is_promo_or_non_financial(text: str) -> bool:
    """Return True if text is a marketing promo, notification ad, or failed transaction."""
    txt_lower = text.lower()
    for pat in PROMO_AND_FAILED_PATTERNS:
        if re.search(pat, txt_lower):
            return True
    return False


def parse_amount_idr(text: str) -> float:
    """
    Extract and normalize an IDR amount from text.
    Handles Indonesian number formats (e.g., Rp 25.000.000,00, Rp 45.000, Rp. 100.000, etc.)
    and conversational multipliers like 25rb, 25k, 25 ribu, 2.5jt, 2,5 juta.
    Returns 0.0 if text is identified as a promotional or failed notification.
    """
    if is_promo_or_non_financial(text):
        return 0.0

    # 0. Check conversational multipliers: e.g. "25rb", "25 k", "25ribu", "2.5jt", "2,5 juta"
    mult_match = re.search(r'(?:(?:Rp\.?|IDR)\s*)?([0-9]+(?:[\.,][0-9]+)?)\s*(rb|k|ribu|jt|juta)\b', text, re.IGNORECASE)
    if mult_match:
        num_str = mult_match.group(1).replace(',', '.')
        unit = mult_match.group(2).lower()
        mult = 1000.0 if unit in ('rb', 'k', 'ribu') else 1000000.0
        try:
            return float(num_str) * mult
        except ValueError:
            pass

    # Prefer explicit currency markers
    patterns = [
        r'(?:sebesar\s+)?(?:Rp\.?|IDR)\s*([0-9\.,]+)',
        r'([0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]{2})?)',
        r'([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{2})?)',
        r'\b([0-9]{4,})\b'
    ]

    raw_num = None
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip().rstrip('.,')
            # Avoid matching dates like 01/09 or years like 2026 if too small
            if candidate:
                raw_num = candidate
                break

    if not raw_num:
        return 0.0

    # 1. Both '.' and ',' present
    if '.' in raw_num and ',' in raw_num:
        if raw_num.rfind(',') > raw_num.rfind('.'):
            # Indonesian format: 25.000.000,00
            clean = raw_num.replace('.', '').replace(',', '.')
        else:
            # International format: 25,000,000.00
            clean = raw_num.replace(',', '')
        try:
            return float(clean)
        except ValueError:
            return 0.0

    # 2. Only ',' present
    if ',' in raw_num:
        parts = raw_num.split(',')
        if len(parts) == 2 and len(parts[1]) == 2:
            clean = raw_num.replace(',', '.')
        else:
            clean = raw_num.replace(',', '')
        try:
            return float(clean)
        except ValueError:
            return 0.0

    # 3. Only '.' present
    if '.' in raw_num:
        parts = raw_num.split('.')
        # In IDR, '.' followed by 3 digits is always a thousand separator
        if len(parts) == 2 and len(parts[1]) != 3:
            clean = raw_num
        else:
            clean = raw_num.replace('.', '')
        try:
            return float(clean)
        except ValueError:
            return 0.0

    try:
        return float(raw_num)
    except ValueError:
        return 0.0


def parse_datetime_id(text: str, default_ts: Optional[str] = None) -> str:
    """
    Extract date and time from text (e.g. '01/09 07:14', '03/09 16:45', '2026-09-01 07:15:22').
    Returns ISO 8601 string.
    """
    # Case A: full ISO date or YYYY-MM-DD HH:MM:SS
    iso_match = re.search(r'(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}(?::\d{2})?)', text)
    if iso_match:
        dt_str = iso_match.group(1).replace(' ', 'T')
        if len(dt_str) == 16:
            dt_str += ":00"
        return dt_str

    # Extract year from default_ts if available, default to current year
    year = datetime.now(timezone.utc).year
    if default_ts:
        ymatch = re.search(r'(\d{4})', default_ts)
        if ymatch:
            year = int(ymatch.group(1))

    # Case B: DD/MM HH:MM(:SS)?
    dmy_match = re.search(r'\b(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\s+(\d{1,2}):(\d{2})(?::(\d{2}))?', text)
    if dmy_match:
        d = int(dmy_match.group(1))
        m = int(dmy_match.group(2))
        y = int(dmy_match.group(3)) if dmy_match.group(3) else year
        if y < 100:
            y += 2000
        hh = int(dmy_match.group(4))
        mm = int(dmy_match.group(5))
        ss = int(dmy_match.group(6)) if dmy_match.group(6) else 0
        try:
            dt = datetime(y, m, d, hh, mm, ss)
            return dt.isoformat()
        except ValueError:
            pass

    # Fallback to default_ts if valid, or current local (WIB) timestamp
    if default_ts and len(default_ts) >= 10:
        return default_ts

    # Use current local system time (WIB / server local timezone) without microsecond noise
    return datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S")


class BaseInstitutionParser(ABC):
    """Abstract base parser for financial institution notifications."""

    institution: Institution

    @abstractmethod
    def can_parse(self, payload: NotificationPayload) -> bool:
        """Return True if this parser can handle the given payload."""
        pass

    @abstractmethod
    def parse(self, payload: NotificationPayload, raw_hash: str) -> ParsedTransaction:
        """Parse the payload and return a normalized ParsedTransaction."""
        pass

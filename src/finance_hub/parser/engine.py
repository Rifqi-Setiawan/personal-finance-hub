"""Master parsing engine that orchestrates institution-specific parsers."""

from typing import List, Optional
import re

from finance_hub.models import (
    Institution,
    TransactionType,
    ParsedTransaction,
    NotificationPayload,
    compute_raw_hash,
)
from finance_hub.parser.base import (
    BaseInstitutionParser,
    parse_amount_idr,
    parse_datetime_id,
)
from finance_hub.parser.bca import BCAParser
from finance_hub.parser.mandiri import MandiriParser
from finance_hub.parser.bri import BRIParser
from finance_hub.parser.bni import BNIParser
from finance_hub.parser.jago import JagoParser
from finance_hub.parser.seabank import SeaBankParser
from finance_hub.parser.gopay import GoPayParser
from finance_hub.parser.dana import DANAParser
from finance_hub.parser.ovo import OVOParser
from finance_hub.parser.shopeepay import ShopeePayParser
from finance_hub.classifier import classify_transaction


class ParserEngine:
    """Master parser that detects notification source institution and delegates parsing."""

    def __init__(self):
        self.parsers: List[BaseInstitutionParser] = [
            BCAParser(),
            MandiriParser(),
            BRIParser(),
            BNIParser(),
            JagoParser(),
            SeaBankParser(),
            GoPayParser(),
            DANAParser(),
            OVOParser(),
            ShopeePayParser(),
        ]

    def detect_institution(self, payload: NotificationPayload) -> Institution:
        """Detect the institution from payload metadata or text."""
        for p in self.parsers:
            if p.can_parse(payload):
                return p.institution

        txt = payload.text.lower()
        if "tunai" in txt or "cash" in txt or "struk" in txt:
            return Institution.CASH

        return Institution.CASH

    def parse(self, payload: NotificationPayload, raw_hash: Optional[str] = None) -> ParsedTransaction:
        """
        Parse notification payload into normalized ParsedTransaction.
        Calculates raw_hash if not explicitly provided.
        """
        if not raw_hash:
            raw_hash = compute_raw_hash(payload)

        # 1. Try institution-specific parsers
        for p in self.parsers:
            if p.can_parse(payload):
                return p.parse(payload, raw_hash)

        # 2. Fallback parser for Cash / Generic receipts
        text = payload.text.strip()
        timestamp = parse_datetime_id(text, payload.timestamp)
        amount = parse_amount_idr(text)
        txt_lower = text.lower()

        institution = Institution.CASH
        account_name = "Cash"
        tx_type = TransactionType.EXPENSE
        payment_method = "CASH"

        # Detect specific institution keyword in manual text
        inst_detect = [
            ("mandiri", Institution.MANDIRI, "Mandiri"),
            ("gopay", Institution.GOPAY, "GoPay"),
            ("dana", Institution.DANA, "DANA"),
            ("shopee", Institution.SHOPEEPAY, "ShopeePay"),
            ("bca", Institution.BCA, "BCA"),
            ("bri", Institution.BRI, "BRI"),
            ("bni", Institution.BNI, "BNI"),
            ("jago", Institution.JAGO, "Bank Jago"),
            ("seabank", Institution.SEABANK, "SeaBank"),
            ("ovo", Institution.OVO, "OVO"),
            ("cash", Institution.CASH, "Cash"),
            ("tunai", Institution.CASH, "Cash"),
        ]
        for inst_word, inst_enum, acct in inst_detect:
            if inst_word in txt_lower:
                institution = inst_enum
                account_name = acct
                if inst_enum in (Institution.GOPAY, Institution.DANA, Institution.OVO, Institution.SHOPEEPAY):
                    payment_method = inst_enum.value
                elif inst_enum != Institution.CASH:
                    payment_method = "DEBIT"
                break

        if "masuk" in txt_lower or "gaji" in txt_lower or "pendapatan" in txt_lower or "ditransfer" in txt_lower:
            tx_type = TransactionType.INCOME
        elif "transfer" in txt_lower and "ke" in txt_lower:
            tx_type = TransactionType.TRANSFER

        # If text or title mentions QRIS, set payment method accordingly
        if "qris" in txt_lower or (payload.title and "qris" in payload.title.lower()):
            payment_method = "QRIS"

        # Extract merchant heuristics
        merchant = "Cash Expense"
        m_merch = re.search(r'(?:di|pembelian|ke)\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
        if m_merch:
            merchant = m_merch.group(1).strip()
        elif "apotek" in txt_lower or "apotik" in txt_lower:
            m_apt = re.search(r'(apotek\s+[^0-9]+?)(?:\s+resep|\s+Rp|\d)', text, re.IGNORECASE)
            if m_apt:
                merchant = m_apt.group(1).strip()

        merchant = re.sub(r'^(di|ke|dari)\s+', '', merchant, flags=re.IGNORECASE).strip()
        merchant = merchant.rstrip(' .,:;-')

        # Clean trailing status words (e.g. berhasil, sukses, settled, selesai, etc.)
        status_pattern = r'\s+(?:berhasil|sukses|success|successful|settled|selesai|pending|gagal|failed)\s*$'
        while re.search(status_pattern, merchant, flags=re.IGNORECASE):
            merchant = re.sub(status_pattern, '', merchant, flags=re.IGNORECASE).strip()
            merchant = merchant.rstrip(' .,:;-')

        if not merchant:
            merchant = "Cash Expense"

        category, subcategory, bucket = classify_transaction(merchant, text, tx_type)

        return ParsedTransaction(
            raw_hash=raw_hash,
            source_institution=institution,
            transaction_type=tx_type,
            amount=amount,
            merchant=merchant,
            category=category,
            subcategory=subcategory,
            account_name=account_name,
            timestamp=timestamp,
            raw_text=text,
            budget_bucket=bucket,
            payment_method=payment_method,
            notes=f"Parsed via Fallback Parser ({institution.value})"
        )


# Global default instance
default_engine = ParserEngine()

"""Parser for Bank Rakyat Indonesia (BRI / BRImo) notifications."""

import re
from typing import Optional

from finance_hub.models import Institution, TransactionType, ParsedTransaction, NotificationPayload
from finance_hub.parser.base import BaseInstitutionParser, parse_amount_idr, parse_datetime_id
from finance_hub.classifier import classify_transaction


class BRIParser(BaseInstitutionParser):
    institution = Institution.BRI

    def can_parse(self, payload: NotificationPayload) -> bool:
        pkg = (payload.package_name or "").lower()
        title = (payload.title or "").lower()
        txt = payload.text.lower()

        if "brimo" in pkg or "bri." in pkg:
            return True
        if "brimo" in title or "bank bri" in title or title == "bri":
            return True
        if "brimo:" in txt or "briva" in txt or "bank bri" in txt:
            return True
        return False

    def parse(self, payload: NotificationPayload, raw_hash: str) -> ParsedTransaction:
        text = payload.text.strip()
        timestamp = parse_datetime_id(text, payload.timestamp)
        amount = parse_amount_idr(text)
        txt_lower = text.lower()

        merchant = "BRI Counterparty"
        account_name = "BritAma Account"
        tx_type = TransactionType.EXPENSE
        payment_method = "TRANSFER"

        # Check account number if present: "Rekening: ...1234"
        rek_match = re.search(r'rek(?:ening)?(?:\s+|:)(\d+)', text, re.IGNORECASE)
        if rek_match:
            account_name = f"BRI ***{rek_match.group(1)[-4:]}"

        # 1. Transfer Masuk (INCOME)
        if "transfer masuk" in txt_lower or "dana masuk" in txt_lower:
            tx_type = TransactionType.INCOME
            payment_method = "BANK_TRANSFER"
            m_from = re.search(r'dari\s+([^0-9]+?)(?:\s+Rp|\s+sebesar|\.|$)', text, re.IGNORECASE)
            if m_from:
                merchant = m_from.group(1).strip()

        # 2. QRIS BRImo
        elif "qris" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "QRIS"
            m_qr = re.search(r'(?:di|ke)\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_qr:
                merchant = m_qr.group(1).strip()

        # 3. BRIVA (BRI Virtual Account)
        elif "briva" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "BRIVA"
            m_briva = re.search(r'briva\s+([^0-9]+?)(?:\s+Rp|\s+sebesar|\.|$)', text, re.IGNORECASE)
            if m_briva:
                merchant = m_briva.group(1).strip()

        # 4. Top Up
        elif "top up" in txt_lower or "topup" in txt_lower:
            tx_type = TransactionType.TRANSFER
            payment_method = "E_WALLET"
            m_top = re.search(r'top\s*up\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_top:
                merchant = m_top.group(1).strip()

        # 5. Transfer Keluar
        elif "transfer keluar" in txt_lower or "transfer ke" in txt_lower:
            m_to = re.search(r'ke\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_to:
                merchant = m_to.group(1).strip()
            if any(k in merchant.lower() for k in ["bibit", "stockbit", "rdn", "investasi"]):
                tx_type = TransactionType.EXPENSE
            else:
                tx_type = TransactionType.TRANSFER
            payment_method = "BANK_TRANSFER"

        # 6. Pembayaran Umum
        elif "pembayaran" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "BILL_PAYMENT"
            m_pay = re.search(r'pembayaran\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_pay:
                merchant = m_pay.group(1).strip()

        merchant = re.sub(r'^(di|ke|dari)\s+', '', merchant, flags=re.IGNORECASE).strip()
        merchant = merchant.rstrip(' .,:;-')

        category, subcategory, bucket = classify_transaction(merchant, text, tx_type)

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
            raw_text=text,
            budget_bucket=bucket,
            payment_method=payment_method,
            notes=f"Parsed from BRI ({payment_method})"
        )

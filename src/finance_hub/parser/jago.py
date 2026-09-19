"""Parser for Bank Jago notifications."""

import re
from typing import Optional

from finance_hub.models import Institution, TransactionType, ParsedTransaction, NotificationPayload
from finance_hub.parser.base import BaseInstitutionParser, parse_amount_idr, parse_datetime_id
from finance_hub.classifier import classify_transaction


class JagoParser(BaseInstitutionParser):
    institution = Institution.JAGO

    def can_parse(self, payload: NotificationPayload) -> bool:
        pkg = (payload.package_name or "").lower()
        title = (payload.title or "").lower()
        txt = payload.text.lower()

        if "jago" in pkg or "jago" in title:
            return True
        if "bank jago" in txt or "kantong utama" in txt or "kantong investasi" in txt:
            return True
        return False

    def parse(self, payload: NotificationPayload, raw_hash: str) -> ParsedTransaction:
        text = payload.text.strip()
        timestamp = parse_datetime_id(text, payload.timestamp)
        amount = parse_amount_idr(text)
        txt_lower = text.lower()

        merchant = "Jago Counterparty"
        account_name = "Kantong Utama"
        tx_type = TransactionType.EXPENSE
        payment_method = "JAGO_DEBIT"

        # Check pocket name (Kantong ...)
        pocket_match = re.search(r'(kantong\s+[a-z0-9\s]+?)(?:\s+debit|\s+top up|\s+sebesar|\s+Rp|\d)', text, re.IGNORECASE)
        if pocket_match:
            account_name = pocket_match.group(1).strip()

        # 1. Uang Masuk / Transfer Masuk (INCOME)
        if "uang masuk" in txt_lower or "transfer masuk" in txt_lower or "terima uang" in txt_lower:
            tx_type = TransactionType.INCOME
            payment_method = "BANK_TRANSFER"
            m_from = re.search(r'dari\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_from:
                merchant = m_from.group(1).strip()

        # 2. Mengirim Uang / Transfer ke
        elif "mengirim" in txt_lower or "kirim uang" in txt_lower or "transfer ke" in txt_lower:
            m_to = re.search(r'ke\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_to:
                merchant = m_to.group(1).strip()
            if any(k in merchant.lower() for k in ["bibit", "stockbit", "rdn", "investasi"]):
                tx_type = TransactionType.EXPENSE
            else:
                tx_type = TransactionType.TRANSFER
            payment_method = "TRANSFER"

        # 3. Top Up (Kantong Investasi / Bibit / GoPay)
        elif "top up" in txt_lower or "topup" in txt_lower:
            m_top = re.search(r'top\s*up\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_top:
                merchant = m_top.group(1).strip()
            if any(k in merchant.lower() for k in ["bibit", "stockbit", "rdn", "investasi"]):
                tx_type = TransactionType.EXPENSE
            else:
                tx_type = TransactionType.TRANSFER
            payment_method = "TOP_UP"

        # 4. QRIS Jago
        elif "qris" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "QRIS"
            m_qr = re.search(r'(?:di|ke)\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_qr:
                merchant = m_qr.group(1).strip()

        # 5. Debit Kantong (e.g. "Kantong Utama Debit Netflix Premium Rp 186.000 Berhasil")
        elif "debit" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "DEBIT"
            m_deb = re.search(r'debit\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_deb:
                merchant = m_deb.group(1).strip()

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
            notes=f"Parsed from Bank Jago ({payment_method})"
        )

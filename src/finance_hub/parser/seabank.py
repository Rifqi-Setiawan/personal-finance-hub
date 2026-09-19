"""Parser for SeaBank Indonesia notifications."""

import re
from typing import Optional

from finance_hub.models import Institution, TransactionType, ParsedTransaction, NotificationPayload
from finance_hub.parser.base import BaseInstitutionParser, parse_amount_idr, parse_datetime_id
from finance_hub.classifier import classify_transaction


class SeaBankParser(BaseInstitutionParser):
    institution = Institution.SEABANK

    def can_parse(self, payload: NotificationPayload) -> bool:
        pkg = (payload.package_name or "").lower()
        title = (payload.title or "").lower()
        txt = payload.text.lower()

        if "seabank" in pkg or "seabank" in title:
            return True
        if "seabank:" in txt or "bunga harian tabungan" in txt:
            return True
        return False

    def parse(self, payload: NotificationPayload, raw_hash: str) -> ParsedTransaction:
        text = payload.text.strip()
        timestamp = parse_datetime_id(text, payload.timestamp)
        amount = parse_amount_idr(text)
        txt_lower = text.lower()

        merchant = "SeaBank Counterparty"
        account_name = "SeaBank Tabungan"
        tx_type = TransactionType.EXPENSE
        payment_method = "TRANSFER"

        # 1. Bunga Harian Tabungan (INCOME)
        if "bunga harian" in txt_lower or "bunga tabungan" in txt_lower:
            tx_type = TransactionType.INCOME
            payment_method = "INTEREST"
            merchant = "Bunga Harian Tabungan"

        # 2. Transfer Masuk (INCOME)
        elif "transfer masuk" in txt_lower or "uang masuk" in txt_lower:
            tx_type = TransactionType.INCOME
            payment_method = "BANK_TRANSFER"
            m_from = re.search(r'dari\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_from:
                merchant = m_from.group(1).strip()

        # 3. Alokasi Tabungan / Dana Darurat (EXPENSE/TRANSFER -> SAVINGS)
        elif "alokasi tabungan" in txt_lower or "kantong" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "INTERNAL_ALLOCATION"
            m_alo = re.search(r'alokasi\s+tabungan\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_alo:
                merchant = m_alo.group(1).strip()
            else:
                merchant = "Alokasi Tabungan SeaBank"

        # 4. QRIS SeaBank
        elif "qris" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "QRIS"
            m_qr = re.search(r'(?:di|ke)\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_qr:
                merchant = m_qr.group(1).strip()

        # 5. Transfer Pembayaran (e.g. Tokopedia)
        elif "transfer pembayaran" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "E_COMMERCE"
            m_pay = re.search(r'transfer\s+pembayaran\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_pay:
                merchant = m_pay.group(1).strip()

        # 6. Transfer ke rekening lain
        elif "transfer ke" in txt_lower:
            m_to = re.search(r'ke\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_to:
                merchant = m_to.group(1).strip()
            if any(k in merchant.lower() for k in ["bibit", "stockbit", "rdn", "investasi"]):
                tx_type = TransactionType.EXPENSE
            else:
                tx_type = TransactionType.TRANSFER
            payment_method = "BANK_TRANSFER"

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
            notes=f"Parsed from SeaBank ({payment_method})"
        )

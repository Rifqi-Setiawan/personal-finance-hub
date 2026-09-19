"""Parser for Bank Negara Indonesia (BNI / BNI Mobile / wondr) notifications."""

import re
from typing import Optional

from finance_hub.models import Institution, TransactionType, ParsedTransaction, NotificationPayload
from finance_hub.parser.base import BaseInstitutionParser, parse_amount_idr, parse_datetime_id
from finance_hub.classifier import classify_transaction


class BNIParser(BaseInstitutionParser):
    institution = Institution.BNI

    def can_parse(self, payload: NotificationPayload) -> bool:
        pkg = (payload.package_name or "").lower()
        title = (payload.title or "").lower()
        txt = payload.text.lower()

        if "bni" in pkg or "wondr" in pkg:
            return True
        if "bni" in title or "wondr" in title:
            return True
        if "bni mobile" in txt or "wondr by bni" in txt or "bank bni" in txt:
            return True
        return False

    def parse(self, payload: NotificationPayload, raw_hash: str) -> ParsedTransaction:
        text = payload.text.strip()
        timestamp = parse_datetime_id(text, payload.timestamp)
        amount = parse_amount_idr(text)
        txt_lower = text.lower()

        merchant = "BNI Counterparty"
        account_name = "BNI Taplus"
        tx_type = TransactionType.EXPENSE
        payment_method = "TRANSFER"

        rek_match = re.search(r'rek(?:ening)?(?:\s+|:)(\d+)', text, re.IGNORECASE)
        if rek_match:
            account_name = f"BNI ***{rek_match.group(1)[-4:]}"

        # 1. Transfer Masuk (INCOME)
        if "transfer masuk" in txt_lower or "dana masuk" in txt_lower:
            tx_type = TransactionType.INCOME
            payment_method = "BANK_TRANSFER"
            m_from = re.search(r'dari\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_from:
                merchant = m_from.group(1).strip()

        # 2. QRIS BNI
        elif "qris" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "QRIS"
            m_qr = re.search(r'(?:di|ke)\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_qr:
                merchant = m_qr.group(1).strip()

        # 3. Transfer Keluar
        elif "transfer keluar" in txt_lower or "transfer ke" in txt_lower:
            m_to = re.search(r'ke\s+([^0-9]+?(?:\s+an\s+[^0-9]+?)?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_to:
                merchant = m_to.group(1).strip()
            if any(k in merchant.lower() for k in ["bibit", "stockbit", "rdn", "investasi"]):
                tx_type = TransactionType.EXPENSE
            else:
                tx_type = TransactionType.TRANSFER
            payment_method = "BI_FAST" if "bi-fast" in txt_lower else "BANK_TRANSFER"

        # 4. Pembayaran Tagihan
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
            notes=f"Parsed from BNI ({payment_method})"
        )

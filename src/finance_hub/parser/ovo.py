"""Parser for OVO notifications."""

import re
from typing import Optional

from finance_hub.models import Institution, TransactionType, ParsedTransaction, NotificationPayload
from finance_hub.parser.base import BaseInstitutionParser, parse_amount_idr, parse_datetime_id
from finance_hub.classifier import classify_transaction


class OVOParser(BaseInstitutionParser):
    institution = Institution.OVO

    def can_parse(self, payload: NotificationPayload) -> bool:
        pkg = (payload.package_name or "").lower()
        title = (payload.title or "").lower()
        txt = payload.text.lower()

        if "ovo.id" in pkg or "ovo" in pkg:
            return True
        if "ovo" in title:
            return True
        if "ovo cash:" in txt or "ovo:" in txt or "saldo ovo" in txt:
            return True
        return False

    def parse(self, payload: NotificationPayload, raw_hash: str) -> ParsedTransaction:
        text = payload.text.strip()
        timestamp = parse_datetime_id(text, payload.timestamp)
        amount = parse_amount_idr(text)
        txt_lower = text.lower()

        merchant = "OVO Merchant"
        account_name = "OVO Cash"
        tx_type = TransactionType.EXPENSE
        payment_method = "OVO_CASH"

        # 1. Transfer Masuk (INCOME)
        if "menerima transfer" in txt_lower or "transfer masuk" in txt_lower or "kamu menerima" in txt_lower:
            tx_type = TransactionType.INCOME
            payment_method = "PEER_TO_PEER"
            m_from = re.search(r'dari\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_from:
                merchant = m_from.group(1).strip()
            else:
                merchant = "OVO Transfer Masuk"

        # 2. Top Up saldo
        elif "top up" in txt_lower or "topup" in txt_lower:
            tx_type = TransactionType.TRANSFER
            payment_method = "TOP_UP"
            m_src = re.search(r'dari\s+([^0-9]+?)(?:\s+sebesar|\s+berhasil|\.|$)', text, re.IGNORECASE)
            if m_src:
                merchant = f"Top Up dari {m_src.group(1).strip()}"
            else:
                merchant = "OVO Top Up"

        # 3. Transaksi QRIS
        elif "qris" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "QRIS"
            m_qr = re.search(r'qris\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_qr:
                merchant = m_qr.group(1).strip()

        # 4. Transaksi di Grab / GrabFood
        elif "grab" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "GRAB"
            m_grab = re.search(r'di\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_grab:
                merchant = m_grab.group(1).strip()
            else:
                merchant = "GrabFood / Grab"

        # 5. Pembayaran di merchant
        elif "pembayaran" in txt_lower or "transaksi di" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "OVO_CASH"
            m_pay = re.search(r'(?:pembayaran di|transaksi di)\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
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
            notes=f"Parsed from OVO ({payment_method})"
        )

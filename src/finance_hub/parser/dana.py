"""Parser for DANA Indonesia notifications."""

import re
from typing import Optional

from finance_hub.models import Institution, TransactionType, ParsedTransaction, NotificationPayload
from finance_hub.parser.base import BaseInstitutionParser, parse_amount_idr, parse_datetime_id
from finance_hub.classifier import classify_transaction


class DANAParser(BaseInstitutionParser):
    institution = Institution.DANA

    def can_parse(self, payload: NotificationPayload) -> bool:
        pkg = (payload.package_name or "").lower()
        title = (payload.title or "").lower()
        txt = payload.text.lower()

        if "id.dana" in pkg or "dana" in pkg:
            return True
        if "dana" in title:
            return True
        if "dana protection:" in txt or "dana:" in txt or "saldo dana" in txt:
            return True
        return False

    def parse(self, payload: NotificationPayload, raw_hash: str) -> ParsedTransaction:
        text = payload.text.strip()
        timestamp = parse_datetime_id(text, payload.timestamp)
        amount = parse_amount_idr(text)
        txt_lower = text.lower()

        merchant = "DANA Counterparty"
        account_name = "DANA Balance"
        tx_type = TransactionType.EXPENSE
        payment_method = "DANA"

        # 1. Menerima Uang (INCOME)
        if "menerima uang" in txt_lower or "transfer masuk" in txt_lower:
            tx_type = TransactionType.INCOME
            payment_method = "PEER_TO_PEER"
            m_from = re.search(r'dari\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_from:
                merchant = m_from.group(1).strip()

        # 2. Transfer Saldo / Kirim Uang (TRANSFER)
        elif "transfer saldo" in txt_lower or "kirim uang" in txt_lower:
            tx_type = TransactionType.TRANSFER
            payment_method = "WALLET_TRANSFER"
            m_to = re.search(r'ke\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_to:
                merchant = m_to.group(1).strip()

        # 3. QRIS DANA
        elif "qris" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "QRIS"
            m_qr = re.search(r'qris\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_qr:
                merchant = m_qr.group(1).strip()

        # 4. Pembayaran Tagihan / Merchant
        elif "pembayaran" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "BILL_PAYMENT"
            m_pay = re.search(r'pembayaran(?:\s+tagihan)?\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_pay:
                merchant = m_pay.group(1).strip()

        # 5. Top Up
        elif "top up" in txt_lower or "topup" in txt_lower:
            tx_type = TransactionType.TRANSFER
            payment_method = "TOP_UP"
            merchant = "DANA Top Up"

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
            notes=f"Parsed from DANA ({payment_method})"
        )

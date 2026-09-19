"""Parser for GoPay / Gojek notifications."""

import re
from typing import Optional

from finance_hub.models import Institution, TransactionType, ParsedTransaction, NotificationPayload
from finance_hub.parser.base import BaseInstitutionParser, parse_amount_idr, parse_datetime_id
from finance_hub.classifier import classify_transaction


class GoPayParser(BaseInstitutionParser):
    institution = Institution.GOPAY

    def can_parse(self, payload: NotificationPayload) -> bool:
        pkg = (payload.package_name or "").lower()
        title = (payload.title or "").lower()
        txt = payload.text.lower()

        if "gojek" in pkg or "gopay" in pkg:
            return True
        if "gopay" in title or "gojek" in title:
            return True
        if "gopay:" in txt or "gofood" in txt or "gocar" in txt or "goride" in txt:
            return True
        return False

    def parse(self, payload: NotificationPayload, raw_hash: str) -> ParsedTransaction:
        text = payload.text.strip()
        timestamp = parse_datetime_id(text, payload.timestamp)
        amount = parse_amount_idr(text)
        txt_lower = text.lower()

        merchant = "GoPay Merchant"
        account_name = "GoPay Wallet"
        tx_type = TransactionType.EXPENSE
        payment_method = "GOPAY"

        # 1. Terima transfer / Uang masuk (INCOME)
        if "menerima transfer" in txt_lower or "transfer masuk" in txt_lower or "kamu menerima" in txt_lower:
            tx_type = TransactionType.INCOME
            payment_method = "PEER_TO_PEER"
            m_from = re.search(r'dari\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_from:
                merchant = m_from.group(1).strip()
            else:
                merchant = "GoPay Transfer Masuk"

        # 2. Top Up saldo
        elif "top up" in txt_lower or "topup" in txt_lower or "isi saldo" in txt_lower:
            tx_type = TransactionType.TRANSFER
            payment_method = "TOP_UP"
            m_src = re.search(r'melalui\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_src:
                merchant = f"Top Up via {m_src.group(1).strip()}"
            else:
                merchant = "GoPay Top Up"

        # 3. QRIS GoPay
        elif "qris" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "QRIS"
            m_qr = re.search(r'qris\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_qr:
                merchant = m_qr.group(1).strip()

        # 4. GoFood
        elif "gofood" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "GOFOOD"
            m_food = re.search(r'gofood\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_food:
                merchant = f"GoFood: {m_food.group(1).strip()}"
            else:
                merchant = "GoFood Order"

        # 5. GoRide / GoCar
        elif "gocar" in txt_lower or "goride" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "TRANSPORT"
            m_ride = re.search(r'(go(?:car|ride)\s+ke\s+[^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_ride:
                merchant = m_ride.group(1).strip()
            else:
                merchant = "Gojek Ride"

        # 6. Transfer Keluar
        elif "transfer" in txt_lower and ("ke" in txt_lower or "berhasil transfer" in txt_lower):
            tx_type = TransactionType.TRANSFER
            payment_method = "TRANSFER"
            m_trf = re.search(r'ke\s+([^0-9.]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_trf:
                merchant = m_trf.group(1).strip()
            else:
                merchant = "GoPay Transfer"

        # 7. Pembayaran Umum
        elif "pembayaran" in txt_lower or "berhasil dibayar" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "GOPAY"
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
            notes=f"Parsed from GoPay ({payment_method})"
        )

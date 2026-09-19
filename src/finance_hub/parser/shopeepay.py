"""Parser for ShopeePay notifications."""

import re
from typing import Optional

from finance_hub.models import Institution, TransactionType, ParsedTransaction, NotificationPayload
from finance_hub.parser.base import BaseInstitutionParser, parse_amount_idr, parse_datetime_id
from finance_hub.classifier import classify_transaction


class ShopeePayParser(BaseInstitutionParser):
    institution = Institution.SHOPEEPAY

    def can_parse(self, payload: NotificationPayload) -> bool:
        pkg = (payload.package_name or "").lower()
        title = (payload.title or "").lower()
        txt = payload.text.lower()

        if "shopee" in pkg:
            return True
        if "shopeepay" in title or "shopee" in title:
            return True
        if "shopeepay:" in txt or "shopeefood" in txt or "saldo shopeepay" in txt:
            return True
        return False

    def parse(self, payload: NotificationPayload, raw_hash: str) -> ParsedTransaction:
        text = payload.text.strip()
        timestamp = parse_datetime_id(text, payload.timestamp)
        amount = parse_amount_idr(text)
        txt_lower = text.lower()

        merchant = "ShopeePay Merchant"
        account_name = "ShopeePay Wallet"
        tx_type = TransactionType.EXPENSE
        payment_method = "SHOPEEPAY"

        # 1. Terima transfer (INCOME)
        if "menerima transfer" in txt_lower or "transfer masuk" in txt_lower or "kamu menerima" in txt_lower:
            tx_type = TransactionType.INCOME
            payment_method = "PEER_TO_PEER"
            m_from = re.search(r'dari\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_from:
                merchant = m_from.group(1).strip()
            else:
                merchant = "ShopeePay Transfer Masuk"

        # 2. Top Up saldo
        elif "top up" in txt_lower or "topup" in txt_lower or "isi saldo" in txt_lower:
            tx_type = TransactionType.TRANSFER
            payment_method = "TOP_UP"
            m_src = re.search(r'melalui\s+([^0-9]+?)(?:\s+berhasil|\.|$)', text, re.IGNORECASE)
            if m_src:
                merchant = f"Top Up via {m_src.group(1).strip()}"
            else:
                merchant = "ShopeePay Top Up"

        # 3. QRIS ShopeePay
        elif "qris" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "QRIS"
            m_qr = re.search(r'qris\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_qr:
                merchant = m_qr.group(1).strip()

        # 4. ShopeeFood
        elif "shopeefood" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "SHOPEEFOOD"
            m_food = re.search(r'shopeefood\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_food:
                merchant = f"ShopeeFood: {m_food.group(1).strip()}"
            else:
                merchant = "ShopeeFood"

        # 5. Pembayaran pesanan di Shopee
        elif "pesanan di shopee" in txt_lower or "shopee" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "SHOPEE_ECOMMERCE"
            m_order = re.search(r'pembayaran\s+([^0-9]+?)(?:\s+sebesar|\s+Rp|\.|$)', text, re.IGNORECASE)
            if m_order:
                merchant = m_order.group(1).strip()
            else:
                merchant = "Shopee Online Shopping"

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
            notes=f"Parsed from ShopeePay ({payment_method})"
        )

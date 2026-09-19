"""Parser for Bank Mandiri / Livin' by Mandiri notifications."""

import re
from typing import Optional

from finance_hub.models import Institution, TransactionType, ParsedTransaction, NotificationPayload
from finance_hub.parser.base import BaseInstitutionParser, parse_amount_idr, parse_datetime_id
from finance_hub.classifier import classify_transaction


class MandiriParser(BaseInstitutionParser):
    institution = Institution.MANDIRI

    def can_parse(self, payload: NotificationPayload) -> bool:
        pkg = (payload.package_name or "").lower()
        title = (payload.title or "").lower()
        txt = payload.text.lower()

        if "mandiri" in pkg or "livin" in pkg:
            return True
        if "mandiri" in title or "livin" in title:
            return True
        if any(marker in txt for marker in ["livin'", "livin by mandiri", "bank mandiri", "transfer mandiri"]):
            return True
        return False

    def parse(self, payload: NotificationPayload, raw_hash: str) -> ParsedTransaction:
        text = payload.text.strip()
        timestamp = parse_datetime_id(text, payload.timestamp)
        amount = parse_amount_idr(text)
        txt_lower = text.lower()

        merchant = "Mandiri Counterparty"
        account_name = "Mandiri Tabungan"
        tx_type = TransactionType.EXPENSE
        payment_method = "TRANSFER"

        # Check account number if present: "Rek: 13700..."
        rek_match = re.search(r'rek(?:ening)?(?:\s+|:)(\d+)', text, re.IGNORECASE)
        if rek_match:
            account_name = f"Mandiri ***{rek_match.group(1)[-4:]}"

        # 1. Transfer Masuk (INCOME)
        # e.g. "Transfer Masuk dari PT TECH Rp 10.000.000,00 Sukses"
        if "transfer masuk" in txt_lower or "dana masuk" in txt_lower or "terima transfer" in txt_lower:
            tx_type = TransactionType.INCOME
            payment_method = "BI_FAST" if "bi-fast" in txt_lower else "BANK_TRANSFER"
            m_from = re.search(r'dari\s+([^0-9]+?)(?:\s+Rp|\s+sebesar|\.|$)', text, re.IGNORECASE)
            if m_from:
                merchant = m_from.group(1).strip()

        # 2. Transfer Keluar / Antar Rekening
        elif "transfer ke" in txt_lower or "kirim uang" in txt_lower:
            m_to = re.search(r'ke\s+([^0-9]+?)(?:\s+Rp|\s+sebesar|\.|$)', text, re.IGNORECASE)
            if m_to:
                merchant = m_to.group(1).strip()
            if any(k in merchant.lower() for k in ["bibit", "stockbit", "rdn", "investasi"]):
                tx_type = TransactionType.EXPENSE
            else:
                tx_type = TransactionType.TRANSFER
            payment_method = "BI_FAST" if "bi-fast" in txt_lower else "BANK_TRANSFER"

        # 3. QRIS Livin'
        elif "qris" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "QRIS"
            m_qr = re.search(r'qris\s+([^0-9]+?)(?:\s+Rp|\s+sebesar|\.|$)', text, re.IGNORECASE)
            if m_qr:
                merchant = m_qr.group(1).strip()

        # 4. Pembayaran Tagihan (PLN, PDAM, Internet, dll)
        elif "pembayaran" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "BILL_PAYMENT"
            m_pay = re.search(r'pembayaran\s+([^0-9]+?)(?:\s+idpel|\s+no|\s+Rp|\s+sebesar|\d)', text, re.IGNORECASE)
            if m_pay:
                merchant = m_pay.group(1).strip()

        # 5. Top up E-Wallet
        elif "top up" in txt_lower or "topup" in txt_lower:
            tx_type = TransactionType.TRANSFER
            payment_method = "E_WALLET"
            m_top = re.search(r'top\s*up\s+([^0-9]+?)(?:\s+Rp|\s+sebesar|\.|$)', text, re.IGNORECASE)
            if m_top:
                merchant = m_top.group(1).strip()

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
            notes=f"Parsed from Mandiri ({payment_method})"
        )

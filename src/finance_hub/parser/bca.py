"""Parser for Bank Central Asia (BCA) notifications."""

import re
from typing import Optional

from finance_hub.models import Institution, TransactionType, ParsedTransaction, NotificationPayload
from finance_hub.parser.base import BaseInstitutionParser, parse_amount_idr, parse_datetime_id
from finance_hub.classifier import classify_transaction


class BCAParser(BaseInstitutionParser):
    institution = Institution.BCA

    def can_parse(self, payload: NotificationPayload) -> bool:
        pkg = (payload.package_name or "").lower()
        title = (payload.title or "").lower()
        txt = payload.text.lower()

        if "bca" in pkg or "bca" in title:
            return True
        if any(marker in txt for marker in ["m-transfer", "debit bca", "qr m-bca", "bca autodebet", "klikbca"]):
            return True
        return False

    def parse(self, payload: NotificationPayload, raw_hash: str) -> ParsedTransaction:
        text = payload.text.strip()
        timestamp = parse_datetime_id(text, payload.timestamp)
        amount = parse_amount_idr(text)

        # Determine transaction type and merchant
        txt_lower = text.lower()
        merchant = "BCA Counterparty"
        account_name = "BCA Account"
        tx_type = TransactionType.EXPENSE
        payment_method = "DEBIT"

        # Check account number if present: "KE REK 5310294821" or "REK 5310294821"
        rek_match = re.search(r'rek(?:ening)?\s+(\d+)', text, re.IGNORECASE)
        if rek_match:
            account_name = f"BCA ***{rek_match.group(1)[-4:]}"

        # Pattern 1: Transfer Masuk (INCOME)
        # e.g. "TRSF DARI PT TECH BERSAMA Rp 25.000.000,00"
        m_in = re.search(r'trsf\s+dari\s+([^0-9]+?)(?:\s+Rp|\s+sebesar|\s+ke|\d)', text, re.IGNORECASE)
        if m_in or "transfer masuk" in txt_lower or "uang masuk" in txt_lower:
            tx_type = TransactionType.INCOME
            payment_method = "BANK_TRANSFER"
            if m_in:
                merchant = m_in.group(1).strip()
            else:
                m_from = re.search(r'dari\s+([^,]+?)(?:\s+Rp|\s+ke|\.|$)', text, re.IGNORECASE)
                if m_from:
                    merchant = m_from.group(1).strip()

        # Pattern 2: Top Up / Transfer Keluar (TRANSFER)
        elif "topup ke" in txt_lower or "top up" in txt_lower:
            tx_type = TransactionType.TRANSFER
            payment_method = "E_WALLET"
            m_top = re.search(r'topup\s+ke\s+([^0-9]+?)(?:\s+Rp|\s+rek|\d)', text, re.IGNORECASE)
            if m_top:
                merchant = m_top.group(1).strip()
            else:
                merchant = "E-Wallet Top Up"

        # Pattern 3: Transfer ke Rekening / RDN
        elif "trsf ke" in txt_lower or "transfer ke" in txt_lower:
            m_to = re.search(r'tr(?:s)?f\s+ke\s+([^0-9]+?)(?:\s+Rp|\s+rek|\d)', text, re.IGNORECASE)
            if m_to:
                merchant = m_to.group(1).strip()
            if any(k in merchant.lower() for k in ["rdn", "stockbit", "bibit", "investasi"]):
                tx_type = TransactionType.EXPENSE
                payment_method = "BANK_TRANSFER"
            else:
                tx_type = TransactionType.TRANSFER
                payment_method = "BANK_TRANSFER"

        # Pattern 4: QRIS
        elif "qr m-bca" in txt_lower or "qris" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "QRIS"
            m_qr = re.search(r'(?:di|ke)\s+([^0-9]+?)(?:\s+Rp|\s+sebesar|\.|$)', text, re.IGNORECASE)
            if m_qr:
                merchant = m_qr.group(1).strip()

        # Pattern 5: Debit BCA / EDC
        elif "debit bca" in txt_lower or "edc" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "DEBIT"
            m_edc = re.search(r'edc\s+([^0-9]+?)(?:\s+Rp|\s+sebesar|\d)', text, re.IGNORECASE)
            if m_edc:
                merchant = m_edc.group(1).strip()

        # Pattern 6: Autodebet / Tagihan
        elif "autodebet" in txt_lower or "tagihan" in txt_lower:
            tx_type = TransactionType.EXPENSE
            payment_method = "AUTODEBET"
            m_auto = re.search(r'tagihan\s+([^0-9]+?)(?:\s+no|\s+id|\s+Rp|\d)', text, re.IGNORECASE)
            if m_auto:
                merchant = m_auto.group(1).strip()

        # Clean merchant string
        merchant = re.sub(r'^(di|ke|dari)\s+', '', merchant, flags=re.IGNORECASE).strip()
        merchant = merchant.rstrip(' .,:;-')

        # Auto classification
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
            notes=f"Parsed from BCA ({payment_method})"
        )

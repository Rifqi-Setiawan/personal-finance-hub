"""Unit tests for GmailPoller and Gmail ingestion logic."""

import base64
import pytest
from unittest.mock import MagicMock, patch

from finance_hub.models import Institution, TransactionType
from finance_hub.integrations.gmail_poller import (
    GmailPoller,
    decode_gmail_body,
    get_header_value,
)
from finance_hub.storage import StorageManager


def test_decode_gmail_body_direct():
    text = "Jenis Transaksi : QRIS Payment\nNominal : Rp 10.000"
    b64 = base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8")
    payload = {"body": {"data": b64}}
    assert "QRIS Payment" in decode_gmail_body(payload)


def test_decode_gmail_body_multipart():
    text = "Jenis Transaksi : QRIS Payment\nNominal : Rp 25.000"
    b64 = base64.urlsafe_b64encode(text.encode("utf-8")).decode("utf-8")
    payload = {
        "parts": [
            {"mimeType": "text/plain", "body": {"data": b64}}
        ]
    }
    assert "Rp 25.000" in decode_gmail_body(payload)


def test_decode_gmail_body_html_fallback():
    html = "<div><p>Jenis Transaksi : QRIS Payment</p><br/><span>Nominal : Rp 30.000</span></div>"
    b64 = base64.urlsafe_b64encode(html.encode("utf-8")).decode("utf-8")
    payload = {
        "parts": [
            {"mimeType": "text/html", "body": {"data": b64}}
        ]
    }
    decoded = decode_gmail_body(payload)
    assert "QRIS Payment" in decoded
    assert "Rp 30.000" in decoded


def test_get_header_value():
    headers = [
        {"name": "Subject", "value": "Notifikasi Transaksi"},
        {"name": "From", "value": "Mandiri mBanking <noreply@bankmandiri.co.id>"},
        {"name": "Date", "value": "Tue, 3 Jun 2025 19:30:48 +0700"},
    ]
    assert get_header_value(headers, "subject") == "Notifikasi Transaksi"
    assert get_header_value(headers, "FROM") == "Mandiri mBanking <noreply@bankmandiri.co.id>"
    assert get_header_value(headers, "nonexistent") == ""


def test_gmail_poller_unauthenticated():
    storage = StorageManager(db_path=":memory:")
    poller = GmailPoller(storage_manager=storage)

    with patch("finance_hub.integrations.gmail_poller.get_gmail_credentials", return_value=None):
        assert not poller.is_authenticated()
        res = poller.poll_recent_transactions()
        assert res["status"] == "unauthenticated"
        assert res["saved_count"] == 0


def test_gmail_poller_mock_success():
    storage = StorageManager(db_path=":memory:")
    mock_sheets = MagicMock()
    mock_sheets.is_configured.return_value = False
    mock_notifier = MagicMock()
    mock_notifier.is_configured.return_value = False

    poller = GmailPoller(
        storage_manager=storage,
        sheets_sync=mock_sheets,
        telegram_notifier=mock_notifier,
    )

    sample_body = """
    Notifikasi Transaksi
    Yth. Nasabah Mandiri,
    Jenis Transaksi : QRIS Payment
    Tanggal : 03/06/2025
    Jam : 19:30:48
    Nominal : Rp 15.000,00
    No. Rekening : 1560017****80
    Merchant : KOPI KENANGAN
    Status : Berhasil
    No. Referensi : 9988112233
    """
    b64 = base64.urlsafe_b64encode(sample_body.encode("utf-8")).decode("utf-8")

    mock_msg_meta = {"id": "msg_001"}
    mock_msg_full = {
        "id": "msg_001",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Notifikasi Transaksi"},
                {"name": "From", "value": "Mandiri mBanking <noreply@bankmandiri.co.id>"},
                {"name": "Date", "value": "Tue, 3 Jun 2025 19:30:48 +0700"},
                {"name": "Message-ID", "value": "<test-msg-001@bankmandiri.co.id>"},
            ],
            "body": {"data": b64},
        },
    }

    mock_service = MagicMock()
    mock_service.users().messages().list().execute.return_value = {"messages": [mock_msg_meta]}
    mock_service.users().messages().get().execute.return_value = mock_msg_full

    mock_creds = MagicMock()
    mock_creds.valid = True

    with patch("finance_hub.integrations.gmail_poller.get_gmail_credentials", return_value=mock_creds), \
         patch("finance_hub.integrations.gmail_poller.build", return_value=mock_service):

        # First run: should save 1 transaction
        res = poller.poll_recent_transactions(sync_sheets=False, notify_telegram=False)
        assert res["status"] == "success"
        assert res["saved_count"] == 1
        assert res["duplicate_count"] == 0

        # Check DB
        assert storage.get_transaction_count() == 1
        txs = storage.get_recent_transactions()
        assert txs[0]["destination_merchant"] == "KOPI KENANGAN"
        assert txs[0]["amount"] == 15000.0

        # Second run: should detect duplicate and skip
        res2 = poller.poll_recent_transactions(sync_sheets=False, notify_telegram=False)
        assert res2["saved_count"] == 0
        assert res2["duplicate_count"] == 1
        assert storage.get_transaction_count() == 1

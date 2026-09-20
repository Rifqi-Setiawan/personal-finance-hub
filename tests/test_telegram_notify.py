"""Unit and integration tests for Telegram Notification system in Personal Finance Hub."""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from finance_hub.models import (
    ParsedTransaction,
    TransactionType,
    Institution,
    CategoryBucket,
)
from finance_hub.integrations.telegram_notify import TelegramNotifier, format_idr
from finance_hub.server import create_app
from finance_hub.storage import StorageManager
from finance_hub.integrations.sheets_sync import GoogleSheetsSync


@pytest.fixture
def sample_tx():
    return ParsedTransaction(
        raw_hash="a1b2c3d4e5f67890",
        source_institution=Institution.MANDIRI,
        transaction_type=TransactionType.EXPENSE,
        amount=50000.0,
        merchant="Bensin Pertamina",
        category="Transportation",
        account_name="Mandiri mBanking",
        timestamp="2026-09-20T14:30:00+07:00",
        raw_text="Pembayaran Rp 50.000 ke SPBU Pertamina berhasil",
        budget_bucket=CategoryBucket.NEEDS,
        notes="Isi Pertamax",
    )


class TestTelegramNotifierFormatting:
    def test_format_idr(self):
        assert format_idr(50000.0) == "Rp 50.000"
        assert format_idr(1250000.0) == "Rp 1.250.000"
        assert format_idr(0.0) == "Rp 0"

    def test_format_expense_message(self, sample_tx):
        notifier = TelegramNotifier(bot_token="fake:token", chat_id="123456")
        cashflow = {
            "formatted_net_remaining": "Rp 450.000",
            "formatted_expense": "Rp 250.000",
        }
        msg = notifier.format_transaction_message(sample_tx, cashflow=cashflow)

        assert "Pengeluaran Baru Dicatat!" in msg
        assert "-Rp 50.000" in msg
        assert "MANDIRI" in msg
        assert "Bensin Pertamina" in msg
        assert "Transportation (NEEDS)" in msg
        assert "Isi Pertamax" in msg
        assert "Rp 450.000" in msg

    def test_format_income_message(self):
        tx = ParsedTransaction(
            raw_hash="income1234",
            source_institution=Institution.BCA,
            transaction_type=TransactionType.INCOME,
            amount=2000000.0,
            merchant="PT Tech Nusantara",
            category="Income",
            account_name="BCA Utama",
            timestamp="2026-09-20T08:00:00+07:00",
            raw_text="Transfer masuk Rp 2.000.000",
            budget_bucket=CategoryBucket.INCOME,
        )
        notifier = TelegramNotifier(bot_token="fake:token", chat_id="123456")
        msg = notifier.format_transaction_message(tx)

        assert "Pemasukan Baru Dicatat!" in msg
        assert "+Rp 2.000.000" in msg
        assert "PT Tech Nusantara" in msg


class TestTelegramNotifierDelivery:
    def test_send_success(self, sample_tx):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen = MagicMock(return_value=mock_resp)

        notifier = TelegramNotifier(
            bot_token="secret_token_123",
            chat_id="6688676936",
            urlopen=mock_urlopen,
        )

        assert notifier.is_configured() is True
        res = notifier.send_transaction_alert(sample_tx)
        assert res is True
        assert mock_urlopen.call_count == 1

    def test_send_not_configured(self, sample_tx):
        notifier = TelegramNotifier(bot_token="", chat_id="")
        assert notifier.is_configured() is False
        assert notifier.send_transaction_alert(sample_tx) is False

    def test_send_disabled(self, sample_tx):
        notifier = TelegramNotifier(
            bot_token="tok", chat_id="123", enabled=False
        )
        assert notifier.is_configured() is False
        assert notifier.send_transaction_alert(sample_tx) is False

    def test_token_redaction(self):
        notifier = TelegramNotifier(bot_token="super_secret_12345", chat_id="123")
        err = "HTTP 401: Unauthorized for url https://api.telegram.org/botsuper_secret_12345/sendMessage"
        redacted = notifier._redact_token(err)
        assert "super_secret_12345" not in redacted
        assert "[REDACTED]" in redacted


class TestServerTelegramWebhookIntegration:
    def test_webhook_triggers_telegram_background(self):
        storage = StorageManager(db_path=":memory:")
        mock_sheets = MagicMock(spec=GoogleSheetsSync)
        mock_sheets.is_configured.return_value = False

        mock_notifier = MagicMock(spec=TelegramNotifier)
        mock_notifier.enabled = True
        mock_notifier.is_configured.return_value = True
        mock_notifier.send_transaction_alert.return_value = True
        mock_notifier.chat_id = "12345"
        mock_notifier.bot_token = "tok"

        app = create_app(
            storage_manager=storage,
            sheets_sync=mock_sheets,
            telegram_notifier=mock_notifier,
        )

        payload = {
            "package_name": "com.bca",
            "title": "m-BCA",
            "text": "m-Transfer: 20/09 10:14 TRSF DARI PT TECH Rp 1.500.000,00 KE REK 5310294821",
            "timestamp": "2026-09-20T10:15:00",
            "source_device": "Samsung Galaxy S24",
        }

        with TestClient(app) as client:
            resp = client.post("/webhook/transaction", json=payload)
            assert resp.status_code == 200

            # Verify notifier was called in background
            assert mock_notifier.send_transaction_alert.call_count == 1
            call_tx = mock_notifier.send_transaction_alert.call_args[0][0]
            assert call_tx.amount == 1500000.0

            # Verify status endpoint
            st_resp = client.get("/api/telegram-status")
            assert st_resp.status_code == 200

        storage.close()

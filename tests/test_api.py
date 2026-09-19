"""Integration tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient

from finance_hub.server import create_app
from finance_hub.storage import StorageManager


@pytest.fixture
def test_app():
    storage = StorageManager(db_path=":memory:")
    app = create_app(storage_manager=storage)
    with TestClient(app) as client:
        yield client
    storage.close()


class TestAPIEndpoints:
    def test_health_endpoint(self, test_app):
        response = test_app.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["engine_version"] == "2.0.0"
        assert data["transaction_count"] == 0
        assert data["db_status"] == "connected"

    def test_webhook_transaction_success(self, test_app):
        payload = {
            "package_name": "com.bca",
            "title": "m-BCA",
            "text": "m-Transfer: 01/09 07:14 TRSF DARI PT TECH NUSANTARA Rp 25.000.000,00 KE REK 5310294821",
            "timestamp": "2026-09-01T07:15:00",
            "source_device": "Samsung Galaxy S24"
        }
        response = test_app.post("/webhook/transaction", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["source_institution"] == "BCA"
        assert data["transaction_type"] == "INCOME"
        assert data["amount"] == 25000000.0
        assert "PT TECH NUSANTARA" in data["merchant"].upper()
        assert "raw_hash" in data

        # Check that transaction is counted in health endpoint
        h_res = test_app.get("/health")
        assert h_res.json()["transaction_count"] == 1

    def test_webhook_transaction_duplicate_ignored(self, test_app):
        payload = {
            "package_name": "com.gojek.app",
            "title": "GoPay",
            "text": "GoPay: 04/09 09:12 Pembayaran QRIS Kopi Kenangan Menara Astra Rp 48.000 Berhasil",
            "timestamp": "2026-09-04T09:12:00"
        }

        # 1st call
        res1 = test_app.post("/webhook/transaction", json=payload)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["amount"] == 48000.0
        assert "raw_hash" in data1

        # 2nd call with same payload -> must be ignored as duplicate
        res2 = test_app.post("/webhook/transaction", json=payload)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["status"] == "duplicate_ignored"
        assert data2["raw_hash"] == data1["raw_hash"]

        # Health endpoint should still report only 1 transaction
        h_res = test_app.get("/health")
        assert h_res.json()["transaction_count"] == 1

    def test_parse_test_dry_run(self, test_app):
        req_data = {
            "text": "Bank Jago: 08/09 03:00 Kantong Utama Debit Netflix Premium Rp 186.000 Berhasil",
            "package_name": "com.jago.app",
            "title": "Bank Jago"
        }
        response = test_app.post("/api/parse-test", json=req_data)
        assert response.status_code == 200
        data = response.json()
        assert data["source_institution"] == "JAGO"
        assert data["amount"] == 186000.0
        assert "NETFLIX" in data["merchant"].upper()

        # Check that database count is still 0 (dry run does not persist)
        h_res = test_app.get("/health")
        assert h_res.json()["transaction_count"] == 0

    def test_get_transactions_endpoint(self, test_app):
        # Ingest 2 transactions
        p1 = {
            "package_name": "id.dana",
            "title": "DANA",
            "text": "DANA Protection: 09/09 15:40 QRIS Indomaret Snack & Minuman Rp 54.000 Berhasil"
        }
        p2 = {
            "package_name": "ovo.id",
            "title": "OVO",
            "text": "OVO Cash: 14/09 16:30 Transaksi QRIS Fore Coffee Menara Mandiri Rp 35.000 Berhasil"
        }
        test_app.post("/webhook/transaction", json=p1)
        test_app.post("/webhook/transaction", json=p2)

        response = test_app.get("/api/transactions?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["transactions"]) == 2
        assert data["limit"] == 10
        assert data["offset"] == 0

    def test_summary_endpoint(self, test_app):
        # Ingest income and expense
        p_inc = {
            "package_name": "com.bca",
            "text": "m-Transfer: 01/09 07:14 TRSF DARI PT TECH BERSAMA Rp 10.000.000,00"
        }
        p_exp = {
            "package_name": "id.bmri.livin",
            "text": "Livin' Mandiri: 02/09 14:15 PEMBAYARAN PLN PASCA IDPEL 53210984 Rp 850.000,00 SUKSES"
        }
        test_app.post("/webhook/transaction", json=p_inc)
        test_app.post("/webhook/transaction", json=p_exp)

        response = test_app.get("/api/summary")
        assert response.status_code == 200
        summary = response.json()
        assert summary["total_income"] == 10000000.0
        assert summary["needs_expense"] == 850000.0
        assert summary["total_transactions"] == 2

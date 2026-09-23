from unittest.mock import patch, MagicMock
from finance_hub.laya_guard import audit_transaction_anomaly, HIGH_EXPENSE_ALERT_THRESHOLD_IDR


def test_audit_zero_amount():
    is_anomaly, score, reason = audit_transaction_anomaly(0.0, "beli gorengan 0", "Food & Dining")
    assert is_anomaly is True
    assert score == 1.0


def test_audit_high_expense_anomaly():
    is_anomaly, score, reason = audit_transaction_anomaly(
        HIGH_EXPENSE_ALERT_THRESHOLD_IDR + 10_000, "beli gadget mahal", "Shopping & Discretionary"
    )
    assert is_anomaly is True
    assert score == 0.85
    assert "melampaui batas kewajaran harian" in reason


def test_audit_rent_not_flagged_as_anomaly():
    # Rent is expected to be high (e.g. 1jt) and should not trigger an anomaly
    is_anomaly, score, reason = audit_transaction_anomaly(
        1_000_000.0, "bayar kosan", "Rent & Housing"
    )
    assert is_anomaly is False


@patch("urllib.request.urlopen")
def test_audit_laya_semantic_check(mock_urlopen):
    # Mock Laya response
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b'{"data": {"answers": {"intent": {"choice": "keuangan", "probabilities": {"keuangan": 0.95, "bukan_keuangan": 0.05}}}}}'
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    is_anomaly, score, reason = audit_transaction_anomaly(
        25_000.0, "beli bakso 25rb cash", "Food & Dining"
    )
    assert is_anomaly is False
    assert score == 0.0

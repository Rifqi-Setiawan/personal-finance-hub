"""Tests for the Personal Finance Hub command-line interface (CLI)."""

import pytest
from unittest.mock import patch
from finance_hub.cli import main, cmd_parse_text


def test_cmd_parse_text_stdout(capsys):
    """Test cmd_parse_text prints expected fields."""
    cmd_parse_text(
        text="Pembayaran QRIS Rp 50.000 di Kopi Tuku berhasil",
        package_name="com.android.generic",
        title="Payment Notification"
    )
    captured = capsys.readouterr().out
    assert "PERSONAL FINANCE HUB" in captured
    assert "Package        : com.android.generic" in captured
    assert "Title          : Payment Notification" in captured
    assert "Payment Method : QRIS" in captured
    assert "Merchant/Party : Kopi Tuku" in captured
    assert "Rp 50.000" in captured


def test_cli_parse_text_with_package_and_title(capsys):
    """Test CLI simulation of notification with --package and --title flags."""
    test_args = [
        "finance_hub.cli",
        "parse-text",
        "Transfer berhasil ke 1234567890 Rp 250.000",
        "--package", "com.bca",
        "--title", "m-BCA"
    ]
    with patch("sys.argv", test_args):
        main()

    captured = capsys.readouterr().out
    assert "PERSONAL FINANCE HUB" in captured
    assert "Package        : com.bca" in captured
    assert "Title          : m-BCA" in captured
    assert "Institution    : BCA" in captured
    assert "Rp 250.000" in captured


def test_cli_parse_text_short_flags(capsys):
    """Test CLI short flags -p and -t."""
    test_args = [
        "finance_hub.cli",
        "parse-text",
        "Transfer masuk dari PT Maju Rp 5.000.000",
        "-p", "id.dana",
        "-t", "DANA"
    ]
    with patch("sys.argv", test_args):
        main()

    captured = capsys.readouterr().out
    assert "Package        : id.dana" in captured
    assert "Title          : DANA" in captured
    assert "Institution    : DANA" in captured

"""Unit tests for MandiriEmailParser."""

import pytest
from finance_hub.models import TransactionType, CategoryBucket, Institution
from finance_hub.parser.mandiri_email import (
    MandiriEmailParser,
    parse_mandiri_email_amount,
    parse_mandiri_email_datetime,
    extract_mandiri_email_fields,
)


def test_parse_mandiri_email_amount():
    assert parse_mandiri_email_amount("Rp 15.000,00") == 15000.0
    assert parse_mandiri_email_amount("Rp 2.500.000,50") == 2500000.5
    assert parse_mandiri_email_amount("15.000") == 15000.0
    assert parse_mandiri_email_amount("Rp 50000") == 50000.0
    assert parse_mandiri_email_amount("invalid") == 0.0


def test_parse_mandiri_email_datetime():
    dt1 = parse_mandiri_email_datetime("03/06/2025", "19:30:48")
    assert dt1 == "2025-06-03T19:30:48"

    dt2 = parse_mandiri_email_datetime("3 Juni 2025", "10:15")
    assert dt2 == "2025-06-03T10:15:00"

    dt3 = parse_mandiri_email_datetime("15-08-2025")
    assert dt3 == "2025-08-15T00:00:00"


def test_extract_mandiri_email_fields():
    text = """
    Jenis Transaksi : QRIS Payment
    Tanggal : 03/06/2025
    Jam : 19:30:48
    Nominal : Rp 15.000,00
    No. Rekening : 1560017****80
    Merchant : TOKO BERKAH JAYA
    Status : Berhasil
    No. Referensi : 2025060319308742
    """
    fields = extract_mandiri_email_fields(text)
    assert fields["jenis_transaksi"] == "QRIS Payment"
    assert fields["tanggal"] == "03/06/2025"
    assert fields["jam"] == "19:30:48"
    assert fields["nominal"] == "Rp 15.000,00"
    assert fields["no_rekening"] == "1560017****80"
    assert fields["merchant"] == "TOKO BERKAH JAYA"
    assert fields["status"] == "Berhasil"
    assert fields["no_referensi"] == "2025060319308742"


def test_mandiri_qris_sample_exact():
    parser = MandiriEmailParser()
    body = """
    Notifikasi Transaksi

    Yth. Nasabah Mandiri,

    Berikut adalah notifikasi transaksi Anda:

    Jenis Transaksi : QRIS Payment
    Tanggal : 03/06/2025
    Jam : 19:30:48
    Nominal : Rp 15.000,00
    No. Rekening : 1560017****80
    Merchant : TOKO BERKAH JAYA
    Status : Berhasil
    No. Referensi : 2025060319308742

    Transaksi ini dilakukan melalui Livin' by Mandiri.
    """
    assert parser.can_parse("Mandiri mBanking <noreply@bankmandiri.co.id>", "Notifikasi Transaksi", body)
    tx = parser.parse("Mandiri mBanking", "Notifikasi Transaksi", body)

    assert tx is not None
    assert tx.source_institution == Institution.MANDIRI
    assert tx.amount == 15000.0
    assert tx.merchant == "TOKO BERKAH JAYA"
    assert tx.payment_method == "QRIS"
    assert tx.transaction_type == TransactionType.EXPENSE
    assert tx.timestamp == "2025-06-03T19:30:48"
    assert tx.account_name == "Mandiri ***80"
    assert "2025060319308742" in tx.notes
    assert tx.budget_bucket == CategoryBucket.WANTS
    assert tx.source_device == "gmail"


def test_mandiri_transfer_masuk():
    parser = MandiriEmailParser()
    body = """
    Notifikasi Transaksi
    Yth. Nasabah Mandiri,

    Jenis Transaksi : Transfer Masuk BI-FAST
    Tanggal : 10/07/2025
    Jam : 09:12:00
    Nominal : Rp 5.000.000,00
    No. Rekening : 1560017****80
    Nama Pengirim : PT KREASI TEKNOLOGI
    Status : Berhasil
    No. Referensi : 998877665544
    """
    tx = parser.parse("Mandiri mBanking", "Notifikasi Transaksi", body)
    assert tx is not None
    assert tx.transaction_type == TransactionType.INCOME
    assert tx.amount == 5000000.0
    assert tx.merchant == "PT KREASI TEKNOLOGI"
    assert tx.payment_method == "BI_FAST"
    assert tx.budget_bucket == CategoryBucket.INCOME


def test_mandiri_transfer_keluar():
    parser = MandiriEmailParser()
    body = """
    Notifikasi Transaksi
    Jenis Transaksi : Transfer BI-FAST
    Tanggal : 12/07/2025
    Jam : 14:00:00
    Nominal : Rp 100.000,00
    No. Rekening : 1560017****80
    Nama Penerima : AHMAD FAUZI
    Status : Berhasil
    No. Referensi : 112233445566
    """
    tx = parser.parse("Mandiri mBanking", "Notifikasi Transaksi", body)
    assert tx is not None
    assert tx.transaction_type == TransactionType.TRANSFER
    assert tx.amount == 100000.0
    assert tx.merchant == "AHMAD FAUZI"


def test_mandiri_transfer_investment():
    parser = MandiriEmailParser()
    body = """
    Notifikasi Transaksi
    Jenis Transaksi : Transfer Antar Bank
    Tanggal : 15/07/2025
    Jam : 10:00:00
    Nominal : Rp 500.000,00
    No. Rekening : 1560017****80
    Nama Penerima : BIBIT REKSADANA
    Status : Berhasil
    No. Referensi : 334455667788
    """
    tx = parser.parse("Mandiri mBanking", "Notifikasi Transaksi", body)
    assert tx is not None
    assert tx.transaction_type == TransactionType.EXPENSE
    assert tx.budget_bucket == CategoryBucket.SAVINGS_INVESTMENTS


def test_mandiri_failed_status_ignored():
    parser = MandiriEmailParser()
    body = """
    Notifikasi Transaksi
    Jenis Transaksi : QRIS Payment
    Tanggal : 03/06/2025
    Jam : 19:30:48
    Nominal : Rp 50.000,00
    Merchant : WARUNG KOPI
    Status : Gagal
    """
    tx = parser.parse("Mandiri mBanking", "Notifikasi Transaksi", body)
    assert tx is None

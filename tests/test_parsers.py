"""Unit tests for Indonesian bank & e-wallet notification parsers."""

import pytest
from finance_hub.models import Institution, TransactionType, NotificationPayload, CategoryBucket
from finance_hub.parser.engine import ParserEngine
from finance_hub.parser.base import parse_amount_idr, parse_datetime_id


@pytest.fixture
def engine():
    return ParserEngine()


class TestAmountAndDateHelpers:
    def test_parse_amount_idr_formats(self):
        # Indonesian format with dots as thousands and comma as decimals
        assert parse_amount_idr("Rp 25.000.000,00") == 25000000.0
        assert parse_amount_idr("Rp 1.450.000,00") == 1450000.0
        assert parse_amount_idr("sebesar Rp 45.000") == 45000.0
        assert parse_amount_idr("Rp 64.500") == 64500.0
        assert parse_amount_idr("Rp 1.250") == 1250.0
        assert parse_amount_idr("Rp. 350.000,00") == 350000.0
        assert parse_amount_idr("IDR 100,000.00") == 100000.0
        assert parse_amount_idr("50000") == 50000.0

    def test_promo_and_failed_notifications_ignored(self):
        # Promo messages with numbers should return 0.0
        assert parse_amount_idr("Hubungkan dan transaksi GoPay di Alfagift, dapatkan CASHBACK s.d. 50rb. Yuk, coba sekarang!") == 0.0
        assert parse_amount_idr("Bayar semua tagihan diskon s.d. 15RB. Bayar sekarang👉🏻") == 0.0
        assert parse_amount_idr("Dapat diskon 9RB buat Rifqi Setiawan, langsung bayar Tagihan PLN disini👉🏻") == 0.0
        # Failed notifications with numbers should return 0.0
        assert parse_amount_idr("Gak bisa bayar Rp59.900 ke Spotify pake GoPay karena saldonya kurang. Klik buat top up.") == 0.0

    def test_parse_datetime_id(self):
        res = parse_datetime_id("01/09 07:14", default_ts="2026-09-01T00:00:00")
        assert "2026-09-01T07:14:00" in res
        res2 = parse_datetime_id("2026-09-05 14:30:00")
        assert "2026-09-05T14:30:00" in res2


class TestBCAParser:
    def test_bca_payroll_income(self, engine):
        payload = NotificationPayload(
            package_name="com.bca",
            title="m-BCA",
            text="m-Transfer: 01/09 07:14 TRSF DARI PT TECH NUSANTARA Rp 25.000.000,00 KE REK 5310294821",
            timestamp="2026-09-01T07:15:00"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.BCA
        assert res.transaction_type == TransactionType.INCOME
        assert res.amount == 25000000.0
        assert "PT TECH NUSANTARA" in res.merchant.upper()
        assert res.budget_bucket == CategoryBucket.INCOME

    def test_bca_topup_transfer(self, engine):
        payload = NotificationPayload(
            package_name="com.bca",
            title="m-BCA",
            text="m-Transfer: 01/09 10:30 TOPUP KE GOPAY RIFQI Rp 1.000.000,00 REK 5310294821"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.BCA
        assert res.transaction_type == TransactionType.TRANSFER
        assert res.amount == 1000000.0
        assert "GOPAY" in res.merchant.upper()

    def test_bca_debit_edc_expense(self, engine):
        payload = NotificationPayload(
            package_name="com.bca",
            title="m-BCA",
            text="Debit BCA: 03/09 16:45 EDC INDOMARET FRESH TB SIMATUPANG Rp 1.450.000,00 SUKSES"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.BCA
        assert res.transaction_type == TransactionType.EXPENSE
        assert res.amount == 1450000.0
        assert "INDOMARET" in res.merchant.upper()
        assert res.budget_bucket == CategoryBucket.NEEDS

    def test_bca_qris_expense(self, engine):
        payload = NotificationPayload(
            package_name="com.bca",
            title="m-BCA",
            text="QR m-BCA: 04/09 12:00 Pembayaran di KOPI KENANGAN Rp 35.000,00 Berhasil"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.BCA
        assert res.transaction_type == TransactionType.EXPENSE
        assert res.amount == 35000.0
        assert "KOPI KENANGAN" in res.merchant.upper()
        assert res.budget_bucket == CategoryBucket.WANTS


class TestMandiriParser:
    def test_mandiri_bill_payment(self, engine):
        payload = NotificationPayload(
            package_name="id.bmri.livin",
            title="Livin' by Mandiri",
            text="Livin' Mandiri: 02/09 14:15 PEMBAYARAN PLN PASCA IDPEL 53210984 Rp 850.000,00 SUKSES"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.MANDIRI
        assert res.transaction_type == TransactionType.EXPENSE
        assert res.amount == 850000.0
        assert "PLN" in res.merchant.upper()
        assert res.budget_bucket == CategoryBucket.NEEDS

    def test_mandiri_qris_spbu(self, engine):
        payload = NotificationPayload(
            package_name="id.bmri.livin",
            text="Livin' Mandiri: 12/09 10:10 QRIS SPBU Shell TB Simatupang Rp 350.000,00 Sukses"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.MANDIRI
        assert res.transaction_type == TransactionType.EXPENSE
        assert res.amount == 350000.0
        assert "SHELL" in res.merchant.upper()
        assert res.budget_bucket == CategoryBucket.NEEDS

    def test_mandiri_transfer_inflow(self, engine):
        payload = NotificationPayload(
            package_name="id.bmri.livin",
            text="Transfer Mandiri: 01/09 08:00 Transfer Masuk dari PT TECH Rp 10.000.000,00 Sukses"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.MANDIRI
        assert res.transaction_type == TransactionType.INCOME
        assert res.amount == 10000000.0


class TestBRIParser:
    def test_bri_qris_expense(self, engine):
        payload = NotificationPayload(
            package_name="id.co.bri.brimo",
            title="BRImo",
            text="BRImo: Transaksi QRIS di RM PADANG SEDERHANA sebesar Rp 45.000 berhasil."
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.BRI
        assert res.transaction_type == TransactionType.EXPENSE
        assert res.amount == 45000.0
        assert "PADANG" in res.merchant.upper() or "SEDERHANA" in res.merchant.upper()

    def test_bri_transfer_inflow(self, engine):
        payload = NotificationPayload(
            package_name="id.co.bri.brimo",
            text="BRImo: Transfer masuk dari AHMAD Rp 2.000.000 berhasil."
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.BRI
        assert res.transaction_type == TransactionType.INCOME
        assert res.amount == 2000000.0

    def test_bri_topup_shopeepay(self, engine):
        payload = NotificationPayload(
            package_name="id.co.bri.brimo",
            text="BRImo: Top Up ShopeePay sebesar Rp 150.000 berhasil."
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.BRI
        assert res.transaction_type == TransactionType.TRANSFER
        assert res.amount == 150000.0


class TestBNIParser:
    def test_bni_qris_starbucks(self, engine):
        payload = NotificationPayload(
            package_name="id.co.bni",
            title="BNI Mobile",
            text="BNI Mobile: Pembayaran QRIS di STARBUCKS sebesar Rp 62.000 berhasil."
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.BNI
        assert res.transaction_type == TransactionType.EXPENSE
        assert res.amount == 62000.0
        assert "STARBUCKS" in res.merchant.upper()
        assert res.budget_bucket == CategoryBucket.WANTS

    def test_bni_transfer_inflow(self, engine):
        payload = NotificationPayload(
            package_name="id.co.bni",
            text="BNI Mobile: Transfer masuk dari BAPAK sebesar Rp 1.000.000 berhasil."
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.BNI
        assert res.transaction_type == TransactionType.INCOME
        assert res.amount == 1000000.0


class TestJagoParser:
    def test_jago_subscription_expense(self, engine):
        payload = NotificationPayload(
            package_name="com.jago.app",
            title="Bank Jago",
            text="Bank Jago: 08/09 03:00 Kantong Utama Debit Netflix Premium Rp 186.000 Berhasil"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.JAGO
        assert res.transaction_type == TransactionType.EXPENSE
        assert res.amount == 186000.0
        assert "NETFLIX" in res.merchant.upper()
        assert res.budget_bucket == CategoryBucket.WANTS

    def test_jago_invest_bibit(self, engine):
        payload = NotificationPayload(
            package_name="com.jago.app",
            title="Bank Jago",
            text="Bank Jago: 10/09 11:00 Kantong Investasi Top Up Bibit Reksadana Indeks Rp 3.000.000 Berhasil"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.JAGO
        assert res.amount == 3000000.0
        assert "BIBIT" in res.merchant.upper()
        assert res.budget_bucket == CategoryBucket.SAVINGS_INVESTMENTS

    def test_jago_freelance_inflow(self, engine):
        payload = NotificationPayload(
            package_name="com.jago.app",
            title="Bank Jago",
            text="Bank Jago: 16/09 18:00 Uang Masuk dari PT Kreasi Digital Konsultasi UI/UX Rp 4.500.000"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.JAGO
        assert res.transaction_type == TransactionType.INCOME
        assert res.amount == 4500000.0
        assert res.budget_bucket == CategoryBucket.INCOME


class TestSeaBankParser:
    def test_seabank_tokopedia_purchase(self, engine):
        payload = NotificationPayload(
            package_name="com.seabank.id",
            title="SeaBank",
            text="SeaBank: 13/09 14:50 Transfer Pembayaran Tokopedia Buku & Keyboard Rp 280.000 Berhasil"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.SEABANK
        assert res.transaction_type == TransactionType.EXPENSE
        assert res.amount == 280000.0
        assert "TOKOPEDIA" in res.merchant.upper()

    def test_seabank_emergency_fund(self, engine):
        payload = NotificationPayload(
            package_name="com.seabank.id",
            title="SeaBank",
            text="SeaBank: 17/09 21:00 Alokasi Tabungan Kantong Dana Darurat SeaBank Rp 1.500.000 Berhasil"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.SEABANK
        assert res.amount == 1500000.0
        assert res.budget_bucket == CategoryBucket.SAVINGS_INVESTMENTS

    def test_seabank_daily_interest(self, engine):
        payload = NotificationPayload(
            package_name="com.seabank.id",
            title="SeaBank",
            text="SeaBank: Bunga Harian Tabungan kamu sebesar Rp 1.250 telah dikreditkan."
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.SEABANK
        assert res.transaction_type == TransactionType.INCOME
        assert res.amount == 1250.0
        assert res.budget_bucket == CategoryBucket.INCOME


class TestGoPayParser:
    def test_gopay_kopi_kenangan_qris(self, engine):
        payload = NotificationPayload(
            package_name="com.gojek.app",
            title="GoPay",
            text="GoPay: 04/09 09:12 Pembayaran QRIS Kopi Kenangan Menara Astra Rp 48.000 Berhasil"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.GOPAY
        assert res.transaction_type == TransactionType.EXPENSE
        assert res.amount == 48000.0
        assert "KOPI KENANGAN" in res.merchant.upper()
        assert res.budget_bucket == CategoryBucket.WANTS

    def test_gopay_gocar_transport(self, engine):
        payload = NotificationPayload(
            package_name="com.gojek.app",
            title="GoPay",
            text="GoPay: 05/09 08:30 GoCar ke Pacific Place SCBD Rp 65.000 Berhasil"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.GOPAY
        assert res.transaction_type == TransactionType.EXPENSE
        assert res.amount == 65000.0
        assert res.budget_bucket == CategoryBucket.NEEDS

    def test_gopay_infaq_charity(self, engine):
        payload = NotificationPayload(
            package_name="com.gojek.app",
            title="GoPay",
            text="GoPay: 18/09 11:45 Pembayaran QRIS Infaq Masjid Nurul Iman Rp 100.000 Berhasil"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.GOPAY
        assert res.transaction_type == TransactionType.EXPENSE
        assert res.amount == 100000.0
        assert res.budget_bucket == CategoryBucket.NEEDS

    def test_gopay_p2p_inflow(self, engine):
        payload = NotificationPayload(
            package_name="com.gojek.app",
            title="GoPay",
            text="GoPay: Kamu menerima transfer sebesar Rp 150.000 dari SITI"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.GOPAY
        assert res.transaction_type == TransactionType.INCOME
        assert res.amount == 150000.0


class TestDANAParser:
    def test_dana_indomaret_qris(self, engine):
        payload = NotificationPayload(
            package_name="id.dana",
            title="DANA",
            text="DANA Protection: 09/09 15:40 QRIS Indomaret Snack & Minuman Rp 54.000 Berhasil"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.DANA
        assert res.transaction_type == TransactionType.EXPENSE
        assert res.amount == 54000.0
        assert "INDOMARET" in res.merchant.upper()

    def test_dana_bpjs_payment(self, engine):
        payload = NotificationPayload(
            package_name="id.dana",
            title="DANA",
            text="DANA: Pembayaran tagihan BPJS Kesehatan Rp 70.000 berhasil"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.DANA
        assert res.transaction_type == TransactionType.EXPENSE
        assert res.amount == 70000.0
        assert res.budget_bucket == CategoryBucket.NEEDS


class TestOVOParser:
    def test_ovo_fore_coffee_qris(self, engine):
        payload = NotificationPayload(
            package_name="ovo.id",
            title="OVO",
            text="OVO Cash: 14/09 16:30 Transaksi QRIS Fore Coffee Menara Mandiri Rp 35.000 Berhasil"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.OVO
        assert res.transaction_type == TransactionType.EXPENSE
        assert res.amount == 35000.0
        assert "FORE" in res.merchant.upper()
        assert res.budget_bucket == CategoryBucket.WANTS

    def test_ovo_alfamart(self, engine):
        payload = NotificationPayload(
            package_name="ovo.id",
            title="OVO",
            text="OVO: Pembayaran di Alfamart sebesar Rp 64.500 berhasil."
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.OVO
        assert res.transaction_type == TransactionType.EXPENSE
        assert res.amount == 64500.0
        assert "ALFAMART" in res.merchant.upper()
        assert res.budget_bucket == CategoryBucket.NEEDS


class TestShopeePayParser:
    def test_shopeepay_padang_qris(self, engine):
        payload = NotificationPayload(
            package_name="com.shopee.id",
            title="ShopeePay",
            text="ShopeePay: 06/09 12:35 QRIS Restoran Sederhana Padang Rp 45.000 Sukses"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.SHOPEEPAY
        assert res.transaction_type == TransactionType.EXPENSE
        assert res.amount == 45000.0
        assert "PADANG" in res.merchant.upper() or "SEDERHANA" in res.merchant.upper()

    def test_shopeepay_ecommerce_order(self, engine):
        payload = NotificationPayload(
            package_name="com.shopee.id",
            title="ShopeePay",
            text="ShopeePay: Pembayaran pesanan di Shopee Rp 129.000 berhasil."
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.SHOPEEPAY
        assert res.transaction_type == TransactionType.EXPENSE
        assert res.amount == 129000.0


class TestCashFallback:
    def test_cash_pharmacy_receipt(self, engine):
        payload = NotificationPayload(
            text="Struk Pembelian Tunai Apotek Kimia Farma Resep Vitamin Rp 175.000"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.CASH
        assert res.transaction_type == TransactionType.EXPENSE
        assert res.amount == 175000.0
        assert "KIMIA FARMA" in res.merchant.upper() or "APOTEK" in res.merchant.upper()
        assert res.budget_bucket == CategoryBucket.NEEDS
        assert res.payment_method == "CASH"

    def test_qris_fallback_payment_method(self, engine):
        payload = NotificationPayload(
            text="Pembayaran QRIS sebesar Rp 45.000 di Kopi Kenangan berhasil"
        )
        res = engine.parse(payload)
        assert res.source_institution == Institution.CASH
        assert res.payment_method == "QRIS"
        assert res.amount == 45000.0
        # Merchant should have trailing 'berhasil' cleaned
        assert res.merchant == "Kopi Kenangan"
        assert "berhasil" not in res.merchant.lower()

    def test_merchant_status_word_stripping(self, engine):
        # Test 'sukses'
        p1 = NotificationPayload(text="Transaksi di Warung Nasi Padang sukses sebesar Rp 25.000")
        r1 = engine.parse(p1)
        assert r1.merchant == "Warung Nasi Padang"
        assert "sukses" not in r1.merchant.lower()

        # Test 'settled'
        p2 = NotificationPayload(text="Pembayaran QRIS ke Toko Elektronik Makmur settled Rp 150.000")
        r2 = engine.parse(p2)
        assert r2.merchant == "Toko Elektronik Makmur"
        assert "settled" not in r2.merchant.lower()
        assert r2.payment_method == "QRIS"

        # Test 'selesai'
        p3 = NotificationPayload(text="Pembelian di Kafe Senja selesai Rp 35.000")
        r3 = engine.parse(p3)
        assert r3.merchant == "Kafe Senja"
        assert "selesai" not in r3.merchant.lower()

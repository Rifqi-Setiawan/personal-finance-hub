"""Unit tests for transaction classification and 50/30/20 budget framework mapping."""

import pytest
from finance_hub.classifier import classify_transaction
from finance_hub.models import TransactionType, CategoryBucket


class TestClassifier:
    # ----------------------------------------------------
    # NEEDS (50%)
    # ----------------------------------------------------
    def test_groceries_indomaret(self):
        cat, subcat, bucket = classify_transaction("Indomaret Fresh", "EDC INDOMARET FRESH TB SIMATUPANG Rp 1.450.000", TransactionType.EXPENSE)
        assert bucket == CategoryBucket.NEEDS
        assert cat == "Groceries & Food Supplies"

    def test_groceries_alfamart(self):
        cat, subcat, bucket = classify_transaction("Alfamart", "Pembayaran di Alfamart sebesar Rp 64.500", TransactionType.EXPENSE)
        assert bucket == CategoryBucket.NEEDS
        assert cat == "Groceries & Food Supplies"

    def test_utilities_pln(self):
        cat, subcat, bucket = classify_transaction("PLN Pascabayar", "PEMBAYARAN PLN PASCA IDPEL 53210984 Rp 850.000", TransactionType.EXPENSE)
        assert bucket == CategoryBucket.NEEDS
        assert cat == "Utilities & Bills"

    def test_utilities_internet_indihome(self):
        cat, subcat, bucket = classify_transaction("Indihome", "TAGIHAN INTERNET INDIHOME NO 12249821 Rp 450.000", TransactionType.EXPENSE)
        assert bucket == CategoryBucket.NEEDS
        assert cat == "Utilities & Bills"

    def test_transport_commute_shell(self):
        cat, subcat, bucket = classify_transaction("SPBU Shell", "QRIS SPBU Shell TB Simatupang Rp 350.000", TransactionType.EXPENSE)
        assert bucket == CategoryBucket.NEEDS
        assert cat == "Transportation & Commute"

    def test_transport_commute_gocar(self):
        cat, subcat, bucket = classify_transaction("GoCar", "GoCar ke Pacific Place SCBD Rp 65.000", TransactionType.EXPENSE)
        assert bucket == CategoryBucket.NEEDS
        assert cat == "Transportation & Commute"

    def test_healthcare_pharmacy(self):
        cat, subcat, bucket = classify_transaction("Apotek Kimia Farma", "Apotek Kimia Farma Resep Vitamin Rp 175.000", TransactionType.EXPENSE)
        assert bucket == CategoryBucket.NEEDS
        assert cat == "Healthcare & Pharmacy"

    def test_charity_infaq(self):
        cat, subcat, bucket = classify_transaction("Masjid Nurul Iman", "Pembayaran QRIS Infaq Masjid Nurul Iman Rp 100.000", TransactionType.EXPENSE)
        assert bucket == CategoryBucket.NEEDS
        assert cat == "Family Support & Charity"

    # ----------------------------------------------------
    # WANTS (30%)
    # ----------------------------------------------------
    def test_dining_coffee(self):
        cat, subcat, bucket = classify_transaction("Kopi Kenangan", "QRIS Kopi Kenangan Menara Astra Rp 48.000", TransactionType.EXPENSE)
        assert bucket == CategoryBucket.WANTS
        assert cat == "Dining Out & Cafes"

    def test_dining_restaurant(self):
        cat, subcat, bucket = classify_transaction("Sushi Tei", "EDC Sushi Tei Senayan City Rp 420.000", TransactionType.EXPENSE)
        assert bucket == CategoryBucket.WANTS
        assert cat == "Dining Out & Cafes"

    def test_dining_gofood(self):
        cat, subcat, bucket = classify_transaction("GoFood", "GoFood pesanan Ayam Geprek sebesar Rp 38.000", TransactionType.EXPENSE)
        assert bucket == CategoryBucket.WANTS
        assert cat == "Dining Out & Cafes"

    def test_entertainment_netflix(self):
        cat, subcat, bucket = classify_transaction("Netflix", "Kantong Utama Debit Netflix Premium Rp 186.000", TransactionType.EXPENSE)
        assert bucket == CategoryBucket.WANTS
        assert cat == "Entertainment & Subscriptions"

    def test_shopping_tokopedia(self):
        cat, subcat, bucket = classify_transaction("Tokopedia", "Transfer Pembayaran Tokopedia Buku & Keyboard Rp 280.000", TransactionType.EXPENSE)
        assert bucket == CategoryBucket.WANTS
        assert cat == "Shopping & Retail"

    # ----------------------------------------------------
    # SAVINGS & INVESTMENTS (20%)
    # ----------------------------------------------------
    def test_savings_bibit(self):
        cat, subcat, bucket = classify_transaction("Bibit Reksadana", "Top Up Bibit Reksadana Indeks Rp 3.000.000", TransactionType.EXPENSE)
        assert bucket == CategoryBucket.SAVINGS_INVESTMENTS
        assert cat == "Mutual Funds & Stocks"

    def test_savings_stockbit_transfer(self):
        cat, subcat, bucket = classify_transaction("Stockbit BCA Sekuritas", "TRSF KE RDN STOCKBIT BCA SEKURITAS Rp 2.500.000", TransactionType.TRANSFER)
        assert bucket == CategoryBucket.SAVINGS_INVESTMENTS
        assert cat == "Mutual Funds & Stocks"

    def test_emergency_fund(self):
        cat, subcat, bucket = classify_transaction("Dana Darurat", "Alokasi Tabungan Kantong Dana Darurat SeaBank Rp 1.500.000", TransactionType.EXPENSE)
        assert bucket == CategoryBucket.SAVINGS_INVESTMENTS
        assert cat == "Emergency Fund Reserve"

    def test_crypto_digital_assets(self):
        cat, subcat, bucket = classify_transaction("Tokocrypto", "Deposit IDR Tokocrypto Beli Bitcoin Rp 1.000.000", TransactionType.EXPENSE)
        assert bucket == CategoryBucket.SAVINGS_INVESTMENTS
        assert cat == "Crypto & Digital Assets"

    # ----------------------------------------------------
    # INCOME
    # ----------------------------------------------------
    def test_income_corporate_payroll(self):
        cat, subcat, bucket = classify_transaction("PT Tech Bersama", "TRSF DARI PT TECH BERSAMA Gaji Bulanan Rp 25.000.000", TransactionType.INCOME)
        assert bucket == CategoryBucket.INCOME
        assert cat == "Salary & Compensation"

    def test_income_freelance(self):
        cat, subcat, bucket = classify_transaction("PT Kreasi Digital", "Uang Masuk dari PT Kreasi Digital Konsultasi UI/UX Rp 4.500.000", TransactionType.INCOME)
        assert bucket == CategoryBucket.INCOME
        assert cat == "Freelance & Consulting"

    def test_income_interest(self):
        cat, subcat, bucket = classify_transaction("SeaBank", "Bunga Harian Tabungan kamu sebesar Rp 1.250", TransactionType.INCOME)
        assert bucket == CategoryBucket.INCOME
        assert cat == "Investment Returns"

    # ----------------------------------------------------
    # TRANSFER
    # ----------------------------------------------------
    def test_internal_transfer(self):
        cat, subcat, bucket = classify_transaction("GoPay Rifqi", "TOPUP KE GOPAY RIFQI Rp 1.000.000", TransactionType.TRANSFER)
        assert bucket == CategoryBucket.TRANSFER
        assert cat == "Internal Account Transfer"

"""Smart transaction classification engine mapping transactions to 50/30/20 budget framework."""

from dataclasses import dataclass
from typing import Optional, List, Tuple
import re

from finance_hub.models import CategoryBucket, TransactionType


@dataclass
class CategoryRule:
    category: str
    subcategory: str
    bucket: CategoryBucket
    keywords: List[str]
    priority: int = 10


# Rule definitions with priority weighting (higher priority matched first)
RULES: List[CategoryRule] = [
    # ----------------------------------------------------
    # SAVINGS & INVESTMENTS (20% Framework)
    # ----------------------------------------------------
    CategoryRule(
        category="Mutual Funds & Stocks",
        subcategory="Stocks & Mutual Funds",
        bucket=CategoryBucket.SAVINGS_INVESTMENTS,
        keywords=[
            "bibit", "stockbit", "ajaib", "reksadana", "saham", "rdn",
            "sekuritas", "bca sekuritas", "mandiri sekuritas", "ipot", "bareksa", "indeks"
        ],
        priority=30,
    ),
    CategoryRule(
        category="Emergency Fund Reserve",
        subcategory="Emergency Savings",
        bucket=CategoryBucket.SAVINGS_INVESTMENTS,
        keywords=["dana darurat", "emergency fund", "kantong dana darurat", "tabungan darurat", "alokasi tabungan"],
        priority=30,
    ),
    CategoryRule(
        category="Crypto & Digital Assets",
        subcategory="Cryptocurrency",
        bucket=CategoryBucket.SAVINGS_INVESTMENTS,
        keywords=["tokocrypto", "indodax", "pintu", "binance", "luno", "btc", "bitcoin", "eth", "ethereum", "crypto"],
        priority=30,
    ),
    CategoryRule(
        category="Government Bonds & Gold",
        subcategory="Gold & Bonds",
        bucket=CategoryBucket.SAVINGS_INVESTMENTS,
        keywords=["pluang", "pegadaian", "emas", "antam", "sbn", "sukuk", "ori", "bonds"],
        priority=30,
    ),

    # ----------------------------------------------------
    # NEEDS (50% Framework)
    # ----------------------------------------------------
    CategoryRule(
        category="Groceries & Food Supplies",
        subcategory="Supermarket & Groceries",
        bucket=CategoryBucket.NEEDS,
        keywords=[
            "indomaret", "alfamart", "alfamidi", "supermarket", "hypermart",
            "superindo", "groceries", "sayurbox", "sayur", "beras", "pasar",
            "sembako", "hero", "transmart", "ranch market", "farmers market", "lotte mart", "grandlucky"
        ],
        priority=20,
    ),
    CategoryRule(
        category="Utilities & Bills",
        subcategory="Electricity, Water & Internet",
        bucket=CategoryBucket.NEEDS,
        keywords=[
            "pln", "listrik", "token pln", "pdam", "air", "indihome", "biznet",
            "first media", "myrepublic", "telkomsel", "xl", "indosat", "tri",
            "smartfren", "wifi", "pulsa", "paket data", "tagihan", "pascabayar", "ipl", "pbb",
            "laundry", "cuci baju", "cuci"
        ],
        priority=20,
    ),
    CategoryRule(
        category="Transportation & Commute",
        subcategory="Public Transit & Fuel",
        bucket=CategoryBucket.NEEDS,
        keywords=[
            "spbu", "pertamina", "shell", "bp akr", "pertamax", "pertalite", "solar", "bensin",
            "krl", "mrt", "lrt", "tol", "jasa marga", "gocar", "goride", "grabride",
            "grabcar", "transjakarta", "busway", "kereta", "kai", "parkir",
            "transportasi", "transport", "e-money", "emoney", "flazz", "jaklingko"
        ],
        priority=20,
    ),
    CategoryRule(
        category="Healthcare & Pharmacy",
        subcategory="Medical & Prescriptions",
        bucket=CategoryBucket.NEEDS,
        keywords=[
            "bpjs", "kimia farma", "apotek", "apotik", "k24", "century", "guardian",
            "dokter", "rumah sakit", "rs ", "klinik", "obat", "resep", "vitamin",
            "halodoc", "alodokter", "asuransi", "prudential", "allianz", "manulife"
        ],
        priority=20,
    ),
    CategoryRule(
        category="Housing & Maintenance",
        subcategory="Rent & Repairs",
        bucket=CategoryBucket.NEEDS,
        keywords=["kost", "sewa kost", "sewa rumah", "kontrakan", "apartemen", "renovasi", "service ac", "plumbing", "maintenance"],
        priority=20,
    ),
    CategoryRule(
        category="Family Support & Charity",
        subcategory="Zakat, Infaq & Charity",
        bucket=CategoryBucket.NEEDS,
        keywords=[
            "zakat", "infaq", "sedekah", "donasi", "dompet dhuafa", "kitabisa",
            "masjid", "orang tua", "mama", "papa", "ibu", "ayah", "adik"
        ],
        priority=20,
    ),

    # ----------------------------------------------------
    # WANTS (30% Framework)
    # ----------------------------------------------------
    CategoryRule(
        category="Dining Out & Cafes",
        subcategory="Cafes & Restaurants",
        bucket=CategoryBucket.WANTS,
        keywords=[
            "kopi kenangan", "fore", "starbucks", "janji jiwa", "point coffee",
            "gofood", "grabfood", "shopeefood", "kopi", "coffee", "cafe", "kafe",
            "restoran", "resto", "mcdonald", "mcd", "kfc", "burger king", "sushi tei",
            "bakmi gm", "bakmi", "solaria", "d'cost", "padang", "sederhana", "warung",
            "boba", "chatime", "mixue", "hokben", "marugame", "ramen", "snack & minuman",
            "gorengan", "sarapan", "makan malam", "makan siang", "makan ayam", "ayam"
        ],
        priority=15,
    ),
    CategoryRule(
        category="E-Wallet & Digital Money",
        subcategory="E-Wallet Top-up",
        bucket=CategoryBucket.WANTS,
        keywords=["top up", "topup", "tokap", "isi saldo"],
        priority=18,
    ),
    CategoryRule(
        category="Entertainment & Subscriptions",
        subcategory="Digital Subscriptions & Media",
        bucket=CategoryBucket.WANTS,
        keywords=[
            "netflix", "spotify", "youtube", "chatgpt", "openai", "apple", "itunes",
            "icloud", "playstation", "steam", "bioskop", "cinema xxi", "xxi", "cgv",
            "cinepolis", "disney", "prime video", "game", "nintendo"
        ],
        priority=15,
    ),
    CategoryRule(
        category="Shopping & Retail",
        subcategory="E-Commerce & Apparel",
        bucket=CategoryBucket.WANTS,
        keywords=[
            "tokopedia", "shopee", "lazada", "blibli", "tiktok shop", "uniqlo",
            "zara", "h&m", "ikea", "ace hardware", "gramedia", "buku & keyboard",
            "keyboard", "gadget", "electronics", "fashion", "baju", "sepatu", "buku"
        ],
        priority=15,
    ),
    CategoryRule(
        category="Hobbies & Recreation",
        subcategory="Leisure & Fitness",
        bucket=CategoryBucket.WANTS,
        keywords=["gym", "fitness", "hotel", "staycation", "tiket.com", "traveloka", "liburan", "flight", "futsal", "badminton"],
        priority=15,
    ),
    CategoryRule(
        category="Personal Care & Grooming",
        subcategory="Salon & Skincare",
        bucket=CategoryBucket.WANTS,
        keywords=["barbershop", "potong rambut", "salon", "skincare", "spa", "massage", "facial", "perawatan"],
        priority=15,
    ),

    # ----------------------------------------------------
    # INCOME TAXONOMY
    # ----------------------------------------------------
    CategoryRule(
        category="Salary & Compensation",
        subcategory="Corporate Payroll",
        bucket=CategoryBucket.INCOME,
        keywords=["gaji", "payroll", "salary", "bonus", "thr", "pt tech", "tunjangan", "upah", "pt tech nusantara", "pt tech bersama"],
        priority=25,
    ),
    CategoryRule(
        category="Freelance & Consulting",
        subcategory="Project & Advisory Fees",
        bucket=CategoryBucket.INCOME,
        keywords=["freelance", "konsultasi", "consulting", "project", "honor", "fee", "side job", "kreasi digital", "ui/ux"],
        priority=25,
    ),
    CategoryRule(
        category="Investment Returns",
        subcategory="Dividends & Interest",
        bucket=CategoryBucket.INCOME,
        keywords=["dividen", "dividend", "bunga harian", "imbal hasil", "yield", "bunga tabungan", "profit sharing", "kupon"],
        priority=25,
    ),
    CategoryRule(
        category="Cashback & Gifts",
        subcategory="Promos & Gifts",
        bucket=CategoryBucket.INCOME,
        keywords=["cashback", "refund", "hadiah", "reward", "promo", "uang masuk", "transfer masuk", "diterima"],
        priority=10,
    ),

    # ----------------------------------------------------
    # INTERNAL TRANSFERS
    # ----------------------------------------------------
    CategoryRule(
        category="Internal Account Transfer",
        subcategory="E-Wallet Top-up & Inter-Bank",
        bucket=CategoryBucket.TRANSFER,
        keywords=["top up", "topup", "tokap", "transfer ke", "kirim uang", "saldo gopay", "saldo dana", "saldo ovo", "saldo shopeepay", "rebalance"],
        priority=5,
    ),
]


def _kw_matches(kw: str, text: str) -> bool:
    """Match keyword using whole-word boundary for short words (<=4 chars) to prevent false positives."""
    if len(kw) <= 4:
        return bool(re.search(r'\b' + re.escape(kw) + r'\b', text))
    return kw in text


def classify_transaction(
    merchant: str,
    raw_text: str,
    transaction_type: TransactionType
) -> Tuple[str, Optional[str], CategoryBucket]:
    """
    Classify a transaction into category, subcategory, and 50/30/20 budget bucket.
    
    Returns:
        (category, subcategory, budget_bucket)
    """
    search_space = f"{merchant} {raw_text}".lower()

    # Special handling for explicit transfer types:
    if transaction_type == TransactionType.TRANSFER:
        # Check if it's an investment transfer (e.g. Bibit, Stockbit, Dana Darurat)
        for rule in RULES:
            if rule.bucket == CategoryBucket.SAVINGS_INVESTMENTS:
                for kw in rule.keywords:
                    if _kw_matches(kw, search_space):
                        return rule.category, rule.subcategory, rule.bucket
        return "Internal Account Transfer", "E-Wallet Top-up & Inter-Bank", CategoryBucket.TRANSFER

    # Special handling for explicit income types:
    if transaction_type == TransactionType.INCOME:
        # Check income rules sorted by priority
        income_rules = [r for r in RULES if r.bucket == CategoryBucket.INCOME]
        income_rules.sort(key=lambda r: r.priority, reverse=True)
        for rule in income_rules:
            for kw in rule.keywords:
                if _kw_matches(kw, search_space):
                    return rule.category, rule.subcategory, rule.bucket
        return "Cashback & Gifts", "Other Income", CategoryBucket.INCOME

    # For EXPENSE transactions:
    # Sort all rules by priority descending
    expense_eligible_rules = [r for r in RULES if r.bucket != CategoryBucket.INCOME and r.bucket != CategoryBucket.TRANSFER]
    expense_eligible_rules.sort(key=lambda r: r.priority, reverse=True)

    for rule in expense_eligible_rules:
        for kw in rule.keywords:
            if _kw_matches(kw, search_space):
                return rule.category, rule.subcategory, rule.bucket

    # Fallback for expense:
    return "Dining Out & Cafes", "General Living Expense", CategoryBucket.WANTS

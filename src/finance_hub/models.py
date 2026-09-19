"""Data models and enums for personal finance hub ingestion and processing."""

from enum import Enum
from typing import Optional
import hashlib
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class Institution(str, Enum):
    BCA = "BCA"
    MANDIRI = "MANDIRI"
    BRI = "BRI"
    BNI = "BNI"
    JAGO = "JAGO"
    SEABANK = "SEABANK"
    GOPAY = "GOPAY"
    DANA = "DANA"
    OVO = "OVO"
    SHOPEEPAY = "SHOPEEPAY"
    CASH = "CASH"


class TransactionType(str, Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    TRANSFER = "TRANSFER"


class CategoryBucket(str, Enum):
    NEEDS = "NEEDS"
    WANTS = "WANTS"
    SAVINGS_INVESTMENTS = "SAVINGS_INVESTMENTS"
    INCOME = "INCOME"
    TRANSFER = "TRANSFER"


class NotificationPayload(BaseModel):
    package_name: Optional[str] = Field(default=None, description="Android package name (e.g. com.bca)")
    title: Optional[str] = Field(default=None, description="Notification title")
    text: str = Field(..., description="Notification message body")
    timestamp: Optional[str] = Field(
        default=None,
        description="ISO 8601 or raw datetime string when notification was triggered"
    )
    source_device: Optional[str] = Field(default=None, description="Identifier of the emitting device/channel")


class ParsedTransaction(BaseModel):
    raw_hash: str = Field(..., description="SHA-256 deduplication hash")
    source_institution: Institution = Field(..., description="Detected financial institution")
    transaction_type: TransactionType = Field(..., description="INCOME, EXPENSE, or TRANSFER")
    amount: float = Field(..., ge=0.0, description="Normalized amount in IDR")
    merchant: str = Field(..., description="Merchant name, counterparty, or transaction party")
    category: str = Field(..., description="Standardized category name")
    subcategory: Optional[str] = Field(default=None, description="Granular subcategory")
    account_name: Optional[str] = Field(default=None, description="Account name or wallet reference")
    timestamp: str = Field(..., description="ISO formatted transaction timestamp")
    raw_text: str = Field(..., description="Original raw notification text")
    budget_bucket: Optional[CategoryBucket] = Field(
        default=None,
        description="50/30/20 budget framework bucket (NEEDS, WANTS, SAVINGS_INVESTMENTS, INCOME, TRANSFER)"
    )
    notes: Optional[str] = Field(default=None, description="Additional context or remarks")
    payment_method: Optional[str] = Field(default="UNKNOWN", description="Payment instrument used")
    source_device: Optional[str] = Field(default="mobile", description="Identifier of the emitting device/channel")
    to_account: Optional[str] = Field(default=None, description="Destination account or counterparty for transfers")


def compute_raw_hash(payload: NotificationPayload) -> str:
    """Compute deterministic SHA-256 hash for idempotent transaction ingestion."""
    pkg = (payload.package_name or "").strip().lower()
    ttl = (payload.title or "").strip()
    txt = payload.text.strip()
    ts = (payload.timestamp or "").strip()
    token = f"{pkg}|{ttl}|{txt}|{ts}"
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def compute_text_hash(text: str, timestamp: str = "", institution: str = "") -> str:
    """Compute SHA-256 hash when only raw text is available."""
    token = f"{institution.strip().lower()}||{text.strip()}|{timestamp.strip()}"
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

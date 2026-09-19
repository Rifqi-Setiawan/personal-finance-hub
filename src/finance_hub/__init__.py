"""Personal Finance Hub package."""

from pathlib import Path
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
except ImportError:
    pass

from finance_hub.models import (
    Institution,
    TransactionType,
    CategoryBucket,
    NotificationPayload,
    ParsedTransaction,
    compute_raw_hash,
    compute_text_hash,
)
from finance_hub.classifier import classify_transaction
from finance_hub.storage import StorageManager, get_storage
from finance_hub.parser.engine import ParserEngine, default_engine

__all__ = [
    "Institution",
    "TransactionType",
    "CategoryBucket",
    "NotificationPayload",
    "ParsedTransaction",
    "compute_raw_hash",
    "compute_text_hash",
    "classify_transaction",
    "StorageManager",
    "get_storage",
    "ParserEngine",
    "default_engine",
]

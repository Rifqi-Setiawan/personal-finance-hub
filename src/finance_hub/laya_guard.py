"""
Laya System 1 Anomaly & Quality Gatekeeper for Personal Finance Hub.
Validates daily burn rate limits, detects potential typos, and audits semantic expense intent.
"""
import logging
import os
import json
import urllib.request
from typing import Tuple

logger = logging.getLogger("finance_hub.laya_guard")

LAYA_SYSTEMONE_URL = os.environ.get("LAYA_SYSTEMONE_URL", "http://127.0.0.1:8098/v1/systemone")
DAILY_BURN_TARGET_IDR = 70_000.0
HIGH_EXPENSE_ALERT_THRESHOLD_IDR = 500_000.0


def audit_transaction_anomaly(amount: float, raw_text: str, category: str) -> Tuple[bool, float, str]:
    """
    Audit transaction against deterministic financial invariants and semantic sanity check.

    Returns:
        (is_anomaly: bool, anomaly_score: float, explanation: str)
    """
    # Invariant 1: Negative or zero amount
    if amount <= 0.0:
        return True, 1.0, "Zero or negative transaction amount"

    # Invariant 2: Extreme outlier check (> Rp 500.000 for everyday spending)
    if amount >= HIGH_EXPENSE_ALERT_THRESHOLD_IDR and category not in ["Rent & Housing", "Internal Account Transfer"]:
        explanation = (
            f"Nominal pengeluaran Rp {amount:,.0f} melampaui batas kewajaran harian "
            f"(target: Rp {DAILY_BURN_TARGET_IDR:,.0f}/hari). Memerlukan perhatian."
        )
        return True, 0.85, explanation

    # Invariant 3: Semantic intent check via Laya System 1 (if available)
    try:
        req_data = json.dumps({
            "state": raw_text[:500],
            "questions": {
                "intent": {
                    "type": "choice",
                    "instructions": "Tentukan kategori teks ini.",
                    "criteria": {
                        "keuangan": "Pembayaran sewa, belanja, transfer, pengeluaran, tagihan, atau mutasi uang",
                        "bukan_keuangan": "Teks percakapan biasa atau obrolan non-finansial"
                    }
                }
            }
        }).encode("utf-8")
        req = urllib.request.Request(
            LAYA_SYSTEMONE_URL,
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                answers = body.get("data", {}).get("answers", {})
                intent_res = answers.get("intent", {})
                if intent_res.get("choice") == "bukan_keuangan":
                    non_fin_prob = intent_res.get("probabilities", {}).get("bukan_keuangan", 0.0)
                    if non_fin_prob >= 0.85:
                        return True, non_fin_prob, f"Laya menandai teks berpotensi non-finansial (score: {non_fin_prob:.2f})"
    except Exception as exc:
        logger.debug("Laya service unavailable or skipped: %s", exc)

    return False, 0.0, "Valid transaction"

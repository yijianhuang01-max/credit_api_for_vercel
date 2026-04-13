from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).resolve().parent / "data" / "scorecard_deployment.json"

FEATURE_META: dict[str, dict[str, Any]] = {
    "annual_inc": {
        "name": "Annual Income",
        "description": "The applicant's annual income level.",
        "type": "number",
        "min": 0,
        "max": 1_000_000,
        "step": 1000,
        "default": 72_000,
    },
    "fico_range_low": {
        "name": "FICO Score",
        "description": "The lower bound of the applicant's FICO score range.",
        "type": "number",
        "min": 300,
        "max": 850,
        "step": 1,
        "default": 690,
    },
    "dti": {
        "name": "Debt-to-Income Ratio",
        "description": "Monthly debt burden relative to income.",
        "type": "number",
        "min": 0,
        "max": 100,
        "step": 0.1,
        "default": 16.4,
    },
    "bc_open_to_buy": {
        "name": "Available Card Credit",
        "description": "Available revolving credit across bankcard accounts.",
        "type": "number",
        "min": 0,
        "max": 500_000,
        "step": 100,
        "default": 9_500,
    },
    "avg_cur_bal": {
        "name": "Average Current Balance",
        "description": "Average current balance across all accounts.",
        "type": "number",
        "min": 0,
        "max": 500_000,
        "step": 100,
        "default": 8_200,
    },
    "acc_open_past_24mths": {
        "name": "Accounts Opened in Past 24 Months",
        "description": "Number of accounts opened in the past two years.",
        "type": "number",
        "min": 0,
        "max": 50,
        "step": 1,
        "default": 4,
    },
    "num_actv_rev_tl": {
        "name": "Active Revolving Accounts",
        "description": "Current number of active revolving credit accounts.",
        "type": "number",
        "min": 0,
        "max": 50,
        "step": 1,
        "default": 6,
    },
    "mths_since_recent_inq": {
        "name": "Months Since Recent Inquiry",
        "description": "Months elapsed since the latest credit inquiry.",
        "type": "number",
        "min": 0,
        "max": 120,
        "step": 1,
        "default": 9,
    },
    "grade": {
        "name": "Credit Grade",
        "description": "LendingClub internal grade.",
        "type": "select",
        "options": ["A", "B", "C", "D", "E", "F", "G"],
        "default": "B",
    },
    "term": {
        "name": "Loan Term",
        "description": "Loan duration in months.",
        "type": "select",
        "options": ["36", "60"],
        "default": "36",
    },
    "home_ownership": {
        "name": "Home Ownership",
        "description": "Applicant housing status.",
        "type": "select",
        "options": ["MORTGAGE", "RENT", "OWN", "ANY", "NONE", "OTHER"],
        "default": "RENT",
    },
    "verification_status": {
        "name": "Verification Status",
        "description": "Whether the applicant's income was verified.",
        "type": "select",
        "options": ["Verified", "Source Verified", "Not Verified"],
        "default": "Verified",
    },
    "purpose": {
        "name": "Loan Purpose",
        "description": "Primary reason for the loan application.",
        "type": "select",
        "options": [
            "debt_consolidation",
            "credit_card",
            "home_improvement",
            "other",
            "major_purchase",
            "medical",
            "car",
            "small_business",
            "vacation",
            "moving",
            "house",
            "wedding",
            "renewable_energy",
            "educational",
        ],
        "default": "debt_consolidation",
    },
}

FIELD_ORDER = list(FEATURE_META.keys())


@lru_cache(maxsize=1)
def load_scorecard() -> dict[str, Any]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def calculate_pd(score: float, pdo: float = 20, base_score: float = 600, base_odds: float = 1 / 20) -> float:
    b_value = pdo / math.log(2)
    a_value = base_score + b_value * math.log(base_odds)
    odds = math.exp((a_value - score) / b_value)
    return odds / (1 + odds)


def get_credit_level(score: float, min_score: float, max_score: float) -> dict[str, str]:
    if max_score == min_score:
        return {"label": "Unknown", "color": "#666666"}
    ratio = (score - min_score) / (max_score - min_score)
    if ratio >= 0.9:
        return {"label": "AAA (Excellent)", "color": "#2E8B57"}
    if ratio >= 0.75:
        return {"label": "AA (Very Good)", "color": "#3CB371"}
    if ratio >= 0.6:
        return {"label": "A (Good)", "color": "#1E90FF"}
    if ratio >= 0.4:
        return {"label": "B (Fair)", "color": "#FFA500"}
    if ratio >= 0.2:
        return {"label": "C (Weak)", "color": "#FF6347"}
    return {"label": "D (High Risk)", "color": "#B22222"}


def _match_numeric_rule(value: float, rules: list[dict[str, Any]]) -> tuple[int, str]:
    for index, rule in enumerate(rules):
        is_first = index == 0
        lower_ok = value > rule["min"] or (is_first and value >= rule["min"])
        if lower_ok and value <= rule["max"]:
            return int(rule["points"]), f"({rule['min']}, {rule['max']}]"
    return 0, "Unmatched"


def _match_category_rule(value: str, mapping: dict[str, Any]) -> tuple[int, str]:
    if value in mapping:
        return int(mapping[value]), value
    for raw_key, points in mapping.items():
        if "[" not in raw_key:
            continue
        normalized = raw_key.replace("[", "").replace("]", "").replace("'", "")
        tokens = [token for token in re.split(r"[\s,]+", normalized) if token]
        if value in tokens:
            return int(points), raw_key
    return 0, "Miss/Else"


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    validated: dict[str, Any] = {}
    missing = [field for field in FIELD_ORDER if field not in payload]
    if missing:
        raise ValueError(f"Missing fields: {', '.join(missing)}")

    for field in FIELD_ORDER:
        meta = FEATURE_META[field]
        value = payload[field]
        if meta["type"] == "number":
            try:
                number_value = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Field '{field}' must be numeric.") from exc
            if "min" in meta and number_value < meta["min"]:
                raise ValueError(f"Field '{field}' must be >= {meta['min']}.")
            if "max" in meta and number_value > meta["max"]:
                raise ValueError(f"Field '{field}' must be <= {meta['max']}.")
            validated[field] = int(number_value) if float(number_value).is_integer() else number_value
        else:
            value_str = str(value)
            if value_str not in meta["options"]:
                raise ValueError(
                    f"Field '{field}' must be one of: {', '.join(meta['options'])}."
                )
            validated[field] = value_str
    return validated


def feature_fields() -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for field in FIELD_ORDER:
        entry = {"key": field}
        entry.update(FEATURE_META[field])
        fields.append(entry)
    return fields


def score_application(payload: dict[str, Any]) -> dict[str, Any]:
    config = load_scorecard()
    applicant = validate_payload(payload)
    total_score = int(config["meta"]["base_points"])
    contributions: list[dict[str, Any]] = []

    for feature in FIELD_ORDER:
        rules = config["features"][feature]
        value = applicant[feature]
        if rules["type"] == "numeric":
            points, matched_bin = _match_numeric_rule(float(value), rules["rules"])
        else:
            points, matched_bin = _match_category_rule(str(value), rules["map"])
        total_score += points
        contributions.append(
            {
                "feature": feature,
                "display_name": FEATURE_META[feature]["name"],
                "value": value,
                "points": points,
                "matched_bin": matched_bin,
            }
        )

    contributions_sorted = sorted(contributions, key=lambda item: item["points"])
    negative = [item for item in contributions_sorted if item["points"] < 0][:3]
    positive = [item for item in reversed(contributions_sorted) if item["points"] > 0][:3]

    min_score = int(config["meta"]["theoretical_min"])
    max_score = int(config["meta"]["theoretical_max"])
    pd_value = calculate_pd(total_score)

    return {
        "score": total_score,
        "pd": pd_value,
        "grade": get_credit_level(total_score, min_score, max_score),
        "range": {"min": min_score, "max": max_score},
        "drivers": {"positive": positive, "negative": negative, "all": contributions},
        "model_meta": {
            "base_points": config["meta"]["base_points"],
            "version": config["meta"]["version"],
        },
        "validated_input": applicant,
    }

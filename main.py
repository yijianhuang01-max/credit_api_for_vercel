from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

try:
    from .scoring import feature_fields, load_scorecard, score_application
except ImportError:
    from scoring import feature_fields, load_scorecard, score_application


def _allowed_origins() -> list[str]:
    raw = os.getenv("ALLOW_ORIGINS", "*")
    if raw.strip() == "*":
        return ["*"]
    return [item.strip() for item in raw.split(",") if item.strip()]


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_scorecard()
    yield


app = FastAPI(
    title="Credit Scoring Demo API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    config = load_scorecard()
    return {"status": "ok", "scorecard_version": str(config["meta"]["version"])}


@app.get("/meta")
def meta() -> dict[str, Any]:
    config = load_scorecard()
    return {
        "fields": feature_fields(),
        "range": {
            "min": int(config["meta"]["theoretical_min"]),
            "max": int(config["meta"]["theoretical_max"]),
        },
        "version": str(config["meta"]["version"]),
    }


@app.post("/score")
def score(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return score_application(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

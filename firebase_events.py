from __future__ import annotations

import os
from typing import Any, Dict, List

import firebase_admin
from firebase_admin import credentials, firestore

_db = None


def _init() -> firestore.Client:
    global _db
    if _db:
        return _db
    cred_path = os.getenv("FIREBASE_CREDENTIALS")
    if not cred_path:
        raise RuntimeError("FIREBASE_CREDENTIALS environment variable not set")
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    _db = firestore.client()
    return _db


def is_enabled() -> bool:
    return bool(os.getenv("FIREBASE_CREDENTIALS"))


def load_events(guild_id: str) -> List[Dict[str, Any]]:
    if not is_enabled():
        return []
    db = _init()
    doc = db.collection("guilds").document(guild_id).get()
    if doc.exists:
        return doc.to_dict().get("events", [])
    return []


def save_events(guild_id: str, events: List[Dict[str, Any]]) -> None:
    if not is_enabled():
        return
    db = _init()
    db.collection("guilds").document(guild_id).set({"events": events}, merge=True)

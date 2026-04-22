"""Translation Alignment Viewer — Flask app.

Thin route layer. Business logic lives in translation_core/.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from flask import Flask, render_template

app = Flask(__name__)

# --- Globals (lazy init, ARA pattern) ---
_i18n: dict = {}
_initialized = False
_init_lock = threading.Lock()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def _init() -> None:
    global _i18n, _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        i18n_path = DATA_DIR / "i18n.json"
        if i18n_path.exists():
            _i18n = json.loads(i18n_path.read_text(encoding="utf-8"))
        _initialized = True


def _t(key: str, lang: str = "en") -> str:
    """Tiny i18n lookup; falls back to the key itself."""
    return _i18n.get(lang, {}).get(key, key)


@app.before_request
def _ensure_init() -> None:
    _init()


@app.context_processor
def _inject_helpers() -> dict:
    return {"t": _t}


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", 5020)))

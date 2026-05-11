import json
import logging
from utils.config import SESSION_DIR

log = logging.getLogger(__name__)


def _path(session_id: str):
    return SESSION_DIR / f"{session_id}.json"


def _load_file(session_id: str) -> dict:
    p = _path(session_id)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
            # Support format lama: file berisi list langsung (hanya history)
            if isinstance(data, list):
                return {"history": data, "pending": None}
            return data
        except Exception:
            return {"history": [], "pending": None}
    return {"history": [], "pending": None}


def _save_file(session_id: str, data: dict):
    _path(session_id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'
    )


# ------------------------------------------------------------------
# History
# ------------------------------------------------------------------

def load_history(session_id: str) -> list:
    return _load_file(session_id)["history"]


def save_history(session_id: str, history: list):
    data = _load_file(session_id)
    data["history"] = history
    _save_file(session_id, data)


def trim_history(history: list, max_turns: int = 20) -> list:
    """
    Buang pesan terlama hingga len(history) <= max_turns.
    Selalu buang dari batas giliran 'user' agar urutan pesan tetap valid.
    """
    while len(history) > max_turns:
        removed = False
        for i in range(1, len(history)):
            if history[i].get('role') == 'user':
                history = history[i:]
                removed = True
                break
        if not removed:
            history = history[1:]
    return history


# ------------------------------------------------------------------
# Pending confirmation
# ------------------------------------------------------------------

def load_pending(session_id: str) -> dict | None:
    return _load_file(session_id).get("pending")


def save_pending(session_id: str, pending: dict):
    data = _load_file(session_id)
    data["pending"] = pending
    _save_file(session_id, data)


def clear_pending(session_id: str):
    data = _load_file(session_id)
    data["pending"] = None
    _save_file(session_id, data)

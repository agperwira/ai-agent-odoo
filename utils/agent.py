"""
Core agent logic:
  _llm_call        — kirim pesan ke AI API dengan retry + backoff
  _dispatch        — terjemahkan nama tool → panggilan OdooBackend
  chat_with_agent  — loop utama (load → LLM → tool → LLM → save)
"""

import json
import logging
import time
import requests
from requests.exceptions import Timeout, ConnectionError as ReqConnError

log = logging.getLogger(__name__)

from utils.config       import AI_BASE_URL, AI_HEADERS, AI_MODEL, AI_TIMEOUT, AI_MAX_RETRIES, SYSTEM_MSG
from utils.odoo         import OdooBackend
from utils.tools_schema import TOOLS
from utils.session      import (load_history, save_history, trim_history,
                                load_pending, save_pending, clear_pending)


_odoo = OdooBackend()


# =============================================================================
# LLM
# =============================================================================

class _BadRequestError(Exception):
    """HTTP 400 dari LLM — caller harus reset history."""


def _llm_call(messages: list, use_tools: bool = True) -> dict:
    payload = {"model": AI_MODEL, "messages": messages}
    if use_tools:
        payload["tools"] = TOOLS

    last_err = None
    for attempt in range(1, AI_MAX_RETRIES + 1):
        try:
            res = requests.post(
                f"{AI_BASE_URL}/chat/completions",
                headers=AI_HEADERS,
                json=payload,
                timeout=AI_TIMEOUT,
            )

            if res.status_code == 400:
                raise _BadRequestError("Permintaan tidak valid (400). History sesi akan direset.")
            if res.status_code == 401:
                raise PermissionError("API Key tidak valid atau kadaluarsa (401). Cek AI_API_KEY di .env.")
            if res.status_code == 429:
                wait = 2 ** attempt
                log.warning("Rate limit (429) — tunggu %ss (retry %s/%s)", wait, attempt, AI_MAX_RETRIES)
                time.sleep(wait)
                last_err = RuntimeError("Terlalu banyak permintaan (429). Coba lagi sebentar.")
                continue
            if res.status_code >= 500:
                wait = 2 ** attempt
                log.warning("Server error %s — tunggu %ss (retry %s/%s)", res.status_code, wait, attempt, AI_MAX_RETRIES)
                time.sleep(wait)
                last_err = RuntimeError(f"Server AI sedang bermasalah ({res.status_code}). Coba lagi nanti.")
                continue

            res.raise_for_status()
            return res.json()

        except (Timeout, ReqConnError):
            wait = 2 ** attempt
            log.warning("Koneksi gagal — tunggu %ss (retry %s/%s)", wait, attempt, AI_MAX_RETRIES)
            time.sleep(wait)
            last_err = TimeoutError(f"Koneksi ke AI timeout ({AI_TIMEOUT}s). Cek jaringan.")

        except (ValueError, PermissionError):
            raise

    raise last_err or RuntimeError("LLM call gagal setelah semua retry.")


# =============================================================================
# Tool dispatch registry
# =============================================================================

def _build_registry(o):
    """Return dict {tool_name: callable(args) -> str}."""
    def _lines(args):
        lines = args.get("lines", "[]")
        if isinstance(lines, str):
            try:    lines = json.loads(lines)
            except Exception: lines = []
        return lines

    return {
        # Generic
        "odoo_search_read": lambda a: o.search_read(
            a.get("model"), a.get("domain"), a.get("fields")),

        # Penjualan
        "odoo_get_sales_orders": lambda a: o.get_sales_orders(
            a.get("partner_name"), a.get("state"), a.get("date_from"),
            a.get("date_to"), a.get("limit", 20)),
        "odoo_get_total_revenue":   lambda _: o.get_total_revenue(),
        "odoo_get_sales_summary":   lambda a: o.get_sales_summary(
            a.get("date_from"), a.get("date_to")),
        "odoo_create_sales_order":  lambda a: o.create_sales_order(
            a["partner_id"], a["product_id"], a.get("quantity", 1), a.get("price_unit")),
        "odoo_confirm_sales_order": lambda a: o.confirm_sales_order(a["order_id"]),
        "odoo_top_products":        lambda a: o.top_products(
            a.get("limit", 10), a.get("date_from"), a.get("date_to"), a.get("order_by", "qty")),

        # Pembelian
        "odoo_get_purchase_orders": lambda a: o.get_purchase_orders(
            a.get("partner_name"), a.get("state"), a.get("date_from"),
            a.get("date_to"), a.get("limit", 20)),
        "odoo_create_purchase_order": lambda a: o.create_purchase_order(
            a["partner_id"], a["product_id"], a.get("quantity", 1), a.get("price_unit")),

        # Gudang & Pengiriman
        "odoo_get_stock":    lambda a: o.get_stock(a.get("product_name")),
        "odoo_get_delivery": lambda a: o.get_delivery(
            a.get("partner_name"), a.get("state"), a.get("limit", 10)),

        # Invoice & Pembayaran
        "odoo_create_invoice": lambda a: o.create_invoice(
            a["partner_id"], _lines(a), a.get("invoice_date")),
        "odoo_get_invoice_list": lambda a: o.get_invoice_list(
            a.get("partner_name"), a.get("state"), a.get("limit", 10)),
        "odoo_post_invoice":   lambda a: o.post_invoice(a["invoice_id"]),
        "odoo_register_payment": lambda a: o.register_payment(
            a["invoice_id"], a.get("amount"), a.get("payment_date"), a.get("journal_id")),
        "odoo_get_customer_receivables": lambda a: o.get_customer_receivables(
            a.get("partner_name"), a.get("limit", 10)),

        # Customer & Record umum
        "odoo_create_customer": lambda a: o.create_customer(
            a["name"], a.get("email"), a.get("phone"), a.get("city")),
        "odoo_update_record":   lambda a: o.update_record(
            a["model"], a["record_id"], a["values"]),

        # HR — Karyawan
        "odoo_create_employee": lambda a: o.create_employee(
            a["name"], a.get("job_title"), a.get("department_id"),
            a.get("work_email"), a.get("mobile_phone"), a.get("pin")),
        "odoo_set_employee_pin": lambda a: o.set_employee_pin(a["employee_id"], a["pin"]),
        "odoo_get_employees":    lambda a: o.get_employees(
            a.get("name"), a.get("department"), a.get("limit", 20)),

        # HR — Absensi
        "odoo_get_attendance": lambda a: o.get_attendance(
            a.get("employee_name"), a.get("date_from"), a.get("date_to"), a.get("limit", 50)),
        "odoo_get_attendance_summary": lambda a: o.get_attendance_summary(
            a.get("date_from"), a.get("date_to"), a.get("department")),

        # HR — Cuti
        "odoo_get_leaves": lambda a: o.get_leaves(
            a.get("employee_name"), a.get("state"),
            a.get("date_from"), a.get("date_to"), a.get("limit", 20)),
    }


_REGISTRY = _build_registry(_odoo)


_ERROR_PREFIXES = ("Gagal", "Akses ditolak", "Domain tidak valid", "Tool tidak dikenal",
                   "Format values", "PIN harus", "Record bukan", "Error query")


def _normalize(result) -> str:
    """Bungkus hasil tool ke format {"ok": ..., ...} sebelum dikirim ke LLM."""
    if isinstance(result, str):
        is_err = any(result.startswith(p) for p in _ERROR_PREFIXES)
        payload = {"ok": False, "error": result} if is_err else {"ok": True, "data": result}
    elif isinstance(result, (list, dict)):
        payload = {"ok": True, "data": result}
    else:
        payload = {"ok": True, "data": str(result)}
    return json.dumps(payload, ensure_ascii=False)


def _dispatch(fn_name: str, args: dict) -> str:
    handler = _REGISTRY.get(fn_name)
    if handler is None:
        log.warning("Tool tidak dikenal: %s", fn_name)
        return json.dumps({"ok": False, "error": f"Tool tidak dikenal: {fn_name}"})
    return _normalize(handler(args))


# =============================================================================
# Destructive-action confirmation
# =============================================================================

DESTRUCTIVE_TOOLS = {
    "odoo_create_sales_order",
    "odoo_confirm_sales_order",
    "odoo_create_purchase_order",
    "odoo_create_invoice",
    "odoo_post_invoice",
    "odoo_register_payment",
    "odoo_update_record",
    "odoo_create_customer",
    "odoo_create_employee",
    "odoo_set_employee_pin",
}

_TOOL_LABELS = {
    "odoo_create_sales_order":    "Buat Sales Order",
    "odoo_confirm_sales_order":   "Konfirmasi Sales Order",
    "odoo_create_purchase_order": "Buat Purchase Order",
    "odoo_create_invoice":        "Buat Invoice",
    "odoo_post_invoice":          "Posting Invoice",
    "odoo_register_payment":      "Catat Pembayaran",
    "odoo_update_record":         "Update Record",
    "odoo_create_customer":       "Buat Customer",
    "odoo_create_employee":       "Buat Karyawan",
    "odoo_set_employee_pin":      "Set PIN Karyawan",
}

_CONFIRM_WORDS = {"ya", "iya", "ok", "yes", "lanjut", "konfirmasi", "setuju", "proceed"}


def _is_confirmation(text: str) -> bool:
    return text.strip().lower() in _CONFIRM_WORDS


def _build_summary(tool_calls: list) -> str:
    """Buat ringkasan aksi dari tool_calls tanpa memanggil LLM."""
    lines = ["Saya akan melakukan aksi berikut:\n"]
    for tc in tool_calls:
        fn_name = tc["function"]["name"]
        label   = _TOOL_LABELS.get(fn_name, fn_name)
        try:
            args = json.loads(tc["function"]["arguments"])
        except Exception:
            args = {}
        # Tampilkan argumen utama yang relevan
        detail_parts = []
        for key in ("name", "partner_id", "product_id", "record_id", "model",
                    "invoice_id", "order_id", "employee_id", "amount"):
            if key in args:
                detail_parts.append(f"{key}={args[key]}")
        detail = ", ".join(detail_parts) if detail_parts else str(args)
        lines.append(f"• {label}: {detail}")
    lines.append("\nKetik *ya/ok* untuk melanjutkan, atau pesan lain untuk membatalkan.")
    return "\n".join(lines)


def _execute_tool_calls(tool_calls: list, history: list) -> list:
    """Jalankan semua tool_calls dan tambahkan hasilnya ke history."""
    for tc in tool_calls:
        fn_name = tc["function"]["name"]
        args    = json.loads(tc["function"]["arguments"])
        result  = _dispatch(fn_name, args)
        history.append({
            "tool_call_id": tc["id"],
            "role":         "tool",
            "name":         fn_name,
            "content":      result,
        })
    return history


# =============================================================================
# Chat entry point
# =============================================================================

def chat_with_agent(user_prompt: str, session_id: str = "default") -> str:
    history = load_history(session_id)

    # ------------------------------------------------------------------
    # Cek apakah ada aksi destruktif yang menunggu konfirmasi
    # ------------------------------------------------------------------
    pending = load_pending(session_id)
    if pending:
        if _is_confirmation(user_prompt):
            log.info("Konfirmasi diterima untuk sesi %s — eksekusi pending tool calls", session_id)
            clear_pending(session_id)
            history = pending["history_snapshot"]
            try:
                history = _execute_tool_calls(pending["tool_calls"], history)
                data2   = _llm_call([SYSTEM_MSG] + history, use_tools=False)
                reply   = data2["choices"][0]["message"]["content"]
                history.append({"role": "assistant", "content": reply})
                save_history(session_id, history)
                return f"Agent: {reply}"
            except _BadRequestError as e:
                log.warning("Bad request saat eksekusi pending sesi %s: %s", session_id, e)
                save_history(session_id, [])
                return "Agent: Permintaan tidak valid, history sesi direset. Silakan coba lagi."
            except Exception as e:
                log.error("Eksekusi pending tool calls gagal: %s", e)
                return f"Agent Error: {e}"
        else:
            clear_pending(session_id)
            history.append({"role": "user", "content": user_prompt})
            save_history(session_id, history)
            log.info("Aksi dibatalkan oleh sesi %s", session_id)
            return "Agent: Aksi dibatalkan."

    # ------------------------------------------------------------------
    # Alur normal
    # ------------------------------------------------------------------
    history.append({"role": "user", "content": user_prompt})
    history = trim_history(history)

    try:
        data      = _llm_call([SYSTEM_MSG] + history)
        msg       = data["choices"][0]["message"]
        msg_clean = {k: v for k, v in msg.items() if v is not None}

        if msg.get("tool_calls"):
            tool_calls     = msg["tool_calls"]
            destructive    = [tc for tc in tool_calls if tc["function"]["name"] in DESTRUCTIVE_TOOLS]

            if destructive:
                # Minta konfirmasi — simpan tool_calls ke pending, jangan eksekusi dulu.
                # Ringkasan dibangun secara programatik (bukan LLM) untuk menghindari
                # pengiriman history dengan tool_calls yang belum resolve ke API (→ 400).
                history.append(msg_clean)
                summary = _build_summary(tool_calls)
                save_pending(session_id, {
                    "history_snapshot": history,
                    "tool_calls":       tool_calls,
                })
                save_history(session_id, history)
                log.info("Menunggu konfirmasi sesi %s — tool: %s",
                         session_id, [tc["function"]["name"] for tc in destructive])
                return f"Agent: {summary}"

            # Tidak ada tool destruktif — eksekusi langsung
            history.append(msg_clean)
            history = _execute_tool_calls(tool_calls, history)
            data2   = _llm_call([SYSTEM_MSG] + history, use_tools=False)
            reply   = data2["choices"][0]["message"]["content"]
        else:
            reply = msg["content"]

        history.append({"role": "assistant", "content": reply})
        save_history(session_id, history)
        return f"Agent: {reply}"

    except _BadRequestError as e:
        log.warning("Bad request — reset history sesi %s: %s", session_id, e)
        save_history(session_id, [])
        return "Agent: Permintaan tidak valid, history sesi direset. Silakan coba lagi."
    except PermissionError as e:
        return f"Agent Error: {e}"
    except TimeoutError as e:
        return f"Agent Error: {e}"
    except Exception as e:
        log.error("chat_with_agent error: %s", e)
        return f"Agent Error: {e}"

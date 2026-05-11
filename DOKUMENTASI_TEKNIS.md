# Technical Documentation — Widya Analytics AI Agent for Odoo

> Version: 3.0 | Author: IdeaLab

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Project Structure](#2-project-structure)
3. [Configuration (`utils/config.py`)](#3-configuration)
4. [Odoo Backend (`utils/odoo/`)](#4-odoo-backend)
5. [Tool Schema (`utils/tools_schema.py`)](#5-tool-schema)
6. [Session Management (`utils/session.py`)](#6-session-management)
7. [Agent Core (`utils/agent.py`)](#7-agent-core)
8. [Telegram Bot (`main_telegram.py`)](#8-telegram-bot)
9. [CLI Entry Point (`main.py`)](#9-cli-entry-point)
10. [Full Request Flow](#10-full-request-flow)
11. [Error Handling Reference](#11-error-handling-reference)
12. [Usage Examples](#12-usage-examples)

---

## 1. System Overview

The agent acts as a bridge between a user (CLI or Telegram) and Odoo 17 ERP.  
It uses an LLM with **function calling** to decide which Odoo operation to run, then executes it via XML-RPC and returns a human-readable answer.

```
┌─────────────┐     natural language      ┌──────────────────┐
│  User (CLI) │ ─────────────────────────▶│                  │
│  or         │                           │   utils/agent.py  │
│  Telegram   │ ◀─────────────────────────│  chat_with_agent  │
└─────────────┘     human-readable reply  └────────┬─────────┘
                                                   │
                              ┌────────────────────┼────────────────────┐
                              │                    │                    │
                              ▼                    ▼                    ▼
                     ┌────────────────┐  ┌──────────────────┐  ┌──────────────┐
                     │  SumoPod AI    │  │  utils/odoo/     │  │  sessions/   │
                     │  (LLM + tools) │  │  OdooBackend     │  │  *.json      │
                     └────────────────┘  └────────┬─────────┘  └──────────────┘
                                                  │
                                                  ▼
                                         ┌─────────────────┐
                                         │  Odoo 17 Server │
                                         │  XML-RPC :8069  │
                                         └────────┬────────┘
                                                  │
                                                  ▼
                                         ┌─────────────────┐
                                         │   PostgreSQL 15  │
                                         └─────────────────┘
```

---

## 2. Project Structure

```
sumopod_agent_app/
├── main.py                    # CLI entry point
├── main_telegram.py           # Telegram bot entry point
├── requirements.txt           # Python dependencies
├── .env                       # Credentials (not committed)
├── sessions/                  # Per-user JSON chat history files
└── utils/
    ├── __init__.py
    ├── config.py              # All env vars & constants
    ├── agent.py               # LLM call + dispatch + chat_with_agent
    ├── session.py             # History persistence & trimming
    ├── tools_schema.py        # 22 tool definitions for the LLM
    └── odoo/
        ├── __init__.py        # OdooBackend class (assembles mixins)
        ├── base.py            # OdooBase: XML-RPC connection & helpers
        ├── sales.py           # SalesMixin
        ├── purchase.py        # PurchaseMixin
        ├── inventory.py       # InventoryMixin
        ├── accounting.py      # AccountingMixin
        ├── partner.py         # PartnerMixin
        └── hr.py              # HRMixin
```

---

## 3. Configuration

**File**: `utils/config.py`  
All values are read from `.env` via `python-dotenv`. Nothing is hardcoded.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ODOO_URL` | `http://127.0.0.1:8069` | Odoo server URL |
| `ODOO_DB` | `database` | Odoo database name |
| `ODOO_USER` | — | Odoo login email |
| `ODOO_PASS` | — | Odoo password |
| `AI_BASE_URL` | `https://ai.sumopod.com/v1` | OpenAI-compatible API endpoint |
| `AI_API_KEY` | — | API key |
| `AI_MODEL` | `gpt-4o-mini` | LLM model name |
| `AI_TIMEOUT` | `60` | Per-request timeout in seconds |
| `AI_MAX_RETRIES` | `3` | Max retry attempts on failure |
| `TELEGRAM_TOKEN` | — | Telegram bot token |
| `TELEGRAM_ADMIN_IDS` | — | Comma-separated admin Telegram user IDs |
| `TELEGRAM_ALLOWED_IDS` | — | Comma-separated allowed user IDs |
| `AGENT_TIMEOUT` | `60` | Max seconds a Telegram handler waits for a response |

### Constants exported

```python
ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASS   # Odoo connection
AI_BASE_URL, AI_API_KEY, AI_MODEL          # AI endpoint
AI_TIMEOUT, AI_MAX_RETRIES, AI_HEADERS     # Request settings
SESSION_DIR                                 # pathlib.Path to sessions/
SYSTEM_MSG                                  # System prompt dict for LLM
```

---

## 4. Odoo Backend

### `utils/odoo/base.py` — OdooBase

Foundation class inherited by all mixins.

#### `_connect()`
Authenticates to Odoo via `/xmlrpc/2/common`. Sets `self.uid` and `self.models`.  
Called on `__init__` and automatically on reconnect.

#### `_exec(model, method, args, kwargs=None)`
Calls `execute_kw` on the Odoo XML-RPC object endpoint.  
Auto-reconnects if `self.uid` is `None` before executing.

#### `_parse_domain(raw)`
Normalizes domain input from the LLM:
- String → `ast.literal_eval`
- Double-wrapped `[[...]]` → unwrapped
- Inner lists → converted to tuples for Odoo

#### `_parse_fields(raw)`
Normalizes fields input:
- Comma-separated string `"id,name,email"` → `["id", "name", "email"]`
- Falls back to `["id", "display_name"]`

#### `search_read(model, domain, fields, limit)`
Generic search across any Odoo model. Used directly and by the `odoo_search_read` tool.

---

### `utils/odoo/sales.py` — SalesMixin

| Method | Odoo Model | Description |
|---|---|---|
| `get_total_revenue()` | `sale.order` | `read_group` aggregation of `amount_total` |
| `get_sales_summary(date_from, date_to)` | `sale.order` | Group by `partner_id`, filter by date range |
| `create_sales_order(partner_id, product_id, quantity, price_unit)` | `sale.order` | Create with one order line |
| `confirm_sales_order(order_id)` | `sale.order` | Calls `action_confirm` |
| `top_products(limit, date_from, date_to, order_by)` | `sale.order.line` | `read_group` by `product_id`, sort by qty or revenue |

---

### `utils/odoo/purchase.py` — PurchaseMixin

| Method | Odoo Model | Description |
|---|---|---|
| `create_purchase_order(partner_id, product_id, quantity, price_unit)` | `purchase.order` | Create with one order line |

---

### `utils/odoo/inventory.py` — InventoryMixin

| Method | Odoo Model | Description |
|---|---|---|
| `get_stock(product_name)` | `product.product` | Returns `qty_available` and `virtual_available` |
| `get_delivery(partner_name, state, limit)` | `stock.picking` | Filters `picking_type_code = outgoing` |

---

### `utils/odoo/accounting.py` — AccountingMixin

| Method | Odoo Model | Description |
|---|---|---|
| `create_invoice(partner_id, lines, invoice_date)` | `account.move` | Creates `out_invoice` with line items |
| `get_invoice_list(partner_name, state, limit)` | `account.move` | Filters by `move_type = out_invoice` |
| `post_invoice(invoice_id)` | `account.move` | Calls `action_post` (Draft → Posted) |
| `register_payment(invoice_id, amount, payment_date, journal_id)` | `account.payment.register` | Uses Odoo payment wizard; validates invoice type first |
| `get_customer_receivables(partner_name, limit)` | `account.move.line` | Filters `account_type = asset_receivable`, unreconciled |

**`register_payment` flow:**
1. Read invoice to get `amount_residual` and validate `move_type`
2. Call `action_register_payment` to get wizard context
3. Create `account.payment.register` wizard record
4. Call `action_create_payments` to finalize

---

### `utils/odoo/partner.py` — PartnerMixin

| Method | Odoo Model | Description |
|---|---|---|
| `create_customer(name, email, phone, city)` | `res.partner` | Sets `customer_rank = 1` |
| `update_record(model, record_id, values)` | any | Generic `write` — `values` is parsed from JSON string if needed |

---

### `utils/odoo/hr.py` — HRMixin

| Method | Odoo Model | Description |
|---|---|---|
| `create_employee(name, job_title, department_id, work_email, mobile_phone, pin)` | `hr.employee` | PIN validated as digits-only before write |
| `set_employee_pin(employee_id, pin)` | `hr.employee` | `write({'pin': str(pin)})` — digits-only validation |
| `get_employees(name, department, limit)` | `hr.employee` | Filters `active = True` |
| `get_attendance(employee_name, date_from, date_to, limit)` | `hr.attendance` | Returns `check_in`, `check_out`, `worked_hours` |
| `get_attendance_summary(date_from, date_to, department)` | `hr.attendance` | `read_group` by `employee_id`, sorted by `worked_hours desc` |
| `get_leaves(employee_name, state, date_from, date_to, limit)` | `hr.leave` | Returns leave type, dates, days, status |

---

### `utils/odoo/__init__.py` — OdooBackend

Assembles all mixins via multiple inheritance:

```python
class OdooBackend(
    SalesMixin,
    PurchaseMixin,
    InventoryMixin,
    AccountingMixin,
    PartnerMixin,
    HRMixin,
    OdooBase,        # must be last — provides _exec, _connect
):
    pass
```

**Adding a new module**: Create `utils/odoo/new_module.py` with a mixin class, then add it to the inheritance list.

---

## 5. Tool Schema

**File**: `utils/tools_schema.py`

Defines `TOOLS` — a list of 22 tool definitions sent to the LLM.

### Helper pattern

```python
def _fn(name, description, properties, required=None): ...

_STR  = lambda desc: {"type": "string",  "description": desc}
_INT  = lambda desc: {"type": "integer", "description": desc}
_NUM  = lambda desc: {"type": "number",  "description": desc}
_DATE = lambda desc: {"type": "string",  "description": f"{desc} (format YYYY-MM-DD)"}
```

### All 22 Tools

| # | Tool Name | Module |
|---|---|---|
| 1 | `odoo_search_read` | Generic |
| 2 | `odoo_get_total_revenue` | Sales |
| 3 | `odoo_get_sales_summary` | Sales |
| 4 | `odoo_create_sales_order` | Sales |
| 5 | `odoo_confirm_sales_order` | Sales |
| 6 | `odoo_top_products` | Sales |
| 7 | `odoo_create_purchase_order` | Purchase |
| 8 | `odoo_get_stock` | Inventory |
| 9 | `odoo_get_delivery` | Inventory |
| 10 | `odoo_create_invoice` | Accounting |
| 11 | `odoo_get_invoice_list` | Accounting |
| 12 | `odoo_post_invoice` | Accounting |
| 13 | `odoo_register_payment` | Accounting |
| 14 | `odoo_get_customer_receivables` | Accounting |
| 15 | `odoo_create_customer` | Partner |
| 16 | `odoo_update_record` | Partner |
| 17 | `odoo_create_employee` | HR |
| 18 | `odoo_set_employee_pin` | HR |
| 19 | `odoo_get_employees` | HR |
| 20 | `odoo_get_attendance` | HR |
| 21 | `odoo_get_attendance_summary` | HR |
| 22 | `odoo_get_leaves` | HR |

> **Note on array types**: All array-type parameters are passed as JSON strings (e.g. `lines`, `domain`) to avoid LiteLLM schema validation errors. They are parsed with `json.loads` or `ast.literal_eval` inside `_dispatch`.

---

## 6. Session Management

**File**: `utils/session.py`

Chat history per user is stored in `sessions/<session_id>.json`.

### Functions

#### `load_history(session_id) → list`
Reads the JSON file. Returns `[]` if not found or corrupted.

#### `save_history(session_id, history)`
Writes the list to disk as formatted JSON.

#### `trim_history(history, max_turns=20) → list`
Removes the oldest messages until `len(history) <= max_turns`.  
**Safety rule**: only trims at `role == "user"` boundaries — never cuts mid tool-sequence (`assistant` with `tool_calls` → `tool` results must stay together).

---

## 7. Agent Core

**File**: `utils/agent.py`

### `_llm_call(messages, session_id, use_tools=True) → dict`

Sends a `POST /chat/completions` request to the AI endpoint.

**Retry logic** (exponential backoff up to `AI_MAX_RETRIES`):

| HTTP Status | Action |
|---|---|
| `200` | Return parsed JSON |
| `400` | Reset history → raise `ValueError` (no retry) |
| `401` | Raise `PermissionError` (no retry) |
| `429` | Sleep `2^attempt` seconds → retry |
| `5xx` | Sleep `2^attempt` seconds → retry |
| Timeout / ConnError | Sleep `2^attempt` seconds → retry |

> **Why raw `requests` instead of OpenAI SDK?**  
> SumoPod AI blocks the OpenAI SDK User-Agent header. All calls use `requests.post()` directly.

### `_dispatch(fn_name, args) → str`

Routes the LLM's tool call to the matching `OdooBackend` method.  
Uses Python 3.10 `match/case` for readability.

Special parsing in dispatch:
- `odoo_create_invoice` → `lines` parsed from JSON string
- `odoo_search_read` → domain and fields already normalized by `OdooBase`

### `chat_with_agent(user_prompt, session_id) → str`

Main entry point called by both CLI and Telegram bot.

```
1. load_history(session_id)
2. append user message
3. trim_history()
4. _llm_call #1 — with tools
5. if tool_calls:
       append assistant message (with tool_calls)
       for each tool_call:
           _dispatch → execute → append tool result
       _llm_call #2 — without tools (summarize)
   else:
       use direct reply
6. append assistant reply
7. save_history(session_id)
8. return "Agent: <reply>"
```

Error returns:
- `ValueError` → session was reset, return message without prefix
- `PermissionError` → bad API key
- `TimeoutError` → network issue
- `Exception` → generic error string

---

## 8. Telegram Bot

**File**: `main_telegram.py`

### Access Control

```python
TELEGRAM_ADMIN_IDS   # can manage other users
TELEGRAM_ALLOWED_IDS # can chat with the bot
```

Both are loaded fresh from `.env` on every request (no restart needed after changes).  
`_load_ids(env_key)` parses comma-separated integers.  
`_save_ids(env_key, ids)` writes changes back using `python-dotenv`'s `set_key`.

**Authorization flow**:
```
incoming message
    │
    ▼
is_allowed(user_id)?
    ├─ NO  → _deny() — replies with user's own ID + instructions
    └─ YES → process message
```

### Commands

| Handler | Command | Access |
|---|---|---|
| `cmd_start` | `/start` | Everyone |
| `cmd_myid` | `/myid` | Everyone |
| `cmd_clear` | `/clear` | Allowed users |
| `cmd_adduser` | `/adduser <id>` | Admin only |
| `cmd_removeuser` | `/removeuser <id>` | Admin only |
| `cmd_listusers` | `/listusers` | Admin only |

### Async + Thread Safety

`chat_with_agent` is a blocking function. It runs in a `ThreadPoolExecutor` via `asyncio.wait_for` to prevent blocking the Telegram event loop:

```python
response = await asyncio.wait_for(
    loop.run_in_executor(_executor, chat_with_agent, user_text, session_id),
    timeout=AGENT_TIMEOUT,
)
```

If it exceeds `AGENT_TIMEOUT` seconds, the user gets a friendly timeout message.

---

## 9. CLI Entry Point

**File**: `main.py`

Starts an interactive REPL loop. Session ID is based on the start timestamp.

| Input | Action |
|---|---|
| Any text | `chat_with_agent(text, session_id)` |
| `clear` | `save_history(session_id, [])` |
| `exit` / `quit` / Ctrl+C | Exit loop |

---

## 10. Full Request Flow

```
User: "Tampilkan 5 produk terlaris bulan ini"
│
▼
main.py / main_telegram.py
│
▼
chat_with_agent("Tampilkan 5 produk terlaris bulan ini", session_id)
│
├─ load_history("telegram_123456")          # load dari sessions/telegram_123456.json
├─ append {"role":"user", "content":"..."}
├─ trim_history(max_turns=20)
│
▼
_llm_call([SYSTEM_MSG] + history, use_tools=True)
│
├─ POST /chat/completions
│  model: gpt-4o-mini
│  tools: [22 tool schemas]
│
▼
LLM Response:
{
  "tool_calls": [{
    "function": {
      "name": "odoo_top_products",
      "arguments": '{"limit":5, "date_from":"2026-05-01", "date_to":"2026-05-31", "order_by":"qty"}'
    }
  }]
}
│
▼
_dispatch("odoo_top_products", {"limit":5, ...})
│
▼
OdooBackend.top_products(limit=5, date_from="2026-05-01", ...)
│
├─ XML-RPC → sale.order.line.read_group(...)
├─ returns: [{"product":"Laptop A","total_qty":42,"total_revenue":63000000}, ...]
│
▼
history.append(tool result)
│
▼
_llm_call([SYSTEM_MSG] + history, use_tools=False)   # LLM call #2
│
▼
Final reply: "Berikut 5 produk terlaris bulan Mei 2026: ..."
│
▼
save_history → sessions/telegram_123456.json
│
▼
"Agent: Berikut 5 produk terlaris..."
```

---

## 11. Error Handling Reference

| Error | Where raised | What happens |
|---|---|---|
| Odoo login fails | `OdooBase._connect()` | `self.uid = None`, prints warning |
| Odoo call fails | `OdooBase._exec()` | Raises `ConnectionError` |
| HTTP 400 | `_llm_call()` | Session reset, `ValueError` raised |
| HTTP 401 | `_llm_call()` | `PermissionError` raised (no retry) |
| HTTP 429 | `_llm_call()` | Sleep + retry up to `AI_MAX_RETRIES` |
| HTTP 5xx | `_llm_call()` | Sleep + retry up to `AI_MAX_RETRIES` |
| Network timeout | `_llm_call()` | Sleep + retry → `TimeoutError` |
| Invalid PIN | `HRMixin` methods | Returns error string before Odoo call |
| Invalid JSON in `values` | `PartnerMixin.update_record` | Returns error string |
| Telegram timeout | `handle_message` | `asyncio.TimeoutError` → friendly message |
| Unauthorized Telegram user | `handle_message` | `_deny()` → shows user's own ID |

---

## 12. Usage Examples

### CLI Prompts

```
Anda: Berapa total omzet perusahaan?
Anda: Tampilkan 10 produk terlaris bulan ini berdasarkan revenue
Anda: Cek stok produk Laptop
Anda: Buat sales order untuk customer ID 7, produk ID 12, qty 3
Anda: Konfirmasi sales order ID 45
Anda: Buat invoice untuk customer ID 7 dengan produk ID 12 qty 2 harga 150000
Anda: Posting invoice ID 23
Anda: Catat pembayaran untuk invoice ID 23
Anda: Lihat piutang customer Budi
Anda: Tampilkan semua karyawan departemen IT
Anda: Buat karyawan baru bernama Siti Rahayu, jabatan Staff HR, PIN 1234
Anda: Ganti PIN karyawan ID 15 menjadi 5678
Anda: Tampilkan absensi Budi minggu ini
Anda: Ringkasan jam kerja semua karyawan bulan April
Anda: Tampilkan pengajuan cuti yang masih pending
```

### Telegram Commands

```
/start             → welcome + instructions
/myid              → shows your Telegram user ID
/clear             → reset conversation
/adduser 987654321 → grant access (admin only)
/listusers         → show all allowed users (admin only)
```

# Widya Analytics — Odoo 17 AI Agent

An AI-powered agent that connects a Large Language Model to **Odoo 17 ERP** via XML-RPC.  
Users interact in natural language (Indonesian or English); the agent translates intent into real Odoo actions.

Available as both a **CLI tool** and a **Telegram bot** with per-user access control.

---

## Features

### Sales
| Capability | Tool |
|---|---|
| Total revenue aggregation | `odoo_get_total_revenue` |
| Sales summary by customer & date range | `odoo_get_sales_summary` |
| Create Sales Order | `odoo_create_sales_order` |
| Confirm Sales Order (Draft → Confirmed) | `odoo_confirm_sales_order` |
| Top N best-selling products by qty / revenue | `odoo_top_products` |

### Purchase
| Capability | Tool |
|---|---|
| Create Purchase Order to vendor | `odoo_create_purchase_order` |

### Inventory
| Capability | Tool |
|---|---|
| Check product stock (physical & virtual) | `odoo_get_stock` |
| Check delivery / shipment status | `odoo_get_delivery` |

### Accounting
| Capability | Tool |
|---|---|
| Create customer invoice | `odoo_create_invoice` |
| List invoices (filter by customer / status) | `odoo_get_invoice_list` |
| Post invoice (Draft → Posted) | `odoo_post_invoice` |
| Register payment for an invoice | `odoo_register_payment` |
| View unpaid customer receivables | `odoo_get_customer_receivables` |

### Customer & Records
| Capability | Tool |
|---|---|
| Register new customer | `odoo_create_customer` |
| Update any Odoo record field | `odoo_update_record` |
| Generic search/read from any model | `odoo_search_read` |

### HR & Attendance
| Capability | Tool |
|---|---|
| Create new employee (with kiosk PIN) | `odoo_create_employee` |
| Update employee attendance PIN | `odoo_set_employee_pin` |
| List active employees | `odoo_get_employees` |
| View attendance check-in/check-out log | `odoo_get_attendance` |
| Attendance hours summary per employee | `odoo_get_attendance_summary` |
| View leave / time-off requests | `odoo_get_leaves` |

---

## Project Structure

```
sumopod_agent_app/
├── main.py                    # CLI entry point
├── main_telegram.py           # Telegram bot entry point
├── requirements.txt
├── .env                       # Credentials & config (never commit)
├── sessions/                  # Per-user JSON chat history
└── utils/
    ├── config.py              # Environment variables & constants
    ├── agent.py               # LLM call + tool dispatch + chat loop
    ├── session.py             # History load / save / trim
    ├── tools_schema.py        # 22 tool definitions for the LLM
    └── odoo/
        ├── __init__.py        # OdooBackend (assembles all mixins)
        ├── base.py            # XML-RPC connection + helpers
        ├── sales.py           # Sales module
        ├── purchase.py        # Purchase module
        ├── inventory.py       # Inventory & delivery module
        ├── accounting.py      # Invoice & payment module
        ├── partner.py         # Customer & generic record update
        └── hr.py              # HR, attendance & leave module
```

---

## Setup & Installation

### Requirements
- Python 3.10+
- Odoo 17 running (local or Docker)
- SumoPod AI API key (or any OpenAI-compatible endpoint)
- Telegram Bot token (for the bot interface)

### Install dependencies

```bash
cd sumopod_agent_app
python -m venv venv

# Windows
.\venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Configure `.env`

```env
# Odoo
ODOO_URL=http://127.0.0.1:8069
ODOO_DB=your_database_name
ODOO_USER=admin@example.com
ODOO_PASS=your_password

# AI
AI_BASE_URL=https://ai.sumopod.com/v1
AI_API_KEY=sk-your-api-key
AI_MODEL=gpt-4o-mini
AI_TIMEOUT=60
AI_MAX_RETRIES=3

# Telegram Bot
TELEGRAM_TOKEN=your_bot_token

# Access control — comma-separated Telegram user IDs
# Get your ID by messaging @userinfobot or using /myid
TELEGRAM_ADMIN_IDS=123456789
TELEGRAM_ALLOWED_IDS=123456789,987654321

# Agent response timeout in seconds (Telegram)
AGENT_TIMEOUT=60
```

---

## Running

### CLI
```bash
python main.py
```
Type `clear` to reset the session, `exit` to quit.

### Telegram Bot
```bash
python main_telegram.py
```

---

## Telegram Access Control

| Command | Who | Description |
|---|---|---|
| `/start` | Everyone | Welcome message (shows ID if not authorized) |
| `/myid` | Everyone | Show your Telegram User ID |
| `/clear` | Allowed users | Reset your conversation history |
| `/adduser <id>` | Admin only | Grant access to a user |
| `/removeuser <id>` | Admin only | Revoke access from a user |
| `/listusers` | Admin only | Show all admins and allowed users |

Unauthorized users see their own ID in the rejection message — they can send it to the admin to request access. No manual lookup required.

---

## How It Works

```
User message
    │
    ▼
Load session history (JSON file)
    │
    ▼
LLM Call #1  ──► tool_calls? ──NO──► Reply directly
    │                                      │
   YES                                     │
    │                                      │
    ▼                                      │
Execute Odoo tool(s) via XML-RPC           │
    │                                      │
    ▼                                      │
LLM Call #2 (summarize tool results)       │
    │                                      │
    └──────────────┬────────────────────────┘
                   ▼
           Save history & reply
```

The LLM decides which tool(s) to call. Results are sent back to the LLM for a final human-readable response. Session history is persisted per user in `sessions/<session_id>.json`.

---

## Reliability Features

- **Auto-reconnect** — Odoo connection is re-established automatically if the session drops
- **Retry with backoff** — LLM calls retry up to 3× with exponential backoff (configurable via `AI_MAX_RETRIES`)
- **Per-status error messages** — 400 resets history, 401 alerts on bad key, 429/5xx retries with wait
- **Safe memory trimming** — history is trimmed only at `user` turn boundaries, never mid tool-sequence
- **Async Telegram timeout** — bot handlers run in a thread pool with configurable timeout so the event loop never blocks

---

**Author**: IdeaLab  
**Version**: 3.0.0

"""
Telegram bot wrapper untuk Widya Analytics AI Agent.

Akses kontrol berbasis whitelist Telegram User ID (dari .env):
  TELEGRAM_ADMIN_IDS  — bisa pakai /adduser, /removeuser, /listusers
  TELEGRAM_ALLOWED_IDS — user biasa yang boleh chat
"""

import asyncio
import logging
import os
import pathlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler
from dotenv import load_dotenv, set_key
from utils.agent   import chat_with_agent
from utils.session import save_history

load_dotenv()

TELEGRAM_TOKEN  = os.getenv('TELEGRAM_TOKEN', '')
AGENT_TIMEOUT   = int(os.getenv('AGENT_TIMEOUT', '60'))
ENV_FILE        = pathlib.Path(__file__).parent / '.env'

_executor = ThreadPoolExecutor(max_workers=4)

RATE_LIMIT_SECONDS = float(os.getenv('RATE_LIMIT_SECONDS', '3'))
_last_request: dict[int, float] = {}  # user_id → monotonic timestamp

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
log = logging.getLogger(__name__)


# =============================================================================
# Whitelist — dibaca ulang setiap request agar perubahan .env langsung berlaku
# =============================================================================

def _load_ids(env_key: str) -> set[int]:
    raw = os.getenv(env_key, '')
    ids = set()
    for part in raw.split(','):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids

def _save_ids(env_key: str, ids: set[int]):
    """Tulis ulang daftar ID ke file .env."""
    value = ','.join(str(i) for i in sorted(ids))
    set_key(str(ENV_FILE), env_key, value)
    os.environ[env_key] = value  # update in-process juga

def is_admin(user_id: int) -> bool:
    return user_id in _load_ids('TELEGRAM_ADMIN_IDS')

def is_allowed(user_id: int) -> bool:
    """Admin otomatis dianggap allowed juga."""
    return user_id in _load_ids('TELEGRAM_ALLOWED_IDS') or is_admin(user_id)


# =============================================================================
# Helper
# =============================================================================

def _session_id(update: Update) -> str:
    return f"telegram_{update.effective_user.id}"

def _user_label(update: Update) -> str:
    u = update.effective_user
    return f"@{u.username}" if u.username else u.first_name


async def _deny(update: Update):
    uid = update.effective_user.id
    await update.message.reply_text(
        "Maaf, Anda tidak memiliki akses ke bot ini.\n\n"
        f"Tunjukkan ID berikut ke administrator untuk meminta akses:\n"
        f"`{uid}`",
        parse_mode="Markdown",
    )
    log.warning("Akses ditolak — user %s (%s)", uid, _user_label(update))


# =============================================================================
# Command handlers
# =============================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await _deny(update)
        return
    await update.message.reply_text(
        "Selamat datang di *Widya Analytics Odoo Agent!*\n\n"
        "Saya bisa membantu Anda mencari data dan membuat transaksi di Odoo.\n"
        "Ketik pertanyaan dalam Bahasa Indonesia atau Inggris.\n\n"
        "*Perintah tersedia:*\n"
        "/start — Pesan ini\n"
        "/clear — Hapus riwayat percakapan Anda\n"
        "/myid  — Lihat Telegram User ID Anda",
        parse_mode="Markdown",
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await _deny(update)
        return
    save_history(_session_id(update), [])
    await update.message.reply_text("Riwayat percakapan dihapus. Mulai percakapan baru!")


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Membantu user menemukan ID-nya untuk diberikan ke admin."""
    uid = update.effective_user.id
    await update.message.reply_text(
        f"Telegram User ID Anda: `{uid}`\n"
        "Berikan angka ini ke administrator untuk meminta akses.",
        parse_mode="Markdown",
    )


async def cmd_adduser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /adduser <telegram_id>"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Perintah ini hanya untuk administrator.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Penggunaan: /adduser <telegram_id>")
        return
    new_id = int(context.args[0])
    allowed = _load_ids('TELEGRAM_ALLOWED_IDS')
    allowed.add(new_id)
    _save_ids('TELEGRAM_ALLOWED_IDS', allowed)
    log.info("Admin %s menambahkan user %s", _user_label(update), new_id)
    await update.message.reply_text(f"User `{new_id}` berhasil ditambahkan ke whitelist.", parse_mode="Markdown")


async def cmd_removeuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /removeuser <telegram_id>"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Perintah ini hanya untuk administrator.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Penggunaan: /removeuser <telegram_id>")
        return
    rem_id = int(context.args[0])
    allowed = _load_ids('TELEGRAM_ALLOWED_IDS')
    allowed.discard(rem_id)
    _save_ids('TELEGRAM_ALLOWED_IDS', allowed)
    log.info("Admin %s menghapus user %s", _user_label(update), rem_id)
    await update.message.reply_text(f"User `{rem_id}` dihapus dari whitelist.", parse_mode="Markdown")


async def cmd_listusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /listusers — tampilkan semua ID yang punya akses."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Perintah ini hanya untuk administrator.")
        return
    admins  = _load_ids('TELEGRAM_ADMIN_IDS')
    allowed = _load_ids('TELEGRAM_ALLOWED_IDS')
    lines = ["*Daftar akses bot:*\n"]
    lines.append("*Admin:*")
    lines += [f"  • `{i}`" for i in sorted(admins)] or ["  (kosong)"]
    lines.append("\n*User diizinkan:*")
    lines += [f"  • `{i}`" for i in sorted(allowed)] or ["  (kosong)"]
    await update.message.reply_text('\n'.join(lines), parse_mode="Markdown")


# =============================================================================
# Message handler
# =============================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await _deny(update)
        return

    uid  = update.effective_user.id
    now  = time.monotonic()
    last = _last_request.get(uid, 0)
    if now - last < RATE_LIMIT_SECONDS:
        remaining = RATE_LIMIT_SECONDS - (now - last)
        await update.message.reply_text(
            f"Mohon tunggu {remaining:.1f} detik sebelum mengirim pesan berikutnya."
        )
        return
    _last_request[uid] = now

    user_text  = update.message.text
    session_id = _session_id(update)
    log.info("Pesan dari %s (%s): %s", _user_label(update), uid, user_text)

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(_executor, chat_with_agent, user_text, session_id),
            timeout=AGENT_TIMEOUT,
        )
        await update.message.reply_text(response.removeprefix("Agent: "))

    except asyncio.TimeoutError:
        await update.message.reply_text(
            f"Maaf, permintaan memakan waktu terlalu lama (>{AGENT_TIMEOUT}s). "
            "Silakan coba lagi atau sederhanakan pertanyaan."
        )
    except Exception as e:
        await update.message.reply_text(f"Maaf, terjadi error: {e}")


# =============================================================================
# Entry point
# =============================================================================

if __name__ == "__main__":
    log.info("Widya Analytics Telegram Bot is Starting...")

    if not TELEGRAM_TOKEN:
        log.error("TELEGRAM_TOKEN belum diset di file .env!")
    else:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

        app.add_handler(CommandHandler('start',      cmd_start))
        app.add_handler(CommandHandler('clear',      cmd_clear))
        app.add_handler(CommandHandler('myid',       cmd_myid))
        app.add_handler(CommandHandler('adduser',    cmd_adduser))
        app.add_handler(CommandHandler('removeuser', cmd_removeuser))
        app.add_handler(CommandHandler('listusers',  cmd_listusers))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        log.info("Bot aktif. Tekan Ctrl+C untuk berhenti.")
        app.run_polling()

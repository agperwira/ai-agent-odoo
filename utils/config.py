import os
import pathlib
from dotenv import load_dotenv

load_dotenv()

# Odoo
ODOO_URL  = os.getenv('ODOO_URL',  'http://127.0.0.1:8069')
ODOO_DB   = os.getenv('ODOO_DB',   'database')
ODOO_USER = os.getenv('ODOO_USER', 'database@gmail.com')
ODOO_PASS = os.getenv('ODOO_PASS', 'admin123')

# AI
AI_BASE_URL    = os.getenv('AI_BASE_URL', 'https://ai.sumopod.com/v1')
AI_API_KEY     = os.getenv('AI_API_KEY', '')
AI_MODEL       = os.getenv('AI_MODEL', 'gpt-4o-mini')
AI_TIMEOUT     = int(os.getenv('AI_TIMEOUT', '60'))
AI_MAX_RETRIES = int(os.getenv('AI_MAX_RETRIES', '3'))
AI_HEADERS     = {
    "Authorization": f"Bearer {AI_API_KEY}",
    "Content-Type": "application/json",
}

# Session storage
SESSION_DIR = pathlib.Path(__file__).parent.parent / 'sessions'
SESSION_DIR.mkdir(exist_ok=True)

# Model yang DILARANG dibaca oleh AI — meskipun via odoo_search_read.
# Berisi data sensitif: password hash, API key, ACL rules, dsb.
BLOCKED_MODELS = {
    'res.users',
    'res.users.apikeys',
    'ir.config_parameter',
    'ir.rule',
    'ir.model.access',
    'res.groups',
    'mail.message',         # bisa mengandung data internal
    'ir.logging',
    'base_setup.act_general_configuration',
}

# Model Odoo yang boleh ditulis oleh AI (create / write).
# Jangan tambahkan: res.users, ir.config_parameter, ir.rule, res.groups, dll.
WRITABLE_MODELS = {
    # Penjualan
    'sale.order',
    'sale.order.line',
    # Pembelian
    'purchase.order',
    'purchase.order.line',
    # Akuntansi
    'account.move',
    'account.move.line',
    'account.payment',
    'account.payment.register',
    # Gudang
    'stock.picking',
    'stock.move',
    # Customer & Vendor
    'res.partner',
    # Produk
    'product.product',
    'product.template',
    # HR
    'hr.employee',
    'hr.leave',
    'hr.attendance',
}

# System prompt
SYSTEM_MSG = {
    "role": "system",
    "content": (
        "You are Widya Analytics AI Agent for Odoo 17. "
        "You are bilingual in English and Indonesian — respond in the same language the user uses. "
        "Keep IDs you discover in memory for use in subsequent steps. "
        "Use the available tools to fetch Odoo data or perform actions."
    ),
}

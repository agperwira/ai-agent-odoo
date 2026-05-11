import ast
import logging
import threading
import xmlrpc.client

from utils.config import ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASS, BLOCKED_MODELS

log = logging.getLogger(__name__)

# Setiap thread menyimpan koneksi Odoo-nya sendiri.
# Ini mencegah race condition saat banyak user Telegram mengirim pesan bersamaan
# dan _connect() di satu thread meng-overwrite self.uid thread lain.
_thread_local = threading.local()


class OdooBase:
    """Koneksi dasar ke Odoo via XML-RPC. Diwarisi oleh semua mixin."""

    def __init__(self):
        self._connect()

    # ------------------------------------------------------------------
    # Thread-local connection state
    # ------------------------------------------------------------------

    @property
    def uid(self):
        return getattr(_thread_local, 'uid', None)

    @uid.setter
    def uid(self, value):
        _thread_local.uid = value

    @property
    def models(self):
        return getattr(_thread_local, 'models', None)

    @models.setter
    def models(self, value):
        _thread_local.models = value

    # ------------------------------------------------------------------

    def _connect(self):
        """Login ke Odoo. Dipanggil saat init dan otomatis saat reconnect."""
        try:
            common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
            self.uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASS, {})
            self.models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
            if not self.uid:
                raise Exception("Login gagal. Cek ODOO_USER / ODOO_PASS di .env")
            log.info("Terhubung ke Odoo (thread=%s)", threading.current_thread().name)
        except Exception as e:
            log.error("Error koneksi Odoo: %s", e)
            self.uid = None

    def _exec(self, model, method, args, kwargs=None):
        """Eksekusi XML-RPC. Auto-reconnect per thread jika sesi mati."""
        if not self.uid:
            log.warning("Sesi Odoo mati (thread=%s), reconnect...", threading.current_thread().name)
            self._connect()
        if not self.uid:
            raise ConnectionError("Tidak dapat terhubung ke Odoo setelah reconnect.")
        return self.models.execute_kw(
            ODOO_DB, self.uid, ODOO_PASS, model, method, args, kwargs or {}
        )

    @staticmethod
    def _parse_domain(raw):
        """Normalisasi domain dari string atau list menjadi list-of-tuples Odoo."""
        if isinstance(raw, str):
            try:
                raw = ast.literal_eval(raw)
            except Exception:
                return []
        if not isinstance(raw, list):
            return []
        # Hilangkan double-wrap [[...]]
        if raw and isinstance(raw[0], list) and raw[0] and isinstance(raw[0][0], list):
            raw = raw[0]
        return [tuple(x) if isinstance(x, list) else x for x in raw]

    @staticmethod
    def _validate_domain(domain: list) -> str | None:
        """
        Validasi struktur domain Odoo. Return pesan error jika tidak valid, None jika ok.

        Domain yang valid adalah list kosong atau list berisi:
          - Operator logika: '&', '|', '!'  (string)
          - Leaf tuple: (field, operator, value)  dengan field berupa string

        Ini mencegah domain malformed atau injeksi dari LLM yang menyebabkan crash
        atau eksposur data tidak terduga.
        """
        LOGIC_OPS = {'&', '|', '!'}
        LEAF_OPS  = {
            '=', '!=', '<', '>', '<=', '>=',
            'like', 'ilike', 'not like', 'not ilike',
            'in', 'not in', 'child_of', 'parent_of', '=?',
        }

        for item in domain:
            if isinstance(item, str):
                if item not in LOGIC_OPS:
                    return f"Operator logika tidak valid dalam domain: '{item}'. Gunakan '&', '|', atau '!'."
            elif isinstance(item, tuple):
                if len(item) != 3:
                    return f"Leaf domain harus berisi 3 elemen (field, operator, value), dapat: {item}"
                field, op, _ = item
                if not isinstance(field, str) or not field:
                    return f"Field domain harus berupa string, dapat: {field!r}"
                if op not in LEAF_OPS:
                    return f"Operator domain tidak valid: '{op}'. Gunakan salah satu: {', '.join(sorted(LEAF_OPS))}"
            else:
                return f"Elemen domain tidak valid: {item!r}. Harus string operator atau tuple (field, op, value)."
        return None

    @staticmethod
    def _parse_fields(raw):
        """Normalisasi fields dari string 'id,name' atau list menjadi list."""
        if isinstance(raw, str):
            parts = [f.strip() for f in raw.split(',') if f.strip()]
            return parts or ['id', 'display_name']
        return raw or ['id', 'display_name']

    def search_read(self, model, domain=None, fields=None, limit=10):
        """Pencarian data generik untuk model Odoo apapun."""
        # 1.2 — Blokir model sensitif
        if model in BLOCKED_MODELS:
            return (
                f"Akses ditolak: model '{model}' diblokir karena mengandung data sensitif. "
                "Gunakan Odoo UI atau admin langsung untuk mengakses data ini."
            )

        domain = self._parse_domain(domain or [])

        # 1.3 — Validasi struktur domain
        err = self._validate_domain(domain)
        if err:
            return f"Domain tidak valid: {err}"

        fields = self._parse_fields(fields)
        log.info("search_read %s | domain=%s fields=%s", model, domain, fields)
        try:
            return self._exec(model, 'search_read', [domain], {'fields': fields, 'limit': limit})
        except Exception as e:
            return f"Error query {model}: {e}"

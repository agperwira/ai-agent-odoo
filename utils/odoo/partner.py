import json
import logging

from utils.config import WRITABLE_MODELS

log = logging.getLogger(__name__)


class PartnerMixin:
    """Operasi Customer & update record generik (res.partner)."""

    def create_customer(self, name, email=None, phone=None, city=None):
        log.info("Buat customer | Nama:%s", name)
        data = {'name': name, 'customer_rank': 1}
        if email: data['email'] = email
        if phone: data['phone'] = phone
        if city:  data['city']  = city
        try:
            new_id = self._exec('res.partner', 'create', [data])
            return f"Customer '{name}' berhasil dibuat dengan ID {new_id}."
        except Exception as e:
            log.error("create_customer gagal: %s", e)
            return f"Gagal buat customer: {e}"

    def update_record(self, model, record_id, values):
        """Update field-field pada record yang sudah ada."""
        if model not in WRITABLE_MODELS:
            return (
                f"Akses ditolak: model '{model}' tidak ada dalam daftar yang diizinkan untuk ditulis. "
                f"Model yang diizinkan: {', '.join(sorted(WRITABLE_MODELS))}"
            )
        if isinstance(values, str):
            try:
                values = json.loads(values)
            except Exception as e:
                return f"Format values tidak valid (harus JSON): {e}"
        log.info("Update %s ID %s | %s", model, record_id, values)
        try:
            self._exec(model, 'write', [[int(record_id)], values])
            return f"Record {model} ID {record_id} berhasil diupdate."
        except Exception as e:
            log.error("update_record gagal: %s", e)
            return f"Gagal update record: {e}"

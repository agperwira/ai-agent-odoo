import logging
from datetime import datetime

log = logging.getLogger(__name__)


class AccountingMixin:
    """Operasi modul Akuntansi (account.move, account.move.line)."""

    def create_invoice(self, partner_id, lines, invoice_date=None):
        log.info("Buat invoice | Partner:%s", partner_id)
        try:
            invoice_lines = [(0, 0, {
                'product_id': int(l['product_id']),
                'quantity':   float(l.get('quantity', 1)),
                'price_unit': float(l['price_unit']),
            }) for l in lines]
            data = {'partner_id': int(partner_id), 'move_type': 'out_invoice',
                    'invoice_line_ids': invoice_lines}
            if invoice_date: data['invoice_date'] = invoice_date
            new_id = self._exec('account.move', 'create', [data])
            return f"Invoice ID {new_id} berhasil dibuat."
        except Exception as e:
            log.error("create_invoice gagal: %s", e)
            return f"Gagal buat invoice: {e}"

    def get_invoice_list(self, partner_name=None, state=None, limit=10):
        domain = [('move_type', '=', 'out_invoice')]
        if state:        domain.append(('state', '=', state))
        if partner_name: domain.append(('partner_id.name', 'ilike', partner_name))
        log.info("Daftar invoice | partner=%s state=%s", partner_name, state)
        try:
            return self._exec('account.move', 'search_read', [domain],
                              {'fields': ['id', 'name', 'partner_id', 'amount_total',
                                          'state', 'invoice_date', 'payment_state'],
                               'limit': limit})
        except Exception as e:
            log.error("get_invoice_list gagal: %s", e)
            return f"Gagal ambil invoice: {e}"

    def post_invoice(self, invoice_id):
        """Posting invoice dari Draft → Posted."""
        log.info("Post invoice ID %s", invoice_id)
        try:
            self._exec('account.move', 'action_post', [[int(invoice_id)]])
            return f"Invoice ID {invoice_id} berhasil diposting."
        except Exception as e:
            log.error("post_invoice gagal: %s", e)
            return f"Gagal posting invoice: {e}"

    def register_payment(self, invoice_id, amount=None, payment_date=None, journal_id=None):
        """Catat pembayaran invoice. Invoice harus sudah Posted."""
        log.info("Register payment | Invoice:%s Amount:%s", invoice_id, amount)
        try:
            inv = self._exec('account.move', 'read', [[int(invoice_id)]],
                             {'fields': ['amount_residual', 'move_type']})
            if not inv:
                return f"Invoice ID {invoice_id} tidak ditemukan."
            if inv[0]['move_type'] not in ('out_invoice', 'in_invoice', 'out_refund', 'in_refund'):
                return "Record bukan invoice yang bisa dibayar."
            ctx = self._exec('account.move', 'action_register_payment', [[int(invoice_id)]])
            pay_data = {
                'payment_date': payment_date or datetime.now().strftime('%Y-%m-%d'),
                'amount': float(amount) if amount else inv[0]['amount_residual'],
            }
            if journal_id: pay_data['journal_id'] = int(journal_id)
            wizard_id = self._exec('account.payment.register', 'create', [pay_data],
                                   {'context': ctx.get('context', {})})
            self._exec('account.payment.register', 'action_create_payments', [[wizard_id]])
            return f"Pembayaran untuk Invoice ID {invoice_id} berhasil dicatat."
        except Exception as e:
            log.error("register_payment gagal: %s", e)
            return f"Gagal catat pembayaran: {e}"

    def get_customer_receivables(self, partner_name=None, limit=10):
        domain = [('account_type', '=', 'asset_receivable'), ('reconciled', '=', False)]
        if partner_name: domain.append(('partner_id.name', 'ilike', partner_name))
        log.info("Piutang customer | partner=%s", partner_name)
        try:
            return self._exec('account.move.line', 'search_read', [domain],
                              {'fields': ['partner_id', 'name', 'debit', 'credit',
                                          'date_maturity', 'move_id'],
                               'limit': limit})
        except Exception as e:
            log.error("get_customer_receivables gagal: %s", e)
            return f"Gagal ambil piutang: {e}"

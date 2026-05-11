import logging

log = logging.getLogger(__name__)


class PurchaseMixin:
    """Operasi modul Pembelian (purchase.order)."""

    def get_purchase_orders(self, partner_name=None, state=None, date_from=None, date_to=None, limit=20):
        """Cari Purchase Order dengan filter opsional."""
        domain = []
        if partner_name: domain.append(('partner_id.name', 'ilike', partner_name))
        if state:        domain.append(('state', '=', state))
        if date_from:    domain.append(('date_order', '>=', date_from))
        if date_to:      domain.append(('date_order', '<=', date_to))
        log.info("Daftar PO | partner=%s state=%s %s~%s", partner_name, state, date_from, date_to)
        try:
            return self._exec('purchase.order', 'search_read', [domain],
                              {'fields': ['id', 'name', 'partner_id', 'date_order',
                                          'amount_total', 'state', 'order_line'],
                               'limit': int(limit), 'order': 'date_order desc'})
        except Exception as e:
            log.error("get_purchase_orders gagal: %s", e)
            return f"Gagal ambil purchase order: {e}"

    def create_purchase_order(self, partner_id, product_id, quantity=1, price_unit=None):
        try:
            if price_unit: price_unit = float(price_unit)
        except Exception:
            price_unit = None
        log.info("Buat PO | Vendor:%s Produk:%s Qty:%s", partner_id, product_id, quantity)
        line = {'product_id': int(product_id), 'product_qty': float(quantity),
                'name': '/', 'date_planned': False}
        if price_unit: line['price_unit'] = price_unit
        try:
            new_id = self._exec('purchase.order', 'create',
                                [{'partner_id': int(partner_id), 'order_line': [(0, 0, line)]}])
            return f"Purchase Order ID {new_id} berhasil dibuat."
        except Exception as e:
            log.error("create_purchase_order gagal: %s", e)
            return f"Gagal buat PO: {e}"

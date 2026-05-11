import logging

log = logging.getLogger(__name__)


class InventoryMixin:
    """Operasi modul Gudang & Pengiriman (product.product, stock.picking)."""

    def get_stock(self, product_name=None):
        domain = [('type', '=', 'product')]
        if product_name: domain.append(('name', 'ilike', product_name))
        log.info("Cek stok | produk='%s'", product_name or 'semua')
        try:
            return self._exec('product.product', 'search_read', [domain],
                              {'fields': ['id', 'name', 'qty_available', 'virtual_available', 'uom_id'],
                               'limit': 20})
        except Exception as e:
            log.error("get_stock gagal: %s", e)
            return f"Gagal ambil stok: {e}"

    def get_delivery(self, partner_name=None, state=None, limit=10):
        """Status delivery order keluar (outgoing picking)."""
        domain = [('picking_type_code', '=', 'outgoing')]
        if state:        domain.append(('state', '=', state))
        if partner_name: domain.append(('partner_id.name', 'ilike', partner_name))
        log.info("Delivery orders | partner=%s state=%s", partner_name, state)
        try:
            return self._exec('stock.picking', 'search_read', [domain],
                              {'fields': ['name', 'partner_id', 'state', 'scheduled_date',
                                          'date_done', 'origin', 'move_ids_without_package'],
                               'limit': int(limit)})
        except Exception as e:
            log.error("get_delivery gagal: %s", e)
            return f"Gagal ambil delivery: {e}"

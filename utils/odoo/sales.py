import logging

log = logging.getLogger(__name__)


class SalesMixin:
    """Operasi modul Penjualan (sale.order, sale.order.line)."""

    def get_total_revenue(self):
        log.info("Agregasi total revenue sale.order")
        res = self._exec('sale.order', 'read_group', [[], ['amount_total'], []])
        return res[0]['amount_total'] if res else 0

    def get_sales_summary(self, date_from=None, date_to=None):
        domain = [('state', 'in', ['sale', 'done'])]
        if date_from: domain.append(('date_order', '>=', date_from))
        if date_to:   domain.append(('date_order', '<=', date_to))
        log.info("Sales summary | %s s/d %s", date_from, date_to)
        try:
            return self._exec('sale.order', 'read_group',
                              [domain, ['amount_total', 'partner_id'], ['partner_id']])
        except Exception as e:
            log.error("get_sales_summary gagal: %s", e)
            return f"Gagal ambil summary penjualan: {e}"

    def create_sales_order(self, partner_id, product_id, quantity=1, price_unit=None):
        try:
            if price_unit: price_unit = float(price_unit)
        except Exception:
            price_unit = None
        log.info("Buat SO | Partner:%s Produk:%s Qty:%s", partner_id, product_id, quantity)
        line = {'product_id': int(product_id), 'product_uom_qty': float(quantity)}
        if price_unit: line['price_unit'] = price_unit
        try:
            new_id = self._exec('sale.order', 'create',
                                [{'partner_id': int(partner_id), 'order_line': [(0, 0, line)]}])
            return f"Sales Order ID {new_id} berhasil dibuat."
        except Exception as e:
            log.error("create_sales_order gagal: %s", e)
            return f"Gagal buat SO: {e}"

    def confirm_sales_order(self, order_id):
        log.info("Konfirmasi SO ID %s", order_id)
        try:
            self._exec('sale.order', 'action_confirm', [[int(order_id)]])
            return f"Sales Order ID {order_id} berhasil dikonfirmasi."
        except Exception as e:
            log.error("confirm_sales_order gagal: %s", e)
            return f"Gagal konfirmasi SO: {e}"

    def get_sales_orders(self, partner_name=None, state=None, date_from=None, date_to=None, limit=20):
        """Cari Sales Order dengan filter opsional."""
        domain = []
        if partner_name: domain.append(('partner_id.name', 'ilike', partner_name))
        if state:        domain.append(('state', '=', state))
        if date_from:    domain.append(('date_order', '>=', date_from))
        if date_to:      domain.append(('date_order', '<=', date_to))
        log.info("Daftar SO | partner=%s state=%s %s~%s", partner_name, state, date_from, date_to)
        try:
            return self._exec('sale.order', 'search_read', [domain],
                              {'fields': ['id', 'name', 'partner_id', 'date_order',
                                          'amount_total', 'state', 'order_line'],
                               'limit': int(limit), 'order': 'date_order desc'})
        except Exception as e:
            log.error("get_sales_orders gagal: %s", e)
            return f"Gagal ambil sales order: {e}"

    def top_products(self, limit=10, date_from=None, date_to=None, order_by='qty'):
        domain = [('order_id.state', 'in', ['sale', 'done'])]
        if date_from: domain.append(('order_id.date_order', '>=', date_from))
        if date_to:   domain.append(('order_id.date_order', '<=', date_to))
        sort = 'price_subtotal desc' if order_by == 'revenue' else 'product_uom_qty desc'
        log.info("Top %s produk | sort=%s", limit, sort)
        try:
            rows = self._exec(
                'sale.order.line', 'read_group',
                [domain, ['product_uom_qty', 'price_subtotal', 'product_id'], ['product_id']],
                {'orderby': sort, 'limit': int(limit)}
            )
            return [{
                'product':       (r.get('product_id') or [None, 'Unknown'])[1],
                'total_qty':     round(r.get('product_uom_qty', 0), 2),
                'total_revenue': round(r.get('price_subtotal', 0), 2),
            } for r in rows]
        except Exception as e:
            log.error("top_products gagal: %s", e)
            return f"Gagal ambil top produk: {e}"

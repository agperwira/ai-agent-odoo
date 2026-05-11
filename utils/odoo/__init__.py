from utils.odoo.base      import OdooBase
from utils.odoo.sales     import SalesMixin
from utils.odoo.purchase  import PurchaseMixin
from utils.odoo.inventory import InventoryMixin
from utils.odoo.accounting import AccountingMixin
from utils.odoo.partner   import PartnerMixin
from utils.odoo.hr        import HRMixin


class OdooBackend(
    SalesMixin,
    PurchaseMixin,
    InventoryMixin,
    AccountingMixin,
    PartnerMixin,
    HRMixin,
    OdooBase,
):
    """
    Gabungan semua mixin Odoo dalam satu class.
    Tambah modul baru cukup dengan buat mixin baru dan daftarkan di sini.
    """

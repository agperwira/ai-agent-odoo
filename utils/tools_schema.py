"""
Definisi schema semua tools yang dikirim ke LLM.
Urutan: Generic → Penjualan → Pembelian → Gudang → Invoice → Customer → HR
"""


def _fn(name, description, properties, required=None):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                **({"required": required} if required else {}),
            },
        },
    }


_STR  = lambda desc: {"type": "string",  "description": desc}
_INT  = lambda desc: {"type": "integer", "description": desc}
_NUM  = lambda desc: {"type": "number",  "description": desc}
_DATE = lambda desc: {"type": "string",  "description": f"{desc} (format YYYY-MM-DD)"}


TOOLS = [

    # ── Generic ───────────────────────────────────────────────────────────
    _fn("odoo_search_read",
        "Ambil data dari model Odoo apapun. Gunakan untuk mencari ID sebelum operasi lain.",
        {
            "model":  _STR("Nama model teknis, misal 'res.partner'"),
            "domain": _STR("Filter domain, misal '[( \"name\",\"ilike\",\"Budi\")]'"),
            "fields": _STR("Kolom yang diambil, pisah koma, misal 'id,name,email'"),
        },
        required=["model"]),

    # ── Penjualan ─────────────────────────────────────────────────────────
    _fn("odoo_get_sales_orders",
        "Cari dan tampilkan daftar Sales Order. Gunakan ini untuk melihat SO milik customer tertentu.",
        {
            "partner_name": _STR("Nama atau sebagian nama customer, misal 'Azure'"),
            "state":        _STR("Status SO: 'draft'|'sale'|'done'|'cancel'. Kosongkan untuk semua."),
            "date_from":    _DATE("Filter SO dari tanggal"),
            "date_to":      _DATE("Filter SO sampai tanggal"),
            "limit":        _INT("Jumlah data, default 20"),
        }),

    _fn("odoo_get_total_revenue",
        "Hitung total omzet seluruh penjualan.",
        {}),

    _fn("odoo_get_sales_summary",
        "Ringkasan omzet penjualan per customer dalam rentang tanggal.",
        {"date_from": _DATE("Dari tanggal"), "date_to": _DATE("Sampai tanggal")}),

    _fn("odoo_create_sales_order",
        "Buat Sales Order baru. Pastikan sudah punya partner_id dan product_id.",
        {
            "partner_id": _INT("ID customer (res.partner)"),
            "product_id": _INT("ID produk (product.product)"),
            "quantity":   _NUM("Jumlah unit, default 1"),
            "price_unit": _NUM("Harga satuan, kosongkan untuk harga default Odoo"),
        },
        required=["partner_id", "product_id"]),

    _fn("odoo_confirm_sales_order",
        "Konfirmasi Sales Order dari Draft menjadi aktif.",
        {"order_id": _INT("ID Sales Order")},
        required=["order_id"]),

    _fn("odoo_top_products",
        "Laporan produk terlaris berdasarkan kuantitas atau revenue.",
        {
            "limit":     _INT("Jumlah produk, default 10"),
            "date_from": _DATE("Filter dari tanggal"),
            "date_to":   _DATE("Filter sampai tanggal"),
            "order_by":  _STR("'qty' untuk by kuantitas, 'revenue' untuk by omzet"),
        }),

    # ── Pembelian ─────────────────────────────────────────────────────────
    _fn("odoo_get_purchase_orders",
        "Cari dan tampilkan daftar Purchase Order. Gunakan ini untuk melihat PO ke vendor tertentu.",
        {
            "partner_name": _STR("Nama atau sebagian nama vendor"),
            "state":        _STR("Status PO: 'draft'|'purchase'|'done'|'cancel'. Kosongkan untuk semua."),
            "date_from":    _DATE("Filter PO dari tanggal"),
            "date_to":      _DATE("Filter PO sampai tanggal"),
            "limit":        _INT("Jumlah data, default 20"),
        }),

    _fn("odoo_create_purchase_order",
        "Buat Purchase Order ke vendor.",
        {
            "partner_id": _INT("ID vendor (res.partner)"),
            "product_id": _INT("ID produk"),
            "quantity":   _NUM("Jumlah, default 1"),
            "price_unit": _NUM("Harga beli, kosongkan untuk harga default"),
        },
        required=["partner_id", "product_id"]),

    # ── Gudang & Pengiriman ───────────────────────────────────────────────
    _fn("odoo_get_stock",
        "Cek stok produk. qty_available=stok fisik; virtual_available=termasuk SO/PO pending.",
        {"product_name": _STR("Nama produk, kosongkan untuk semua")}),

    _fn("odoo_get_delivery",
        "Cek status pengiriman (delivery order) untuk customer.",
        {
            "partner_name": _STR("Nama customer, opsional"),
            "state":        _STR("'draft'|'waiting'|'confirmed'|'assigned'|'done'|'cancel'"),
            "limit":        _INT("Jumlah data, default 10"),
        }),

    # ── Invoice & Pembayaran ──────────────────────────────────────────────
    _fn("odoo_create_invoice",
        "Buat customer invoice baru.",
        {
            "partner_id":   _INT("ID customer"),
            "lines":        _STR('Baris invoice JSON, misal \'[{"product_id":5,"quantity":2,"price_unit":150000}]\''),
            "invoice_date": _DATE("Tanggal invoice, kosongkan untuk hari ini"),
        },
        required=["partner_id", "lines"]),

    _fn("odoo_get_invoice_list",
        "Lihat daftar invoice penjualan.",
        {
            "partner_name": _STR("Nama customer"),
            "state":        _STR("'draft'|'posted'|'cancel'"),
            "limit":        _INT("Jumlah data, default 10"),
        }),

    _fn("odoo_post_invoice",
        "Validasi / posting invoice dari Draft menjadi Posted.",
        {"invoice_id": _INT("ID invoice (account.move)")},
        required=["invoice_id"]),

    _fn("odoo_register_payment",
        "Catat pembayaran invoice customer. Invoice harus sudah Posted.",
        {
            "invoice_id":   _INT("ID invoice"),
            "amount":       _NUM("Nominal pembayaran, kosongkan untuk lunas penuh"),
            "payment_date": _DATE("Tanggal pembayaran, default hari ini"),
            "journal_id":   _INT("ID jurnal kas/bank, opsional"),
        },
        required=["invoice_id"]),

    _fn("odoo_get_customer_receivables",
        "Lihat piutang customer yang belum lunas.",
        {
            "partner_name": _STR("Nama customer"),
            "limit":        _INT("Jumlah data, default 10"),
        }),

    # ── Customer & Record Umum ────────────────────────────────────────────
    _fn("odoo_create_customer",
        "Daftarkan customer baru ke Odoo.",
        {
            "name":  _STR("Nama lengkap"),
            "email": _STR("Email"),
            "phone": _STR("Nomor telepon"),
            "city":  _STR("Kota"),
        },
        required=["name"]),

    _fn("odoo_update_record",
        "Update field record Odoo yang sudah ada.",
        {
            "model":     _STR("Nama model teknis, misal 'sale.order'"),
            "record_id": _INT("ID record"),
            "values":    _STR('Field yang diupdate dalam JSON, misal \'{"note": "Urgent"}\''),
        },
        required=["model", "record_id", "values"]),

    # ── HR — Karyawan ─────────────────────────────────────────────────────
    _fn("odoo_create_employee",
        "Buat karyawan baru. PIN digunakan untuk check-in absensi via kiosk.",
        {
            "name":          _STR("Nama lengkap karyawan"),
            "job_title":     _STR("Jabatan / posisi"),
            "department_id": _INT("ID departemen, cari via odoo_search_read 'hr.department'"),
            "work_email":    _STR("Email kerja"),
            "mobile_phone":  _STR("Nomor HP"),
            "pin":           _STR("PIN angka untuk absensi kiosk (4-6 digit)"),
        },
        required=["name"]),

    _fn("odoo_set_employee_pin",
        "Update PIN absensi karyawan yang sudah ada.",
        {
            "employee_id": _INT("ID karyawan (hr.employee)"),
            "pin":         _STR("PIN baru berupa angka (4-6 digit)"),
        },
        required=["employee_id", "pin"]),

    _fn("odoo_get_employees",
        "Lihat daftar karyawan aktif.",
        {
            "name":       _STR("Nama karyawan"),
            "department": _STR("Nama departemen"),
            "limit":      _INT("Jumlah data, default 20"),
        }),

    # ── HR — Absensi ──────────────────────────────────────────────────────
    _fn("odoo_get_attendance",
        "Lihat rekap absensi (check-in/check-out) karyawan.",
        {
            "employee_name": _STR("Nama karyawan"),
            "date_from":     _DATE("Dari tanggal"),
            "date_to":       _DATE("Sampai tanggal"),
            "limit":         _INT("Jumlah baris, default 50"),
        }),

    _fn("odoo_get_attendance_summary",
        "Ringkasan total jam kerja per karyawan.",
        {
            "date_from":  _DATE("Dari tanggal"),
            "date_to":    _DATE("Sampai tanggal"),
            "department": _STR("Filter by nama departemen"),
        }),

    # ── HR — Cuti ─────────────────────────────────────────────────────────
    _fn("odoo_get_leaves",
        "Lihat pengajuan cuti karyawan.",
        {
            "employee_name": _STR("Nama karyawan"),
            "state":         _STR("'draft'|'confirm'|'validate1'|'validate'|'refuse'"),
            "date_from":     _DATE("Dari tanggal"),
            "date_to":       _DATE("Sampai tanggal"),
            "limit":         _INT("Jumlah data, default 20"),
        }),
]

import logging

log = logging.getLogger(__name__)


class HRMixin:
    """Operasi modul HR — Karyawan, Absensi, dan Cuti."""

    # ------------------------------------------------------------------
    # Karyawan
    # ------------------------------------------------------------------

    def create_employee(self, name, job_title=None, department_id=None,
                        work_email=None, mobile_phone=None, pin=None):
        """Buat karyawan baru. PIN dipakai untuk check-in absensi via kiosk."""
        log.info("Buat karyawan | Nama:%s PIN:%s", name, '***' if pin else '-')
        data = {'name': name}
        if job_title:     data['job_title']     = job_title
        if department_id: data['department_id'] = int(department_id)
        if work_email:    data['work_email']    = work_email
        if mobile_phone:  data['mobile_phone']  = mobile_phone
        if pin:
            if not str(pin).isdigit():
                return "PIN harus berupa angka saja."
            data['pin'] = str(pin)
        try:
            new_id = self._exec('hr.employee', 'create', [data])
            return f"Karyawan '{name}' berhasil dibuat dengan ID {new_id}."
        except Exception as e:
            log.error("create_employee gagal: %s", e)
            return f"Gagal buat karyawan: {e}"

    def set_employee_pin(self, employee_id, pin):
        """Update PIN absensi karyawan yang sudah ada."""
        if not str(pin).isdigit():
            return "PIN harus berupa angka saja."
        log.info("Set PIN karyawan ID %s", employee_id)
        try:
            self._exec('hr.employee', 'write', [[int(employee_id)], {'pin': str(pin)}])
            return f"PIN karyawan ID {employee_id} berhasil diupdate."
        except Exception as e:
            log.error("set_employee_pin gagal: %s", e)
            return f"Gagal set PIN: {e}"

    def get_employees(self, name=None, department=None, limit=20):
        domain = [('active', '=', True)]
        if name:       domain.append(('name', 'ilike', name))
        if department: domain.append(('department_id.name', 'ilike', department))
        log.info("Daftar karyawan | name=%s dept=%s", name, department)
        try:
            return self._exec('hr.employee', 'search_read', [domain],
                              {'fields': ['id', 'name', 'job_title', 'department_id',
                                          'work_email', 'mobile_phone', 'work_location_id'],
                               'limit': int(limit)})
        except Exception as e:
            log.error("get_employees gagal: %s", e)
            return f"Gagal ambil karyawan: {e}"

    # ------------------------------------------------------------------
    # Absensi
    # ------------------------------------------------------------------

    def get_attendance(self, employee_name=None, date_from=None, date_to=None, limit=50):
        """Detail check-in / check-out karyawan."""
        domain = []
        if employee_name: domain.append(('employee_id.name', 'ilike', employee_name))
        if date_from:     domain.append(('check_in', '>=', date_from + ' 00:00:00'))
        if date_to:       domain.append(('check_in', '<=', date_to   + ' 23:59:59'))
        log.info("Absensi | employee=%s %s~%s", employee_name, date_from, date_to)
        try:
            return self._exec('hr.attendance', 'search_read', [domain],
                              {'fields': ['employee_id', 'check_in', 'check_out', 'worked_hours'],
                               'limit': int(limit), 'order': 'check_in desc'})
        except Exception as e:
            log.error("get_attendance gagal: %s", e)
            return f"Gagal ambil absensi: {e}"

    def get_attendance_summary(self, date_from=None, date_to=None, department=None):
        """Agregasi total jam kerja per karyawan."""
        domain = []
        if date_from:  domain.append(('check_in', '>=', date_from + ' 00:00:00'))
        if date_to:    domain.append(('check_in', '<=', date_to   + ' 23:59:59'))
        if department: domain.append(('employee_id.department_id.name', 'ilike', department))
        log.info("Summary absensi | dept=%s %s~%s", department, date_from, date_to)
        try:
            rows = self._exec('hr.attendance', 'read_group',
                              [domain, ['worked_hours', 'employee_id'], ['employee_id']],
                              {'orderby': 'worked_hours desc'})
            return [{
                'employee':         (r.get('employee_id') or [None, 'Unknown'])[1],
                'total_hours':      round(r.get('worked_hours', 0), 2),
                'attendance_count': r.get('employee_id_count', 0),
            } for r in rows]
        except Exception as e:
            log.error("get_attendance_summary gagal: %s", e)
            return f"Gagal ambil summary absensi: {e}"

    # ------------------------------------------------------------------
    # Cuti
    # ------------------------------------------------------------------

    def get_leaves(self, employee_name=None, state=None, date_from=None, date_to=None, limit=20):
        domain = []
        if employee_name: domain.append(('employee_id.name', 'ilike', employee_name))
        if state:         domain.append(('state', '=', state))
        if date_from:     domain.append(('date_from', '>=', date_from))
        if date_to:       domain.append(('date_to',   '<=', date_to))
        log.info("Cuti | employee=%s state=%s", employee_name, state)
        try:
            return self._exec('hr.leave', 'search_read', [domain],
                              {'fields': ['employee_id', 'holiday_status_id', 'date_from',
                                          'date_to', 'number_of_days', 'state', 'name'],
                               'limit': int(limit)})
        except Exception as e:
            log.error("get_leaves gagal: %s", e)
            return f"Gagal ambil data cuti: {e}"

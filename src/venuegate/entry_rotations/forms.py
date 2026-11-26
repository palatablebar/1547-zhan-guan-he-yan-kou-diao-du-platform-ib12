from collections.abc import Mapping
from decimal import Decimal

from .contracts import MeasureIssue


from dataclasses import dataclass


def form_number(form, sheet, name, minimum, maximum):
    from .service import number

    table = form.get(sheet)
    if not isinstance(table, Mapping):
        raise MeasureIssue(sheet, 'FORM_SECTION_REQUIRED')
    return Decimal(str(number(table.get(name), name, minimum, maximum)))


@dataclass(frozen=True, slots=True)
class EntryRotationsSheet:
    reservation_tickets: Decimal
    reported_school_runs: Decimal
    rain_deci_mm: Decimal
    open_gates: Decimal
    show_break_seconds: Decimal
    bus_due_seconds: Decimal

    def fields(self):
        return {
            'reservations': float(self.reservation_tickets),
            'school_groups': float(self.reported_school_runs),
            'rain_mm': float(self.rain_deci_mm) / 10,
            'turnstiles': float(self.open_gates),
            'transfer_min': float(self.show_break_seconds) / 60,
            'bus_eta': float(self.bus_due_seconds) / 60,
        }

    def validation(self):
        fields = self.fields()
        reservations = fields['reservations']
        school_groups = fields['school_groups']
        rain_mm = fields['rain_mm']
        turnstiles = fields['turnstiles']
        transfer_min = fields['transfer_min']
        bus_eta = fields['bus_eta']
        backlog_per_gate = reservations/turnstiles
        school_minimum = school_groups*5
        queue_window = transfer_min-bus_eta
        rain_intensity = rain_mm/max(4,bus_eta)
        alerts = []
        if school_minimum > reservations:
            alerts.append(('reported_school_runs', 'GROUP_TICKETS_DO_NOT_RECONCILE'))
        if backlog_per_gate>=205 and queue_window<0:
            alerts.append(('open_gates', 'CHECK_OPEN_BOOTH_TOTAL'))
        if rain_intensity>=8.5 and turnstiles<=3:
            alerts.append(('rain_deci_mm', 'RAIN_PLAN_MISSING'))
        return tuple(alerts)


def read_entry_rotations(form):
    return EntryRotationsSheet(
        reservation_tickets=form_number(form, '核验票数', 'reservation_tickets', 30, 440),
        reported_school_runs=form_number(form, '核验票数', 'reported_school_runs', 0, 21),
        rain_deci_mm=form_number(form, '场馆口排班', 'rain_deci_mm', 0, 380),
        open_gates=form_number(form, '场馆口排班', 'open_gates', 2, 14),
        show_break_seconds=form_number(form, '团客到站', 'show_break_seconds', 300, 3660),
        bus_due_seconds=form_number(form, '团客到站', 'bus_due_seconds', 240, 2700),
    )


def explicit_rows(form):
    if not isinstance(form, Mapping):
        raise MeasureIssue('form', 'FORM_OBJECT_REQUIRED')
    note = read_entry_rotations(form)
    return note.fields(), note.validation()


def check_native_history(source):
    if not isinstance(source, Mapping) or 'form' not in source:
        return source
    if any(key in source for key in ('reservations', 'school_groups', 'rain_mm', 'turnstiles', 'transfer_min', 'bus_eta')):
        raise MeasureIssue('form','MIXED_FORM_AND_FLAT_READING')
    converted, flags = explicit_rows(source['form'])
    if flags:
        raise MeasureIssue(*flags[0])
    return {**source, **converted}

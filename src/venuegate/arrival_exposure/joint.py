from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class JointAction:
    case: str
    work_units: int
    notes: str
    changes: dict[str, tuple[float, float]]

    def evidence(self, old_value, new_value, extrapolates):
        return {'联动推演':self.case, '用量':self.work_units, '先决条件':self.notes,
                '原预测':round(old_value,4), '替换预测':round(new_value,4),
                '变化':round(new_value-old_value,4), '超训练域':bool(extrapolates),
                '联动量测':{item:{'原值':before,'替换值':after} for item,(before,after) in self.changes.items()}}


def simulate_open_spare_gate(readings, invalid):
    turnstiles, transfer_min = readings[3], readings[4]
    if invalid.intersection(('turnstiles', 'transfer_min')):
        return None
    if not (turnstiles<=12 and transfer_min<=50):
        return None
    turnstiles_adjusted = turnstiles+2
    transfer_min_adjusted = transfer_min+10
    inspected = {
        'turnstiles': (turnstiles, turnstiles_adjusted),
        'transfer_min': (transfer_min, transfer_min_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('提早开口和预留空档', 2, '先调备用口并疏通下一展场', inspected)
    return None


def simulate_stagger_school_bus(readings, invalid):
    school_groups, bus_eta = readings[1], readings[5]
    if invalid.intersection(('school_groups', 'bus_eta')):
        return None
    if not (school_groups>=5 and bus_eta<=33):
        return None
    school_groups_adjusted = school_groups-4
    bus_eta_adjusted = bus_eta+9
    inspected = {
        'school_groups': (school_groups, school_groups_adjusted),
        'bus_eta': (bus_eta, bus_eta_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('挂签拆团', 2, '拆开车次后保留同组预约票', inspected)
    return None


def simulate_move_ticket_series(readings, invalid):
    reservations, transfer_min = readings[0], readings[4]
    if invalid.intersection(('reservations', 'transfer_min')):
        return None
    if not (reservations>=95 and transfer_min<=48):
        return None
    reservations_adjusted = reservations-48
    transfer_min_adjusted = transfer_min+8
    inspected = {
        'reservations': (reservations, reservations_adjusted),
        'transfer_min': (transfer_min, transfer_min_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('半小时预约分流', 2, '把一部分普通票流移到下个窗口', inspected)
    return None


def simulate_rain_gate_release(readings, invalid):
    rain_mm, turnstiles, transfer_min = readings[2], readings[3], readings[4]
    if invalid.intersection(('rain_mm', 'turnstiles', 'transfer_min')):
        return None
    if not (rain_mm>=12 and turnstiles<=11):
        return None
    turnstiles_adjusted = turnstiles+2
    transfer_min_adjusted = min(61,transfer_min+5)
    inspected = {
        'turnstiles': (turnstiles, turnstiles_adjusted),
        'transfer_min': (transfer_min, transfer_min_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('雨天备用候场', 3, '保留一个口给室内队列', inspected)
    return None


def simulate_school_counter(readings, invalid):
    reservations, school_groups = readings[0], readings[1]
    if invalid.intersection(('reservations', 'school_groups')):
        return None
    if not (school_groups>=9 and reservations>=100):
        return None
    school_groups_adjusted = school_groups-5
    reservations_adjusted = reservations-35
    inspected = {
        'school_groups': (school_groups, school_groups_adjusted),
        'reservations': (reservations, reservations_adjusted),
    }
    if any(new != old for old,new in inspected.values()):
        return JointAction('团客改用前台核验', 2, '把核验表和团客转到服务侧厅', inspected)
    return None


def options(values, missing):
    measurements=tuple(values)
    unobserved=frozenset(missing)
    cases=(
        simulate_open_spare_gate(measurements, unobserved),
        simulate_stagger_school_bus(measurements, unobserved),
        simulate_move_ticket_series(measurements, unobserved),
        simulate_rain_gate_release(measurements, unobserved),
        simulate_school_counter(measurements, unobserved),
    )
    return tuple(action for action in cases if action is not None)

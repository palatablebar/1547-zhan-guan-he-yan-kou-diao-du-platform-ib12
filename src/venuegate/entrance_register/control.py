from collections import Counter
from math import isfinite


def accountable_plan(rows, actual_balance, starting_capacity):
    seen = set()
    counts = Counter()
    total = 0
    for row in rows:
        if row['key'] in seen:
            raise ArithmeticError('复核凭证的关联单号不唯一')
        key = row['key']
        seen.add(key)
        state = row['state']
        counts[state] += 1
        if state == '已分派':
            total += row['cost']
        if not isfinite(row['estimate']):
            raise ArithmeticError('非有限估计不能签发')
    if total + actual_balance != starting_capacity:
        raise ArithmeticError('处置清册与工位余额不符')
    return counts, total


def register_entrance_register(measurements, estimate):
    reservations = measurements['reservations']
    school_groups = measurements['school_groups']
    rain_mm = measurements['rain_mm']
    turnstiles = measurements['turnstiles']
    transfer_min = measurements['transfer_min']
    bus_eta = measurements['bus_eta']
    return {
        '每口预约': round(reservations/turnstiles, 3),
        '换场票流密度': round(reservations/max(5,transfer_min), 3),
        '两展共用宽余时间': round(transfer_min-bus_eta, 3),
        '全天余下口': round(14-turnstiles, 3),
        '复核代价指标': round(estimate/(30*turnstiles) + max(0,25-transfer_min)/21, 4),
    }


def document_control(rows):
    register = []
    for row in rows:
        if row['state'] not in {'已分派', '暂停', '人工判读'}:
            continue
        note = register_entrance_register(row['measurements'], row['estimate'])
        register.append({'单号': row['key'], '区段': row['zone'], '处置': row['state'], **note})
    return register

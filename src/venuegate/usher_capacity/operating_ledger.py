from collections import defaultdict
from dataclasses import dataclass
from math import ceil, floor


@dataclass(frozen=True, slots=True)
class GateTurn:
    window: int
    booked: int
    groups: int
    served: int
    queue_end: int
    use_inner_line: bool


def seats_per_gate(measures, escorted):
    local = int(measures['turnstiles'])
    if escorted:
        local = max(1, local - 1)
    seconds_per_scan = 12 if measures['rain_mm'] >= 19 else 8
    return local * (5 * 60 // seconds_per_scan)


def turn_profile(ticket):
    scan = ticket['measurements']
    windows = max(1, ceil(scan['transfer_min'] / 5))
    planned = min(ceil(scan['reservations']), max(0, ceil(ticket['estimate'])))
    groups = int(scan['school_groups'])
    escorted_people = min(planned, groups * 14)
    walk_ins = planned - escorted_people
    escort_window = min(windows-1, floor(scan['bus_eta'] / 5))
    backlog = 0
    output = []
    for offset in range(windows):
        bookings = (offset+1) * walk_ins // windows - offset * walk_ins // windows
        escorted = escorted_people if offset == escort_window else 0
        seats = seats_per_gate(scan, escorted)
        line = backlog + bookings + escorted
        boarded = min(line,seats)
        backlog = line - boarded
        inner = scan['rain_mm'] >= 19 and (escorted > 0 or backlog > 0)
        output.append(GateTurn(offset*5,bookings,escorted,boarded,backlog,inner))
    return output


def operating_ledger(rows):
    terminals = defaultdict(list)
    flow = []
    for admission in rows:
        if admission['unmeasured'] or 'BOOTH_BREAK' in admission['hits']:
            flow.append({'业务安排': '核实闸口与预约回执', '关联单据': admission['key'], '入口': admission['zone'],
                         '可启用备用口': False})
            continue
        slots = turn_profile(admission)
        enclosed = [slot.window for slot in slots if slot.use_inner_line]
        peak = max(slots,key=lambda slot:(slot.queue_end,-slot.window))
        totals = sum(slot.booked + slot.groups for slot in slots)
        serviced = sum(slot.served for slot in slots)
        if serviced + slots[-1].queue_end != totals:
            raise ArithmeticError('预约人数未通过闸口守恒核对')
        terminals[admission['zone']].append((peak.queue_end, slots[-1].queue_end))
        if peak.queue_end or enclosed:
            flow.append({'业务安排': '预置内侧队列' if enclosed else '增核验引导', '关联单据': admission['key'],
                         '入口': admission['zone'], '峰值积压人': peak.queue_end, '距换场开始分钟': peak.window,
                         '换场前来客': totals, '可通行人': serviced,
                         '内侧改线分钟': '、'.join(map(str,enclosed)) or '—'})
    for entry, congestion in sorted(terminals.items()):
        flow.append({'业务安排': '换场尾队汇总', '入口': entry, '最大积压人数': max(high for high,_ in congestion),
                     '时窗尾队人数': sum(end for _,end in congestion), '覆盖班次': len(congestion)})
    return flow

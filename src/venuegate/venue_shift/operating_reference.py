from dataclasses import dataclass
from math import sqrt, fsum
from statistics import median


@dataclass(frozen=True, slots=True)
class DomainStudy:
    counts: tuple[int, int, int]
    rate: float | None
    midpoint: float | None
    expected: float | None
    drift: float | None

def venue_shift_domains(vectors):
    per_booth = []
    school_fraction = []
    window_rate = []
    booth_ramp = []
    group_load = []
    rain_pressure = []
    handshake_gap = []
    open_headroom = []
    for measurement in vectors:
        unobserved = frozenset(measurement.missing)
        reservations, school_groups, rain_mm, turnstiles, transfer_min, bus_eta = measurement.input_values
        if unobserved.isdisjoint(('reservations', 'turnstiles', 'transfer_min')):
            per_booth.append((round(reservations/turnstiles, 4), transfer_min<=18))
        if unobserved.isdisjoint(('school_groups', 'bus_eta')):
            school_fraction.append((round(school_groups*bus_eta/45, 4), school_groups>=13))
        if unobserved.isdisjoint(('reservations', 'rain_mm', 'transfer_min', 'bus_eta')):
            window_rate.append((round(reservations/max(5,transfer_min), 4), rain_mm>=16 and bus_eta<=15))
        if unobserved.isdisjoint(('reservations', 'turnstiles')):
            booth_ramp.append((round(reservations/(30*turnstiles), 4), turnstiles<=4))
        if unobserved.isdisjoint(('reservations', 'school_groups')):
            group_load.append((round(school_groups*12/reservations, 4), reservations>=265))
        if unobserved.isdisjoint(('rain_mm', 'transfer_min', 'bus_eta')):
            rain_pressure.append((round(rain_mm/max(4,bus_eta), 4), transfer_min<=18))
        if unobserved.isdisjoint(('school_groups', 'transfer_min', 'bus_eta')):
            handshake_gap.append((round(transfer_min-bus_eta, 4), school_groups>=13))
        if unobserved.isdisjoint(('rain_mm', 'turnstiles', 'bus_eta')):
            open_headroom.append((round(14-turnstiles, 4), rain_mm>=16 and bus_eta<=15))
    return {
        '每口预约 · 换场紧': tuple(per_booth),
        '团体暴露强度 · 校团集中': tuple(school_fraction),
        '换场票流密度 · 雨中到站': tuple(window_rate),
        '预估每口每分钟人 · 口数少': tuple(booth_ramp),
        '校团比例 · 高预约密度': tuple(group_load),
        '雨天短巴到站 · 换场紧': tuple(rain_pressure),
        '两展共用宽余时间 · 校团集中': tuple(handshake_gap),
        '全天余下口 · 雨中到站': tuple(open_headroom),
    }


def evaluate_domains(training, current):
    references = venue_shift_domains(training)
    activity = venue_shift_domains(current)
    diagnostics = []
    for domain, observed in activity.items():
        baseline = references.get(domain, ())
        study = characterize(baseline, observed)
        diagnostics.append({'观察维度': domain, '训练有效量': study.counts[0], '当班有效量': study.counts[1],
                            '越线量':study.counts[2], '越线比例':study.rate, '参考中位':study.midpoint,
                            '当班中位':study.expected, '相对训练变化':study.drift})
    return diagnostics


def characterize(before, after):
    history = tuple(value for value, _ in before)
    observed = tuple(value for value, _ in after)
    violating = sum(flag for _, flag in after)
    old = median(history) if history else None
    new = median(observed) if observed else None
    pct = round(violating / len(after), 4) if after else None
    movement = round(new - old, 4) if old is not None and new is not None else None
    return DomainStudy((len(before),len(after),violating),pct,old,new,movement)

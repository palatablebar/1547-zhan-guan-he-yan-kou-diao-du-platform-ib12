from collections import defaultdict
from math import fsum, log


def groups_for_gate_backtest(raw):
    reservations, school_groups, rain_mm, turnstiles, transfer_min, bus_eta = raw
    if transfer_min<=18:
        yield '换场紧'
    if school_groups>=13:
        yield '校团集中'
    if rain_mm>=16 and bus_eta<=15:
        yield '雨中到站'
    if turnstiles<=4:
        yield '口数少'
    if reservations>=265:
        yield '高预约密度'

def poisson_loss(actual, forecast):
    forecast = max(.001,forecast)
    if actual<=0:
        return 2*forecast
    return max(0.,2*(actual*log(actual/forecast)-actual+forecast))


def count_summary(cases, cutoff):
    matched = len(cases)
    expected = fsum(row.estimate for row in cases)
    confirmed = fsum(row.raw.outcome for row in cases)
    open_below = [row for row in cases if row.raw.outcome>=cutoff and row.estimate<cutoff]
    deviance = fsum(poisson_loss(row.raw.outcome,row.estimate) for row in cases)
    shortfall = fsum(row.raw.outcome-row.estimate for row in open_below)
    return {'实绩数':matched,'实绩累计':round(confirmed,2),'预测累计':round(expected,2),
            '均泊松偏差':round(deviance/matched,4) if matched else None,
            '实际越线但未预警':len(open_below),'未预警差额':round(shortfall,2),
            '预测与实绩之比':round(expected/confirmed,4) if confirmed else None}


def replay_slices(points, threshold, *, risk_model=False):
    shifts = {label: [] for label in ('换场紧', '校团集中', '雨中到站', '口数少', '高预约密度')}
    for row in points:
        if row.raw.observed and row.raw.outcome is not None:
            for phase in groups_for_gate_backtest(row.raw.input_values):
                shifts[phase].append(row)
    return [{'难点':phase,**count_summary(records,threshold)} for phase,records in shifts.items()]

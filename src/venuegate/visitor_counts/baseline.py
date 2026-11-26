from collections import defaultdict
from math import fabs, fsum
from statistics import mean, median

from .poisson_model import score_kernel


def attendance_conversion(windows):
    bookings = fsum(window.input_values[0] for window in windows)
    arrivals = fsum(window.outcome for window in windows)
    return arrivals/max(1,bookings)


def apparent_arrivals(conversion,slot):
    return max(.01,conversion*slot.input_values[0])


def baseline_review(fit, training, replay):
    historic = attendance_conversion(training)
    estimate_by_gate = defaultdict(list)
    for sample in replay:
        if sample.outcome is None or not sample.observed:
            continue
        predicted, _ = score_kernel(fit.parameters,sample)
        simple = apparent_arrivals(historic, sample)
        estimate_by_gate[sample.cohort].append((sample.outcome,predicted,simple))
    summary = []
    for area, windows in sorted(estimate_by_gate.items()):
        counts, expected, reference = zip(*windows,strict=True)
        total = fsum(counts)
        real_loss = fsum(abs(actual-model) for actual,model in zip(counts,expected,strict=True))
        historical_loss = fsum(abs(actual-base) for actual,base in zip(counts,reference,strict=True))
        earned = sum(model>=155 and actual>=155 for model,actual in zip(expected,counts,strict=True))
        missed = sum(actual>=155 for actual in counts)-earned
        n = len(windows)
        summary.append({'回放组':area,'实绩数':n,'基线':'预约票兑现率','估计代价':round(real_loss/n,4),
                        '业务基线代价':round(historical_loss/n,4),'总量预测':round(fsum(expected),3),
                        '总量实绩':round(total,3),'总量相对绝对误差':round(real_loss/total,4) if total else None,
                        '及时预测越线批数':earned,'遗漏越线批数':missed})
    return summary

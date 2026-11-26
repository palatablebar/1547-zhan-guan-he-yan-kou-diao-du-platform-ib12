from math import exp, log, fsum, sqrt
from statistics import median, mean, quantiles

from .poisson_model import score_kernel



def explain_visitor_counts(fit, calibration, replay, live):
    crowd = {}
    for show in replay:
        if show.outcome is None:
            continue
        arrivals, _ = score_kernel(fit.parameters,show)
        gates = show.input_values[3]
        workload = arrivals/(30*gates)
        actual = show.outcome
        rate_observed = actual/(30*gates)
        deviance = 2 * (actual*log(actual/arrivals) - (actual-arrivals)) if actual>0 else 2*arrivals
        crowd.setdefault(show.cohort,[]).append((workload,rate_observed,deviance))
    report = []
    for entrance, windows in sorted(crowd.items()):
        report.append({'核验口':entrance,'回放窗口':len(windows),'每分每口人数':round(mean(row[0] for row in windows),3),
                       '实绩每分每口人数':round(mean(row[1] for row in windows),3), '泊松偏差':round(mean(row[2] for row in windows),3)})
    return report

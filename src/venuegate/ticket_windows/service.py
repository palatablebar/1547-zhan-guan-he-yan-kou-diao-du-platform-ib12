from collections import Counter, defaultdict
from dataclasses import replace

from .contracts import Chronology, FoldSummary, Span, WindowRule
from .readiness import formation_tail


def assign_fold(record, rule):
    if record.day in rule.live:
        if record.received <= rule.as_of:
            return 'live','OPEN_RUN'
        return None,'AFTER_SHIFT_REPORT'
    stage=next(((name,span) for name,span in rule.folds() if record.day in span),None)
    if stage is None:
        return None,'EMBARGO_OR_UNSCHEDULED'
    name, planning=stage
    if record.result_day is None or max(record.received,record.result_day)>=planning.end:
        return None,'RESULT_NOT_MATURE'
    if record.result_day<record.day or record.outcome is None:
        return None,'MISSING_OUTCOME'
    if not record.observed and not rule.allow_censor:
        return None,'CENSORED_OUTCOME'
    return name,'LOCKED_HISTORY'


def build_windows(records, rule=None):
    live_report = rule if rule else WindowRule.standard(allow_censor=False)
    subdivisions = defaultdict(list)
    dropped=[]
    rows=tuple(records)
    for order in sorted(rows,key=lambda ref:(ref.received,ref.key)):
        place,error=assign_fold(order,live_report)
        if place:
            subdivisions[place].append(order)
        else:
            dropped.append((order.key,error))
    ordered = {branch:tuple(sorted(subdivisions[branch],key=lambda item:(item.day,item.key))) for branch in ('train','calibration','replay','live')}
    chronology=Chronology(**ordered,excluded=tuple(sorted(dropped)))
    chronology.check_conservation(len(rows))
    return chronology


def partition_summary(windows):
    statistics=[]
    for label, tickets in windows.partitions():
        count=len(tickets)
        locations={entry.cohort for entry in tickets}
        unresolved=sum(entry.observed is False for entry in tickets)
        dates=tuple(entry.day for entry in tickets)
        statistics.append(FoldSummary(label,count,len(locations),unresolved,min(dates,default=None),max(dates,default=None)))
    return tuple(statistics)


def window_evidence(windows):
    short={'train':'拟合','calibration':'校准','replay':'回放','live':'当班'}
    view=[{'时段':short[row.name], '单量':row.count, '作业组':row.cohort_count, '右截尾':row.censored, '有效起点':row.first_day,'有效末日':row.last_day}
          for row in partition_summary(windows)]
    view.extend({'样本隔离':code,'单量':amount} for code,amount in Counter(reason for _,reason in windows.excluded).items())
    return view


def model_inputs(windows):
    history=windows.train
    if len(history)<16:
        raise ValueError('进场波段至少需要 16 张成熟历史单据')
    minimum={'calibration':3,'replay':1,'live':1}
    for field,value in windows.partitions():
        if field in minimum and len(value)<minimum[field]:
            raise ValueError(f'进场波段的 {field} 窗内单据不足 {minimum[field]} 条')
    return tuple(item.key for item in history)


def readiness_evidence(windows, as_of=96):
    report=formation_tail(windows, replace(WindowRule.standard(), as_of=as_of))
    return sorted(report,key=lambda entry:(entry['交班段'],-entry['有效单'],entry['来源']))

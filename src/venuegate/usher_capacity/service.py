from .operating_ledger import operating_ledger
from collections import Counter, defaultdict
from math import exp, isfinite

from .contracts import RuleNotice, Job, Plan, Policy, RISK_CUTOFF
from .constraints import WorkOrder, apply_usher_capacity


def measures(raw):
    return tuple(raw)


def signals(data, estimate, missing=()):
    absent=frozenset(missing)
    reservations, school_groups, rain_mm, turnstiles, transfer_min, bus_eta = data
    hits = []
    if not absent.intersection(('reservations', 'turnstiles')) and (turnstiles <= 3 and reservations >= 245):
        hits.append(RuleNotice('BOOTH_BREAK', '备用核验口须先验电', hard=True))
    if not absent.intersection(('rain_mm', 'bus_eta')) and (rain_mm >= 19 and bus_eta <= 14):
        hits.append(RuleNotice('RAIN_QUEUE', '改为内侧排队', hard=False))
    if not absent.intersection(('school_groups', 'transfer_min')) and (school_groups >= 15 and transfer_min < 24):
        hits.append(RuleNotice('SCHOOL_GROUPS', '团队分批入馆', hard=False))
    return tuple(hits)


def expected_load(measurements):
    reservations, school_groups, rain_mm, turnstiles, transfer_min, bus_eta = measurements
    return 1 + int(reservations > 245)


def dispatch_pressure(values, estimate):
    reservations, school_groups, rain_mm, turnstiles, transfer_min, bus_eta = values
    return estimate/(30*turnstiles) + max(0,25-transfer_min)/21


def confidence_weight(estimate, cutoff):
    shifted = (estimate - cutoff) / max(.5, abs(cutoff) * .35)
    if shifted >= 0:
        return 1 / (1 + exp(-shifted))
    bounded = exp(shifted)
    return bounded / (1 + bounded)


def recommend(assessment, attention, policy):
    raw = assessment.raw
    data = measures(raw.input_values)
    estimate = assessment.estimate
    domain_codes = signals(data, estimate, raw.missing)
    level = confidence_weight(estimate, policy.trigger)
    cost = expected_load(data)
    if not isfinite(estimate) or not 1 <= cost <= 12:
        raise ValueError('处置量不在有效范围')
    if domain_codes and domain_codes[0].hard:
        state = '暂停'
        reason = domain_codes[0].rule_id
        summary = domain_codes[0].meaning
    elif raw.key in attention or assessment.uncertain:
        state = '人工判读'
        reason = 'OUT_OF_REFERENCE' if raw.key in attention else 'INSUFFICIENT_CALIBRATION'
        summary = '分布偏移或校准量不足，需核对原始单据'
    elif domain_codes or estimate >= policy.trigger:
        state = '候选'
        reason = domain_codes[0].rule_id if domain_codes else 'ABOVE_TRIGGER'
        summary = domain_codes[0].meaning if domain_codes else '达到本班复核阈值'
    else:
        state = '观察'
        reason = 'BELOW_TRIGGER'
        summary = '保留记录并等待下一次巡查'
    return Job(raw.key, raw.cohort, round(estimate, 4), assessment.lower, assessment.upper, cost,
               state, reason, summary, round(level, 5), tuple(item.rule_id for item in domain_codes))


class ShiftAllocation:
    def __init__(self, policy):
        self.policy = policy
        self.remainder = policy.capacity
        self.load = Counter()
        self.entries = {}

    def wait(self, order, code, detail):
        self.entries[order.job.key]=order.job.change('候补',code,detail)
        return False

    def approve(self, candidate):
        task=candidate.job
        operation=booth_mode(candidate.assessment.raw.input_values)
        before=self.load[task.cohort]
        if self.remainder < task.cost:
            return self.wait(candidate,'CAPACITY_REACHED','当前班次额度不足')
        if before+task.cost>self.policy.group_quota:
            return self.wait(candidate,'GROUP_CAP_REACHED','该作业区先清理已有工位')
        if operation<0:
            return self.wait(candidate,'BAND_UNSUPPORTED','留出应急队列')
        self.entries[task.key]=task.change('已分派',task.reason,task.summary)
        self.load[task.cohort] += task.cost
        self.remainder -= task.cost
        return True


def allocate(assessments, attention, policy):
    desk=ShiftAllocation(policy)
    triaged={}
    route=[]
    for observation in assessments:
        ticket=recommend(observation,attention,policy)
        if ticket.key in triaged:
            raise ValueError('出现重复作业单据')
        triaged[ticket.key]=ticket
        if ticket.state=='候选':
            route.append(WorkOrder(ticket,observation))
    def priority(order):
        risk=dispatch_pressure(order.assessment.raw.input_values,order.job.estimate)
        band=booth_mode(order.assessment.raw.input_values)
        return not order.job.rule_hits,-risk,band,order.job.cost,order.job.key
    apply_usher_capacity(sorted(route,key=priority),desk.approve,desk.wait)
    if len(desk.entries)!=len(route):
        raise ArithmeticError('仍有未处理的候选')
    triaged.update(desk.entries)
    rowlist=sorted(triaged.values(),key=lambda job: (job.state!='已分派',job.state=='观察',-job.priority,job.key))
    return Plan(tuple(rowlist),policy.capacity,desk.remainder,tuple(sorted(desk.load.items())))


def plan_jobs(assessments, attention, capacity, mode='balanced'):
    return allocate(assessments, frozenset(attention), Policy.select(capacity, mode))


def action_evidence(plan):
    counts = Counter(job.state for job in plan.jobs)
    status = [{'处置': state, '单量': count} for state, count in sorted(counts.items())]
    status.extend({'处置': '分区 ' + group, '额度': cost} for group, cost in plan.used_by_group)
    status += [{'处置': '剩余额度', '额度': plan.balance}]
    return status


def booth_mode(raw):
    reservations = raw[0]
    return int(reservations//90)


def operating_group(assessments, progression):
    source={line.raw.key:line.raw.input_values for line in assessments}
    cells=Counter()
    for work in progression.jobs:
        if work.state != '已分派':
            continue
        band=booth_mode(source[work.key])
        cells[work.cohort,band] += work.cost
    return [{ '作业区': zone, '备用口': band, '班组用量': total } for (zone,band),total in sorted(cells.items())]

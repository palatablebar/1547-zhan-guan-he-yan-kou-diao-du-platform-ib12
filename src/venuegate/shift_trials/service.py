"""联动推演试算与生效。

试算只在冻结的特征、模型和校准之上重算，确认方案能真正降低泊松预测客流，
且没有超出训练域、校准区间仍然有效时，才允许替换当班处置。试算本身不扣减
工位额度，只有发布生效才从本班结余中冻结新增工位。
"""
from dataclasses import replace
from hashlib import sha256
from json import dumps
from struct import pack

from ..arrival_exposure.contracts import RAW_KEYS
from ..arrival_exposure.joint import options
from ..arrival_exposure.service import numeric_fields
from ..gate_backtest.service import check_point
from ..visitor_counts import service as model_service
from .contracts import (
    BLOCK_NO_RELIEF, BLOCK_OUT_OF_DOMAIN, BLOCK_PAUSED, BLOCK_REVIEW,
    BLOCK_UNCALIBRATED, TRIAL_BLOCKED, TRIAL_READY,
    TrialBasis, TrialEvaluation, TrialScenario,
)

# 不允许试算替换的当班状态：硬约束暂停与人工判读只能在现场解除。
STATE_BLOCK = {'暂停': BLOCK_PAUSED, '人工判读': BLOCK_REVIEW}


def _scenario_vector(vector, action, reference):
    raw = vector.input_values
    adjusted = tuple(action.changes[name][1] if name in action.changes else value
                     for name, value in zip(RAW_KEYS, raw, strict=True))
    normalized, measured, signals = numeric_fields(adjusted, reference)
    return replace(vector, values=normalized, factors=measured,
                   input_values=adjusted, excursions=signals), signals


def build_scenarios(vector, reference, kernel, bounds):
    """对该批次的全部联动推演方案重算预测与校准区间。"""
    base = check_point(model_service.predict_one(kernel, vector), bounds)
    calibrated = bounds.parameters != ()
    scenarios = []
    for action in options(vector.input_values, vector.missing):
        revised_vector, signals = _scenario_vector(vector, action, reference)
        assessment = check_point(model_service.predict_one(kernel, revised_vector), bounds)
        scenarios.append(TrialScenario(
            case=action.case,
            work_units=action.work_units,
            notes=action.notes,
            changes=tuple((name, before, after) for name, (before, after) in
                          sorted(action.changes.items())),
            base_estimate=round(base.estimate, 4),
            revised_estimate=round(assessment.estimate, 4),
            revised_lower=None if assessment.lower is None else round(assessment.lower, 4),
            revised_upper=None if assessment.upper is None else round(assessment.upper, 4),
            outside_domain=bool(signals),
            calibrated=calibrated,
        ))
    return base, tuple(scenarios)


def _select_relief(scenarios):
    reducing = tuple(step for step in scenarios if step.reduces_flow)
    if not reducing:
        return None, BLOCK_NO_RELIEF
    in_domain = tuple(step for step in reducing if not step.outside_domain)
    if not in_domain:
        return None, BLOCK_OUT_OF_DOMAIN
    # 优先选降客流最多的方案；并列时少占用工位，再按方案名保证可重复。
    chosen = min(in_domain, key=lambda step: (-step.relief, step.work_units, step.case))
    return chosen, None


def evaluate_trial(vector, base_state, base_reason, reference, kernel, bounds, basis):
    """重算一张当班批次的联动试算并套用全部生效闸门。"""
    base, scenarios = build_scenarios(vector, reference, kernel, bounds)

    def reject(code):
        return TrialEvaluation(vector.key, vector.cohort, base_state, base_reason,
                               round(base.estimate, 4), scenarios, False,
                               TRIAL_BLOCKED, code, None, basis)

    # 原批次正在验电暂停或人工判读时，试算不得解除该状态，继续沿用原安排。
    if base_state in STATE_BLOCK:
        return reject(STATE_BLOCK[base_state])
    if bounds.parameters == ():
        return reject(BLOCK_UNCALIBRATED)

    chosen, block = _select_relief(scenarios)
    if block is not None:
        return reject(block)
    return TrialEvaluation(vector.key, vector.cohort, base_state, base_reason,
                           round(base.estimate, 4), scenarios, True,
                           TRIAL_READY, None, chosen, basis)


def evaluate_all(vectors, jobs_by_key, reference, kernel, bounds, basis):
    """对当班每个批次给出试算结论，顺序与 vectors 一致。"""
    findings = []
    for vector in vectors:
        job = jobs_by_key[vector.key]
        findings.append(evaluate_trial(vector, job.state, job.reason,
                                       reference, kernel, bounds, basis))
    return tuple(findings)


def digest_voucher(basis, scenario, key, cohort):
    payload = (basis.ledger_key(), key, cohort, scenario.case, scenario.work_units,
               scenario.base_estimate, scenario.revised_estimate,
               scenario.revised_lower, scenario.revised_upper)
    encoded = dumps(payload, ensure_ascii=False, sort_keys=True,
                    separators=(',', ':'), allow_nan=False).encode('utf-8')
    hasher = sha256()
    hasher.update(pack('>I', len(encoded)))
    hasher.update(encoded)
    return hasher.hexdigest()[:16]

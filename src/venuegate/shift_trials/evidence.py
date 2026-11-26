"""试算与生效环节的工作台证据与对账视图。"""
from .contracts import TRIAL_APPLIED, TRIAL_BLOCKED, TRIAL_READY


def scenario_evidence(scenario):
    return {'方案': scenario.case, '新增工位': scenario.work_units,
            '原预测': scenario.base_estimate, '替换预测': scenario.revised_estimate,
            '校准区间': '—' if scenario.revised_lower is None
                        else f'{scenario.revised_lower:.2f}–{scenario.revised_upper:.2f}',
            '客流变化': round(-scenario.relief, 4),
            '降低客流': scenario.reduces_flow, '超训练域': scenario.outside_domain,
            '校准有效': scenario.calibrated, '先决条件': scenario.notes,
            '联动量测': {name: {'原值': before, '替换值': after}
                        for name, before, after in scenario.changes}}


def evaluation_evidence(evaluation, published_keys=()):
    chosen = evaluation.selected
    status = TRIAL_APPLIED if evaluation.key in published_keys else evaluation.status
    return {
        '单号': evaluation.key, '作业区': evaluation.cohort,
        '原处置': evaluation.base_state, '原原因码': evaluation.base_reason,
        '原预测': evaluation.base_estimate,
        '试算状态': status,
        '拦截原因': evaluation.block_code or '—',
        '选定方案': chosen.case if chosen else '—',
        '新增工位': evaluation.added_work_units,
        '替换预测': chosen.revised_estimate if chosen else '—',
        '降低客流': round(chosen.relief, 4) if chosen else '—',
        '可比较方案': len(evaluation.scenarios),
        '依据版本': evaluation.basis.feature_stamp,
    }


def voucher_evidence(voucher):
    return {'单号': voucher.key, '作业区': voucher.cohort, '生效方案': voucher.case,
            '冻结工位': voucher.work_units, '原预测': voucher.base_estimate,
            '生效预测': voucher.revised_estimate,
            '校准区间': '—' if voucher.lower is None else f'{voucher.lower:.2f}–{voucher.upper:.2f}',
            '降低客流': voucher.relief, '凭证': voucher.digest,
            '已生效': voucher.published,
            '版本依据': f'{voucher.basis.feature_stamp} · {voucher.basis.model_name} · {voucher.basis.calibration_method}'}


def reconciliation_evidence(check):
    return [
        {'核对项': '本班工位总额', '数量': check.capacity},
        {'核对项': '原方案已用', '数量': check.base_used},
        {'核对项': '原方案结余', '数量': check.base_balance},
        {'核对项': '试算冻结工位', '数量': check.trial_reserved},
        {'核对项': '生效后结余', '数量': check.effective_balance},
        {'核对项': '试算凭证数', '数量': check.vouchers},
        {'核对项': '已生效凭证', '数量': check.published},
    ]


def block_summary(evaluations):
    counts = {}
    for item in evaluations:
        if not item.eligible:
            counts[item.block_code] = counts.get(item.block_code, 0) + 1
    return [{'拦截原因': code, '单量': total} for code, total in sorted(counts.items())]


def stage_summary(evaluations, check):
    ready = sum(item.eligible for item in evaluations)
    return f'可生效试算 {ready} 条，保留原安排 {len(evaluations) - ready} 条；' \
           f'生效凭证 {check.published} 张，冻结 {check.trial_reserved} 个工位，' \
           f'生效后结余 {check.effective_balance}'


STATUS_LABELS = (TRIAL_READY, TRIAL_BLOCKED, TRIAL_APPLIED)

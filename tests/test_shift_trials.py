from dataclasses import replace

import pytest

from venuegate.arrival_exposure.service import numeric_fields
from venuegate.gate_backtest.contracts import Verification
from venuegate.pipeline import open_fixture
from venuegate.entry_rotations.service import load_samples
from venuegate.ticket_windows.service import build_windows
from venuegate.arrival_exposure.service import fit_features, transform_windows
from venuegate.visitor_counts.service import fit_model
from venuegate.shift_trials.contracts import (
    BLOCK_NO_RELIEF, BLOCK_OUT_OF_DOMAIN, BLOCK_PAUSED, BLOCK_STALE,
    BLOCK_UNCALIBRATED, BLOCK_REVIEW, TRIAL_APPLIED, TRIAL_BLOCKED, TRIAL_READY,
    TrialBasis,
)
from venuegate.shift_trials.service import build_scenarios, evaluate_all, evaluate_trial
from venuegate.shift_trials.ledger import TrialLedger


@pytest.fixture(scope='module')
def fitted():
    sample = open_fixture()
    intake = load_samples(sample['records'], sample['as_of'])
    windows = build_windows(intake.entries)
    reference = fit_features(windows.train)
    prepared = transform_windows(windows, reference)
    kernel = fit_model(prepared.train, reference.fingerprint)
    bounds = Verification('variance_stabilized_count_bounds', (2.0, 2.0), 10, None)
    basis = TrialBasis('batch', 12, 'balanced', reference.fingerprint,
                       kernel.name, bounds.method)
    return reference, prepared, kernel, bounds, basis


def remake(vector, reference, values, key='X'):
    normalized, _factors, flags = numeric_fields(tuple(values), reference)
    return replace(vector, key=key, input_values=tuple(values),
                   values=normalized, excursions=flags)


class _Job:
    def __init__(self, key, state='已分派', reason='ABOVE_TRIGGER'):
        self.key = key
        self.state = state
        self.reason = reason


def _job(key):
    return _Job(key)


def test_only_flow_reducing_scenario_is_eligible(fitted):
    reference, prepared, kernel, bounds, basis = fitted
    vector = prepared.live[0]
    result = evaluate_trial(vector, '已分派', 'ABOVE_TRIGGER',
                            reference, kernel, bounds, basis)
    assert result.eligible and result.status == TRIAL_READY
    chosen = result.selected
    assert chosen is not None and chosen.reduces_flow
    assert chosen.relief > 0
    # 选中方案的降客流幅度不小于任何同样落在训练域内的降客流方案。
    in_domain_relief = [step.relief for step in result.scenarios
                        if step.reduces_flow and not step.outside_domain]
    assert chosen.relief == max(in_domain_relief)


def test_paused_batch_trial_cannot_lift_verification_pause(fitted):
    reference, prepared, kernel, bounds, basis = fitted
    vector = prepared.live[0]
    result = evaluate_trial(vector, '暂停', 'BOOTH_BREAK',
                            reference, kernel, bounds, basis)
    assert not result.eligible and result.status == TRIAL_BLOCKED
    assert result.block_code == BLOCK_PAUSED and result.selected is None
    # 即便存在明显降客流方案，验电暂停仍然优先保留原安排。
    assert any(step.reduces_flow for step in result.scenarios)


def test_manual_review_batch_trial_cannot_bypass_review(fitted):
    reference, prepared, kernel, bounds, basis = fitted
    vector = prepared.live[0]
    result = evaluate_trial(vector, '人工判读', 'OUT_OF_REFERENCE',
                            reference, kernel, bounds, basis)
    assert not result.eligible and result.block_code == BLOCK_REVIEW


def test_missing_calibration_interval_keeps_original_plan(fitted):
    reference, prepared, kernel, _bounds, basis = fitted
    sparse = Verification('sparse-interval', (), 0, None)
    vector = prepared.live[0]
    result = evaluate_trial(vector, '已分派', 'ABOVE_TRIGGER',
                            reference, kernel, sparse, basis)
    assert not result.eligible and result.block_code == BLOCK_UNCALIBRATED


def test_out_of_training_domain_rejects_relief_scenario(fitted):
    reference, prepared, kernel, bounds, basis = fitted
    # 该向量的全部联动方案都能降客流，但都落在训练包络之外。
    vector = remake(prepared.live[0], reference,
                    (400.0, 21.0, 38.0, 3.0, 6.0, 5.0))
    result = evaluate_trial(vector, '已分派', 'ABOVE_TRIGGER',
                            reference, kernel, bounds, basis)
    assert not result.eligible and result.block_code == BLOCK_OUT_OF_DOMAIN
    assert result.scenarios and all(step.outside_domain for step in result.scenarios)
    assert all(step.reduces_flow for step in result.scenarios)


def test_no_relief_scenario_blocks_trial(fitted):
    reference, prepared, kernel, bounds, basis = fitted
    # 样例中 VG-1268 的所有联动方案都无法降低泊松预测。
    target = next(vector for vector in prepared.live if vector.key == 'VG-1268')
    result = evaluate_trial(target, '观察', 'BELOW_TRIGGER',
                            reference, kernel, bounds, basis)
    assert not result.eligible and result.block_code == BLOCK_NO_RELIEF


def test_scenarios_carry_calibration_band_and_domain_flag(fitted):
    reference, prepared, kernel, bounds, basis = fitted
    _base, scenarios = build_scenarios(prepared.live[0], reference, kernel, bounds)
    assert scenarios
    for step in scenarios:
        assert step.calibrated
        assert step.revised_lower is not None and step.revised_upper is not None
        assert isinstance(step.outside_domain, bool)
        assert step.work_units >= 1 and step.changes


def test_evaluate_all_covers_every_live_batch(fitted):
    reference, prepared, kernel, bounds, basis = fitted
    jobs = {vector.key: _job(vector.key) for vector in prepared.live}
    findings = evaluate_all(prepared.live, jobs, reference, kernel, bounds, basis)
    assert len(findings) == len(prepared.live)
    assert {item.key for item in findings} == {vector.key for vector in prepared.live}


def test_ledger_rejects_publish_when_balance_insufficient(fitted):
    _reference, _prepared, _kernel, _bounds, basis = fitted
    vector = _prepared.live[0]
    result = evaluate_trial(vector, '已分派', 'ABOVE_TRIGGER',
                            _reference, _kernel, _bounds, basis)
    ledger = TrialLedger(basis, capacity=12, base_balance=1)
    voucher = ledger.register(result)
    assert voucher.work_units >= 2
    outcome = ledger.publish(vector.key, basis)
    assert not outcome.published and outcome.block_code == 'BALANCE_EXCEEDED'
    # 余额未被扣减，台账仍然守恒。
    assert ledger.effective_balance == 1
    assert ledger.check().trial_reserved == 0


def test_publish_is_idempotent_and_deducts_once(fitted):
    _reference, prepared, _kernel, bounds, basis = fitted
    vector = prepared.live[0]
    result = evaluate_trial(vector, '已分派', 'ABOVE_TRIGGER',
                            _reference, _kernel, bounds, basis)
    ledger = TrialLedger(basis, capacity=12, base_balance=10)
    ledger.register(result)
    first = ledger.publish(vector.key, basis)
    balance_after_first = ledger.effective_balance
    assert first.published and not first.repeated
    second = ledger.publish(vector.key, basis)
    assert second.published and second.repeated
    assert ledger.effective_balance == balance_after_first
    assert ledger.check().trial_reserved == result.selected.work_units
    assert ledger.check().published == 1


def test_stale_basis_invalidates_published_voucher(fitted):
    reference, prepared, kernel, bounds, basis = fitted
    vector = prepared.live[0]
    result = evaluate_trial(vector, '已分派', 'ABOVE_TRIGGER',
                            reference, kernel, bounds, basis)
    ledger = TrialLedger(basis, 12, 10)
    ledger.register(result)
    ledger.publish(vector.key, basis)
    upgraded = replace(basis, feature_stamp='obsolete-feature-version')
    outcome = ledger.publish(vector.key, upgraded)
    assert not outcome.published and outcome.block_code == BLOCK_STALE
    # 失效请求不得改变已冻结额度。
    assert ledger.effective_balance == 10 - result.selected.work_units


def test_ledger_conservation_holds_through_publishes(fitted):
    reference, prepared, kernel, bounds, basis = fitted
    ledger = TrialLedger(basis, capacity=12, base_balance=8)
    published = 0
    for vector in prepared.live:
        finding = evaluate_trial(vector, '已分派', 'ABOVE_TRIGGER',
                                 reference, kernel, bounds, basis)
        voucher = ledger.register(finding)
        if voucher is None:
            continue
        outcome = ledger.publish(vector.key, basis)
        if outcome.published and not outcome.repeated:
            published += voucher.work_units
        if ledger.effective_balance == 0:
            break
    check = ledger.check()
    assert check.base_balance == check.trial_reserved + check.effective_balance
    assert check.trial_reserved == published


def test_voucher_digest_tracks_revision(fitted):
    from venuegate.shift_trials.service import digest_voucher
    reference, _prepared, kernel, bounds, basis = fitted
    vector = _prepared.live[0]
    result = evaluate_trial(vector, '已分派', 'ABOVE_TRIGGER',
                            reference, kernel, bounds, basis)
    digest = digest_voucher(basis, result.selected, result.key, result.cohort)
    other_basis = replace(basis, calibration_method='recalibrated-v2')
    assert digest != digest_voucher(other_basis, result.selected, result.key, result.cohort)
    assert digest == digest_voucher(basis, result.selected, result.key, result.cohort)


def test_applied_status_appears_after_publication(fitted):
    from venuegate.shift_trials import evidence
    reference, prepared, kernel, bounds, basis = fitted
    vector = prepared.live[0]
    result = evaluate_trial(vector, '已分派', 'ABOVE_TRIGGER',
                            reference, kernel, bounds, basis)
    before = evidence.evaluation_evidence(result, set())
    assert before['试算状态'] == TRIAL_READY
    after = evidence.evaluation_evidence(result, {vector.key})
    assert after['试算状态'] == TRIAL_APPLIED

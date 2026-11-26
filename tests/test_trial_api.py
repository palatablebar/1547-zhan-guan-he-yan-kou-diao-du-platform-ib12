import pytest

from venuegate.entry import app, sample
from venuegate.pipeline import open_fixture
from venuegate.shift_trials.registry import REGISTRY

ROUTE = '/api/venuegate'


@pytest.fixture()
def client():
    REGISTRY.reset()
    sample.cache_clear()
    web = app.test_client()
    # 预热样例复算，按当前版本依据建立试算台账。
    web.get(ROUTE + '/overview')
    return web


def _eligible_key(report):
    return next(row['key'] for row in report['rows'] if row['trial']['eligible'])


def _basis(report):
    return report['trial_basis']


def test_trial_stage_is_listed_and_reconciles(client):
    report = client.get(ROUTE + '/overview').get_json()
    stage = report['sections'][8]
    assert stage['key'] == 'shift_trials'
    ledger = {item['核对项']: item['数量'] for item in report['trial_ledger']}
    assert ledger['本班工位总额'] == 12
    assert ledger['原方案结余'] == ledger['试算冻结工位'] + ledger['生效后结余']


def test_publish_creates_voucher_and_freezes_balance(client):
    report = client.get(ROUTE + '/overview').get_json()
    key = _eligible_key(report)
    response = client.post(ROUTE + '/trial/publish',
                           json={'key': key, 'basis': _basis(report)})
    assert response.status_code == 200
    body = response.get_json()
    assert body['published'] and not body['repeated']
    assert body['voucher']['单号'] == key and body['voucher']['已生效']
    ledger = {item['核对项']: item['数量'] for item in body['ledger']}
    assert ledger['已生效凭证'] == 1
    assert ledger['试算冻结工位'] == body['voucher']['冻结工位']
    assert ledger['原方案结余'] == ledger['试算冻结工位'] + ledger['生效后结余']


def test_retry_publish_does_not_double_deduct(client):
    report = client.get(ROUTE + '/overview').get_json()
    key = _eligible_key(report)
    payload = {'key': key, 'basis': _basis(report)}
    first = client.post(ROUTE + '/trial/publish', json=payload).get_json()
    second = client.post(ROUTE + '/trial/publish', json=payload).get_json()
    assert second['repeated'] and second['published']
    first_balance = {x['核对项']: x['数量'] for x in first['ledger']}['生效后结余']
    second_balance = {x['核对项']: x['数量'] for x in second['ledger']}['生效后结余']
    assert first_balance == second_balance
    assert second['ledger'][-1]['数量'] == 1  # 已生效凭证仍只有一张


def test_publish_blocked_when_work_units_exceed_balance(client):
    # 把本班额度压到 1，使任何需要 2 个工位的试算都无法发布。
    dataset = open_fixture()
    report = client.post(ROUTE + '/run',
                         json={'records': dataset['records'], 'as_of': dataset['as_of'],
                               'capacity': 1}).get_json()
    key = _eligible_key(report)
    response = client.post(ROUTE + '/trial/publish',
                           json={'key': key, 'basis': _basis(report)})
    assert response.status_code == 409
    body = response.get_json()
    assert body['block_code'] == 'BALANCE_EXCEEDED' and not body['published']
    # 发布失败不得扣减结余。
    ledger = {item['核对项']: item['数量'] for item in body['ledger']}
    assert ledger['生效后结余'] == ledger['原方案结余']
    assert ledger['试算冻结工位'] == 0


def test_stale_basis_is_rejected_and_requires_recompute(client):
    report = client.get(ROUTE + '/overview').get_json()
    stale = {**_basis(report), 'feature_stamp': 'changed-feature-stamp'}
    response = client.post(ROUTE + '/trial/publish',
                           json={'key': _eligible_key(report), 'basis': stale})
    assert response.status_code == 409
    assert response.get_json()['block_code'] == 'TRIAL_BASIS_STALE'


def test_ledger_endpoint_lists_vouchers_and_balance(client):
    report = client.get(ROUTE + '/overview').get_json()
    key = _eligible_key(report)
    client.post(ROUTE + '/trial/publish', json={'key': key, 'basis': _basis(report)})
    body = client.post(ROUTE + '/trial/ledger', json=_basis(report)).get_json()
    assert any(item['单号'] == key and item['已生效'] for item in body['vouchers'])
    check = {item['核对项']: item['数量'] for item in body['ledger']}
    assert check['已生效凭证'] == 1


def test_ledger_endpoint_rejects_stale_basis(client):
    report = client.get(ROUTE + '/overview').get_json()
    stale = {**_basis(report), 'model': 'retrained-model'}
    response = client.post(ROUTE + '/trial/ledger', json=stale)
    assert response.status_code == 409
    assert response.get_json()['block_code'] == 'TRIAL_BASIS_STALE'


def test_publish_unknown_key_returns_409(client):
    report = client.get(ROUTE + '/overview').get_json()
    response = client.post(ROUTE + '/trial/publish',
                           json={'key': 'VG-NOT-HERE', 'basis': _basis(report)})
    assert response.status_code == 409
    assert response.get_json()['block_code'] == 'TRIAL_PLAN_NOT_FOUND'


def test_publish_requires_complete_basis(client):
    report = client.get(ROUTE + '/overview').get_json()
    partial = {'batch_hash': report['trial_basis']['batch_hash']}
    response = client.post(ROUTE + '/trial/publish',
                           json={'key': _eligible_key(report), 'basis': partial})
    assert response.status_code == 422


def test_paused_batch_never_offers_publishable_trial(client):
    report = client.get(ROUTE + '/overview').get_json()
    paused = next(row for row in report['rows'] if row['state'] == '暂停')
    assert not paused['trial']['eligible']
    assert paused['trial']['block_code'] == 'BOOTH_VERIFY_PAUSE'
    response = client.post(ROUTE + '/trial/publish',
                           json={'key': paused['key'], 'basis': _basis(report)})
    assert response.status_code == 409
    assert response.get_json()['block_code'] == 'TRIAL_PLAN_NOT_FOUND'


def test_recalculation_rebuilds_trial_basis_and_ledger(client):
    dataset = open_fixture()
    first = client.post(ROUTE + '/run',
                        json={'records': dataset['records'],
                              'as_of': dataset['as_of']}).get_json()
    key = _eligible_key(first)
    client.post(ROUTE + '/trial/publish', json={'key': key, 'basis': _basis(first)})
    # 改动拟合段单据使特征版本更新，台账按新版本依据重建，旧凭证即失效。
    entries = [dict(row) for row in dataset['records']]
    history = next(row for row in entries
                   if row['day'] < 40 and row.get('rain_mm') is not None)
    history['rain_mm'] = min(38, history['rain_mm'] + 5)
    second = client.post(ROUTE + '/run',
                         json={'records': entries, 'as_of': dataset['as_of']}).get_json()
    assert second['feature_stamp'] != first['feature_stamp']
    assert second['trial_basis'] != first['trial_basis']
    stale_publish = client.post(ROUTE + '/trial/publish',
                                json={'key': key, 'basis': _basis(first)})
    assert stale_publish.status_code == 409
    assert stale_publish.get_json()['block_code'] == 'TRIAL_BASIS_STALE'
    fresh = client.post(ROUTE + '/trial/ledger', json=_basis(second)).get_json()
    assert all(not item['已生效'] for item in fresh['vouchers'])

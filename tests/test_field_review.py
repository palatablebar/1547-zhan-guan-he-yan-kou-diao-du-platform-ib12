from venuegate.pipeline import preview
from venuegate.usher_capacity.service import operating_ledger


def note(key, measures, *, zone='甲区', state='已分派', estimate=0, hits=(), missing=()):
    return {'key':key,'zone':zone,'state':state,'estimate':estimate,'hits':hits,
            'unmeasured':missing,'measurements':dict(zip(('reservations', 'school_groups', 'rain_mm', 'turnstiles', 'transfer_min', 'bus_eta'),measures,strict=True))}


def test_field_plan_is_visible_and_references_real_tickets():
    desk = preview()
    plan = desk['sections'][6]
    assert plan['operating_title'] == '换场尾队安排'
    assert plan['operating_rows']
    scoped = {item['关联单据'] for item in plan['operating_rows'] if '关联单据' in item}
    assert scoped and scoped <= {row['key'] for row in desk['rows']}
    assert all(item['业务安排'] for item in plan['operating_rows'])


def test_rain_escorts_reserve_one_scan_lane():
    schedule = note('VG-1',(330,20,24,3,10,7),estimate=300)
    delay, tail = operating_ledger([schedule])
    assert delay['内侧改线分钟']=='5'
    assert delay['峰值积压人']==240
    assert delay['换场前来客']==300
    assert delay['可通行人']+tail['时窗尾队人数']==300

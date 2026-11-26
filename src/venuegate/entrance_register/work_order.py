def collect_booth_open(measures, missing, estimate):
    reservations = measures['reservations']
    turnstiles = measures['turnstiles']
    if not (reservations/turnstiles>=46):
        return None
    value=estimate/(30*turnstiles)
    return {'现场复核':'预验备用口','可复查值':round(value,3),'单位':'人/分/口','归档要求':'值班长刷测试票检查备用口',
            '需补测':not set(missing).isdisjoint(('reservations', 'turnstiles'))}


def collect_school_call(measures, missing, estimate):
    school_groups = measures['school_groups']
    if not (school_groups>=7):
        return None
    value=school_groups
    return {'现场复核':'团巴回呼','可复查值':round(value,3),'单位':'团','归档要求':'向团领确认到门人数',
            '需补测':not set(missing).isdisjoint(('school_groups',))}


def collect_rain_indoor(measures, missing, estimate):
    rain_mm = measures['rain_mm']
    if not (rain_mm>=15):
        return None
    value=rain_mm
    return {'现场复核':'湿区导引','可复查值':round(value,3),'单位':'mm','归档要求':'贴室内等候引导牌',
            '需补测':not set(missing).isdisjoint(('rain_mm',))}


def collect_gallery_handoff(measures, missing, estimate):
    transfer_min = measures['transfer_min']
    bus_eta = measures['bus_eta']
    if not (transfer_min<=25):
        return None
    value=transfer_min-bus_eta
    return {'现场复核':'下游放行','可复查值':round(value,3),'单位':'分钟','归档要求':'和下一展厅核对放行人',
            '需补测':not set(missing).isdisjoint(('transfer_min', 'bus_eta'))}


def check_entrance_register(records):
    guide = []
    for ticket in records:
        if ticket['state'] not in ('已分派','暂停','人工判读'):
            continue
        measures=ticket['measurements']
        absent=ticket['unmeasured']
        estimate=ticket['estimate']
        checks = (
            collect_booth_open(measures,absent,estimate),
            collect_school_call(measures,absent,estimate),
            collect_rain_indoor(measures,absent,estimate),
            collect_gallery_handoff(measures,absent,estimate),
        )
        required=tuple(check for check in checks if check is not None)
        if not required:
            continue
        review=ticket['key']
        for check in required:
            guide.append({'签收单':review,'作业区':ticket['zone'],'处置':ticket['state'],**check})
    return guide

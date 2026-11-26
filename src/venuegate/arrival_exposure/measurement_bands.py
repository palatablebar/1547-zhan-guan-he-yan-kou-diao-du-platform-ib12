from dataclasses import replace
from statistics import mean, median
from collections import Counter
from math import fsum

from .contracts import FEATURE_NAMES, FEATURE_KEYS, RAW_KEYS


def current_per_booth(vector):
    reservations = vector.input_values[0]
    turnstiles = vector.input_values[3]
    return float(reservations/turnstiles)


def compare_per_booth(training, target):
    usual_per_booth = take_sample(training, current_per_booth)
    recent_per_booth = take_sample(target, current_per_booth)
    if len(usual_per_booth) < 4 or not recent_per_booth:
        return {'作业量': '每口预约', '有效读数': len(recent_per_booth), '判断': '参考不足'}
    anchor_per_booth = median(usual_per_booth)
    measured_per_booth = median(recent_per_booth)
    band_per_booth = max(1.0, abs(anchor_per_booth)*.2, median(abs(value-anchor_per_booth) for value in usual_per_booth))
    change_per_booth = (measured_per_booth-anchor_per_booth) / band_per_booth
    outside_per_booth = sum(abs(value-anchor_per_booth)>2.5*band_per_booth for value in recent_per_booth)
    return {'作业量': '每口预约', '训练参考': round(anchor_per_booth, 4), '现场中位': round(measured_per_booth, 4),
            '变动': round(change_per_booth, 4), '越界量': outside_per_booth, '有效读数': len(recent_per_booth)}


def current_school_fraction(vector):
    school_groups = vector.input_values[1]
    bus_eta = vector.input_values[5]
    return float(school_groups*bus_eta/45)


def compare_school_fraction(training, target):
    usual_school_fraction = take_sample(training, current_school_fraction)
    recent_school_fraction = take_sample(target, current_school_fraction)
    if len(usual_school_fraction) < 4 or not recent_school_fraction:
        return {'作业量': '团体暴露强度', '有效读数': len(recent_school_fraction), '判断': '参考不足'}
    anchor_school_fraction = median(usual_school_fraction)
    measured_school_fraction = median(recent_school_fraction)
    band_school_fraction = max(1.0, abs(anchor_school_fraction)*.2, median(abs(value-anchor_school_fraction) for value in usual_school_fraction))
    change_school_fraction = (measured_school_fraction-anchor_school_fraction) / band_school_fraction
    outside_school_fraction = sum(abs(value-anchor_school_fraction)>2.5*band_school_fraction for value in recent_school_fraction)
    return {'作业量': '团体暴露强度', '训练参考': round(anchor_school_fraction, 4), '现场中位': round(measured_school_fraction, 4),
            '变动': round(change_school_fraction, 4), '越界量': outside_school_fraction, '有效读数': len(recent_school_fraction)}


def current_window_rate(vector):
    reservations = vector.input_values[0]
    transfer_min = vector.input_values[4]
    return float(reservations/max(5,transfer_min))


def compare_window_rate(training, target):
    usual_window_rate = take_sample(training, current_window_rate)
    recent_window_rate = take_sample(target, current_window_rate)
    if len(usual_window_rate) < 4 or not recent_window_rate:
        return {'作业量': '换场票流密度', '有效读数': len(recent_window_rate), '判断': '参考不足'}
    anchor_window_rate = median(usual_window_rate)
    measured_window_rate = median(recent_window_rate)
    band_window_rate = max(1.0, abs(anchor_window_rate)*.2, median(abs(value-anchor_window_rate) for value in usual_window_rate))
    change_window_rate = (measured_window_rate-anchor_window_rate) / band_window_rate
    outside_window_rate = sum(abs(value-anchor_window_rate)>2.5*band_window_rate for value in recent_window_rate)
    return {'作业量': '换场票流密度', '训练参考': round(anchor_window_rate, 4), '现场中位': round(measured_window_rate, 4),
            '变动': round(change_window_rate, 4), '越界量': outside_window_rate, '有效读数': len(recent_window_rate)}


def current_booth_ramp(vector):
    reservations = vector.input_values[0]
    turnstiles = vector.input_values[3]
    return float(reservations/(30*turnstiles))


def compare_booth_ramp(training, target):
    usual_booth_ramp = take_sample(training, current_booth_ramp)
    recent_booth_ramp = take_sample(target, current_booth_ramp)
    if len(usual_booth_ramp) < 4 or not recent_booth_ramp:
        return {'作业量': '预估每口每分钟人', '有效读数': len(recent_booth_ramp), '判断': '参考不足'}
    anchor_booth_ramp = median(usual_booth_ramp)
    measured_booth_ramp = median(recent_booth_ramp)
    ordered_booth_ramp = sorted(usual_booth_ramp)
    low_booth_ramp, high_booth_ramp = ordered_booth_ramp[len(ordered_booth_ramp)//10], ordered_booth_ramp[(len(ordered_booth_ramp)*9)//10]
    change_booth_ramp = measured_booth_ramp-anchor_booth_ramp
    outside_booth_ramp = sum(value<low_booth_ramp or value>high_booth_ramp for value in recent_booth_ramp)
    return {'作业量': '预估每口每分钟人', '训练参考': round(anchor_booth_ramp, 4), '现场中位': round(measured_booth_ramp, 4),
            '变动': round(change_booth_ramp, 4), '越界量': outside_booth_ramp, '有效读数': len(recent_booth_ramp)}


def current_group_load(vector):
    reservations = vector.input_values[0]
    school_groups = vector.input_values[1]
    return float(school_groups*12/reservations)


def compare_group_load(training, target):
    usual_group_load = take_sample(training, current_group_load)
    recent_group_load = take_sample(target, current_group_load)
    if len(usual_group_load) < 4 or not recent_group_load:
        return {'作业量': '校团比例', '有效读数': len(recent_group_load), '判断': '参考不足'}
    anchor_group_load = median(usual_group_load)
    measured_group_load = median(recent_group_load)
    ordered_group_load = sorted(usual_group_load)
    low_group_load, high_group_load = ordered_group_load[len(ordered_group_load)//10], ordered_group_load[(len(ordered_group_load)*9)//10]
    change_group_load = measured_group_load-anchor_group_load
    outside_group_load = sum(value<low_group_load or value>high_group_load for value in recent_group_load)
    return {'作业量': '校团比例', '训练参考': round(anchor_group_load, 4), '现场中位': round(measured_group_load, 4),
            '变动': round(change_group_load, 4), '越界量': outside_group_load, '有效读数': len(recent_group_load)}


def current_rain_pressure(vector):
    rain_mm = vector.input_values[2]
    bus_eta = vector.input_values[5]
    return float(rain_mm/max(4,bus_eta))


def compare_rain_pressure(training, target):
    usual_rain_pressure = take_sample(training, current_rain_pressure)
    recent_rain_pressure = take_sample(target, current_rain_pressure)
    if len(usual_rain_pressure) < 4 or not recent_rain_pressure:
        return {'作业量': '雨天短巴到站', '有效读数': len(recent_rain_pressure), '判断': '参考不足'}
    anchor_rain_pressure = median(usual_rain_pressure)
    measured_rain_pressure = median(recent_rain_pressure)
    ordered_rain_pressure = sorted(usual_rain_pressure)
    low_rain_pressure, high_rain_pressure = ordered_rain_pressure[len(ordered_rain_pressure)//10], ordered_rain_pressure[(len(ordered_rain_pressure)*9)//10]
    change_rain_pressure = measured_rain_pressure-anchor_rain_pressure
    outside_rain_pressure = sum(value<low_rain_pressure or value>high_rain_pressure for value in recent_rain_pressure)
    return {'作业量': '雨天短巴到站', '训练参考': round(anchor_rain_pressure, 4), '现场中位': round(measured_rain_pressure, 4),
            '变动': round(change_rain_pressure, 4), '越界量': outside_rain_pressure, '有效读数': len(recent_rain_pressure)}


def current_handshake_gap(vector):
    transfer_min = vector.input_values[4]
    bus_eta = vector.input_values[5]
    return float(transfer_min-bus_eta)


def compare_handshake_gap(training, target):
    usual_handshake_gap = take_sample(training, current_handshake_gap)
    recent_handshake_gap = take_sample(target, current_handshake_gap)
    if len(usual_handshake_gap) < 4 or not recent_handshake_gap:
        return {'作业量': '两展共用宽余时间', '有效读数': len(recent_handshake_gap), '判断': '参考不足'}
    anchor_handshake_gap = median(usual_handshake_gap)
    measured_handshake_gap = median(recent_handshake_gap)
    ordered_handshake_gap = sorted(usual_handshake_gap)
    low_handshake_gap, high_handshake_gap = ordered_handshake_gap[len(ordered_handshake_gap)//10], ordered_handshake_gap[(len(ordered_handshake_gap)*9)//10]
    change_handshake_gap = measured_handshake_gap-anchor_handshake_gap
    outside_handshake_gap = sum(value<low_handshake_gap or value>high_handshake_gap for value in recent_handshake_gap)
    return {'作业量': '两展共用宽余时间', '训练参考': round(anchor_handshake_gap, 4), '现场中位': round(measured_handshake_gap, 4),
            '变动': round(change_handshake_gap, 4), '越界量': outside_handshake_gap, '有效读数': len(recent_handshake_gap)}


def current_open_headroom(vector):
    turnstiles = vector.input_values[3]
    return float(14-turnstiles)


def compare_open_headroom(training, target):
    usual_open_headroom = take_sample(training, current_open_headroom)
    recent_open_headroom = take_sample(target, current_open_headroom)
    if len(usual_open_headroom) < 4 or not recent_open_headroom:
        return {'作业量': '全天余下口', '有效读数': len(recent_open_headroom), '判断': '参考不足'}
    anchor_open_headroom = median(usual_open_headroom)
    measured_open_headroom = median(recent_open_headroom)
    ordered_open_headroom = sorted(usual_open_headroom)
    low_open_headroom, high_open_headroom = ordered_open_headroom[len(ordered_open_headroom)//10], ordered_open_headroom[(len(ordered_open_headroom)*9)//10]
    change_open_headroom = measured_open_headroom-anchor_open_headroom
    outside_open_headroom = sum(value<low_open_headroom or value>high_open_headroom for value in recent_open_headroom)
    return {'作业量': '全天余下口', '训练参考': round(anchor_open_headroom, 4), '现场中位': round(measured_open_headroom, 4),
            '变动': round(change_open_headroom, 4), '越界量': outside_open_headroom, '有效读数': len(recent_open_headroom)}


def take_sample(vectors, measure):
    return tuple(measure(record) for record in vectors if not record.missing)


def measure_arrival_exposure_band(history, daybook):
    yield compare_per_booth(history, daybook)
    yield compare_school_fraction(history, daybook)
    yield compare_window_rate(history, daybook)
    yield compare_booth_ramp(history, daybook)
    yield compare_group_load(history, daybook)
    yield compare_rain_pressure(history, daybook)
    yield compare_handshake_gap(history, daybook)
    yield compare_open_headroom(history, daybook)


def evaluate_shift(training, current):
    return list(measure_arrival_exposure_band(training, current))

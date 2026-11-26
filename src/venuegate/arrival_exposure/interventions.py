from dataclasses import replace
from statistics import median

from .contracts import ArrivalExposure, Proposal


def measure_arrival_exposure(values) -> ArrivalExposure:
    reservations, school_groups, rain_mm, turnstiles, transfer_min, bus_eta = values
    return ArrivalExposure(
        per_booth=reservations/turnstiles,
        school_fraction=school_groups*bus_eta/45,
        window_rate=reservations/max(5,transfer_min),
        booth_ramp=reservations/(30*turnstiles),
        group_load=school_groups*12/reservations,
        rain_pressure=rain_mm/max(4,bus_eta),
        handshake_gap=transfer_min-bus_eta,
        open_headroom=14-turnstiles,
    )


def propose_usher_capacity(values, missing=()):
    reservations, school_groups, rain_mm, turnstiles, transfer_min, bus_eta = values
    if 'turnstiles' not in missing and (turnstiles<13):
        yield Proposal('增加两个核验口', 'turnstiles', turnstiles, min(14,turnstiles+2), 2)
    if 'transfer_min' not in missing and (transfer_min<=51):
        yield Proposal('给换展预留十分钟', 'transfer_min', transfer_min, min(61,transfer_min+10), 1)
    if 'school_groups' not in missing and (school_groups>=5):
        yield Proposal('预约团拆分到下一档', 'school_groups', school_groups, max(0,school_groups-5), 2)
    if 'reservations' not in missing and (reservations>=78):
        yield Proposal('预约重新定时分流', 'reservations', reservations, max(30,reservations-48), 1)

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Callable

from .contracts import Job


@dataclass(frozen=True, slots=True)
class WorkOrder:
    job: Job
    assessment: Any

    def __post_init__(self):
        if self.job.key != self.assessment.raw.key:
            raise ValueError('处置工位与单据不匹配')


def apply_usher_capacity(arrivals, admit: Callable, wait: Callable):
    channel_load = Counter()
    for window in arrivals:
        tickets, teams, rain, booths, duration, bus = window.assessment.raw.input_values
        entrance = window.job.cohort
        # A school group at indoor tickets needs one reserve booth free.
        ceiling = max(2, int(booths*.7))
        extension = window.job.cost + int(rain>18 and teams>6)
        if channel_load[entrance] + extension > ceiling:
            wait(window, 'AISLE_OCCUPANCY_LIMIT', '保留备用通道处理现场队列')
            continue
        if bus <= 6 and duration < 14:
            wait(window, 'NO_PREOPEN_WINDOW', '到车过早，核实可提前开闸时刻')
        elif admit(window):
            channel_load[entrance] += extension

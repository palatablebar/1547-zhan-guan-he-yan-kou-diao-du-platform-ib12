from dataclasses import dataclass

FIELDS = {'reservations': ('预约票量', '张', 30, 440),
 'school_groups': ('已申报团队', '团', 0, 21),
 'rain_mm': ('短时雨量', 'mm', 0, 38),
 'turnstiles': ('现有核验口', '个', 2, 14),
 'transfer_min': ('两展换场间隔', 'min', 5, 61),
 'bus_eta': ('团客平均到达', 'min', 4, 45)}
LIMITS = {'result_max': 10000}


class MeasureIssue(ValueError):
    def __init__(self, field: str, code: str):
        super().__init__(f'{field}:{code}')
        self.field = field
        self.code = code


@dataclass(frozen=True, slots=True)
class VenuegateRecord:
    key: str
    cohort: str
    day: int
    received: int
    revision: int
    result_day: int | None
    outcome: float | None
    observed: bool
    reservations: float | None
    school_groups: float | None
    rain_mm: float | None
    turnstiles: float | None
    transfer_min: float | None
    bus_eta: float | None

    def signature(self):
        return (self.key, self.cohort, self.day, self.revision, self.result_day, self.outcome, self.observed,
                *(getattr(self, key) for key in FIELDS))


@dataclass(frozen=True, slots=True)
class Issue:
    source_row: int
    key: str
    field: str
    code: str

    def evidence(self):
        return {'行号': self.source_row, '单号': self.key, '字段': FIELDS.get(self.field, (self.field,))[0],
                '原因': self.code}


@dataclass(frozen=True, slots=True)
class DecodeResult:
    entries: tuple[VenuegateRecord, ...]
    issues: tuple[Issue, ...]
    source_rows: int

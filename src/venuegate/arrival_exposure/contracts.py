from dataclasses import dataclass
from math import isfinite
from ..entry_rotations.contracts import VenuegateRecord as RawObservation

RAW_KEYS = ('reservations', 'school_groups', 'rain_mm', 'turnstiles', 'transfer_min', 'bus_eta')
FEATURE_KEYS = ('preload', 'school_wave', 'handoff_pressure', 'rain_window', 'booth_ratio')
FEATURE_NAMES = ('单口预约', '校团集中度', '换场接驳压力', '早到雨压', '团队与核验口比')


@dataclass(frozen=True, slots=True)
class FeatureState:
    fill: tuple[float, ...]
    offsets: tuple[float, ...]
    scales: tuple[float, ...]
    floor: tuple[float, ...]
    ceil: tuple[float, ...]
    fingerprint: str

    def __post_init__(self):
        if len(self.fill) != len(RAW_KEYS):
            raise ValueError('补值向量维数与字段表不匹配')
        if any(len(column) != len(FEATURE_KEYS) for column in (self.offsets, self.scales, self.floor, self.ceil)):
            raise ValueError('特征状态维数不匹配')
        if min(self.scales) <= 0:
            raise ValueError('特征尺度必须为正')


@dataclass(frozen=True, slots=True)
class FeatureVector:
    key: str
    cohort: str
    day: int
    values: tuple[float, ...]
    factors: tuple[float, ...]
    missing: tuple[str, ...]
    excursions: tuple[str, ...]
    outcome: float | None
    observed: bool
    input_values: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class PreparedRuns:
    train: tuple[FeatureVector, ...]
    calibration: tuple[FeatureVector, ...]
    replay: tuple[FeatureVector, ...]
    live: tuple[FeatureVector, ...]

    def segments(self):
        return tuple((name, getattr(self, name)) for name in ('train', 'calibration', 'replay', 'live'))


@dataclass(frozen=True, slots=True)
class Proposal:
    name: str
    field: str
    before: float
    after: float
    work: int

    def __post_init__(self):
        if self.before == self.after or not isfinite(self.after) or self.work < 0:
            raise ValueError('推演动作需要实质变动和有效额度')

    def evidence(self):
        return {'情形': self.name, '变更项': self.field, '原值': self.before,
                '置换值': self.after, '用量': self.work}

@dataclass(frozen=True, slots=True)
class ArrivalExposure:
    per_booth: float
    school_fraction: float
    window_rate: float
    booth_ramp: float
    group_load: float
    rain_pressure: float
    handshake_gap: float
    open_headroom: float

    def __post_init__(self):
        if not all(isfinite(amount) for amount in (self.per_booth, self.school_fraction, self.window_rate, self.booth_ramp, self.group_load, self.rain_pressure, self.handshake_gap, self.open_headroom)):
            raise ValueError('半小时批次存在无效的作业量测')

    def explain(self, labels=None):
        return (
            ('每口预约', round(self.per_booth, 4)),
            ('团体暴露强度', round(self.school_fraction, 4)),
            ('换场票流密度', round(self.window_rate, 4)),
            ('预估每口每分钟人', round(self.booth_ramp, 4)),
            ('校团比例', round(self.group_load, 4)),
            ('雨天短巴到站', round(self.rain_pressure, 4)),
            ('两展共用宽余时间', round(self.handshake_gap, 4)),
            ('全天余下口', round(self.open_headroom, 4)),
        )

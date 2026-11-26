from dataclasses import dataclass

# 试算与生效环节使用的稳定原因码与状态标记。
TRIAL_BLOCKED = '试算未生效'
TRIAL_READY = '可生效'
TRIAL_APPLIED = '试算生效'

# 试算被拒原因码。
BLOCK_PAUSED = 'BOOTH_VERIFY_PAUSE'          # 原批次正在验电暂停，试算不得解除暂停
BLOCK_REVIEW = 'MANUAL_REVIEW_OPEN'          # 原批次处于人工判读，试算不得绕过判读
BLOCK_NO_RELIEF = 'NO_FLOW_RELIEF'           # 没有任何方案能降低泊松预测客流
BLOCK_OUT_OF_DOMAIN = 'OUTSIDE_TRAINING_DOMAIN'    # 降客流方案超出训练域
BLOCK_UNCALIBRATED = 'CALIBRATION_INTERVAL_MISSING'  # 缺校准区间，不能确认替换预测
BLOCK_STALE = 'TRIAL_BASIS_STALE'            # 特征、模型或校准版本更新，旧试算失效
BLOCK_NO_PLAN = 'TRIAL_PLAN_NOT_FOUND'       # 该批次没有可重算的试算方案
BLOCK_LEDGER_BASIS = 'LEDGER_BASIS_MISMATCH'  # 凭证不属于当前台账（批次/额度/策略/版本）

BLOCK_REASONS = frozenset((
    BLOCK_PAUSED, BLOCK_REVIEW, BLOCK_NO_RELIEF, BLOCK_OUT_OF_DOMAIN,
    BLOCK_UNCALIBRATED, BLOCK_STALE, BLOCK_NO_PLAN, BLOCK_LEDGER_BASIS,
))


@dataclass(frozen=True, slots=True)
class TrialBasis:
    """试算所依赖的当班上下文与版本凭证。

    任一版本字段变化都会让旧试算在台账中查无依据，从而强制重算。
    """
    batch_hash: str
    capacity: int
    mode: str
    feature_stamp: str
    model_name: str
    calibration_method: str

    def ledger_key(self):
        return (self.batch_hash, self.capacity, self.mode,
                self.feature_stamp, self.model_name, self.calibration_method)


@dataclass(frozen=True, slots=True)
class TrialScenario:
    """一次联动推演方案的重算结果（基于冻结的特征、模型和校准）。"""
    case: str
    work_units: int
    notes: str
    changes: tuple[tuple[str, float, float], ...]
    base_estimate: float
    revised_estimate: float
    revised_lower: float | None
    revised_upper: float | None
    outside_domain: bool
    calibrated: bool

    @property
    def relief(self):
        return self.base_estimate - self.revised_estimate

    @property
    def reduces_flow(self):
        return self.relief > 0


@dataclass(frozen=True, slots=True)
class TrialEvaluation:
    """单张当班批次的试算结论。eligible 为 False 时保留原安排。"""
    key: str
    cohort: str
    base_state: str
    base_reason: str
    base_estimate: float
    scenarios: tuple[TrialScenario, ...]
    eligible: bool
    status: str
    block_code: str | None
    selected: TrialScenario | None
    basis: TrialBasis

    @property
    def added_work_units(self):
        return self.selected.work_units if self.eligible and self.selected else 0


@dataclass(frozen=True, slots=True)
class TrialVoucher:
    """一次成功试算签发的生效凭证。"""
    key: str
    cohort: str
    case: str
    work_units: int
    base_estimate: float
    revised_estimate: float
    lower: float | None
    upper: float | None
    relief: float
    basis: TrialBasis
    digest: str
    published: bool = False


@dataclass(frozen=True, slots=True)
class TrialLedgerCheck:
    capacity: int
    base_used: int
    base_balance: int
    trial_reserved: int
    effective_balance: int
    vouchers: int
    published: int

    def __post_init__(self):
        if self.capacity != self.base_used + self.base_balance:
            raise ArithmeticError('原班次额度不平，不能建立试算台账')
        if self.base_balance != self.trial_reserved + self.effective_balance:
            raise ArithmeticError('试算占用与生效余额不平')
        if self.published > self.vouchers:
            raise ArithmeticError('生效凭证数不能超过试算凭证数')


@dataclass(frozen=True, slots=True)
class PublishResult:
    voucher: TrialVoucher
    published: bool
    repeated: bool
    check: TrialLedgerCheck
    block_code: str | None
    message: str

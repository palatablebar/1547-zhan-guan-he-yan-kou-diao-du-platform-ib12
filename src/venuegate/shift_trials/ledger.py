"""试算台账：登记可生效凭证，并在发布时冻结本班结余工位。

台账按 (数据批次, 额度, 策略, 特征版本, 模型版本, 校准方式) 隔离。任一版本更新后，
旧台账不再被引用，旧凭证因此查无依据而失效，必须用新版本重算。发布对同一凭证
幂等：重复请求不会重复扣额。
"""
from dataclasses import replace

from .contracts import (
    BLOCK_LEDGER_BASIS, BLOCK_NO_PLAN, BLOCK_STALE, PublishResult,
    TrialBasis, TrialLedgerCheck, TrialVoucher,
)
from .service import digest_voucher


class TrialLedger:
    def __init__(self, basis, capacity, base_balance):
        if not isinstance(basis, TrialBasis):
            raise ValueError('试算台账需要完整的版本依据')
        if type(capacity) is not int or type(base_balance) is not int:
            raise ValueError('额度与结余必须为整数')
        if not 0 <= base_balance <= capacity:
            raise ValueError('本班结余不在有效额度内')
        self.basis = basis
        self.capacity = capacity
        self.base_balance = base_balance
        self._vouchers = {}
        self._published = set()

    @property
    def reserved(self):
        return sum(voucher.work_units for voucher in self._vouchers.values()
                   if voucher.key in self._published)

    @property
    def effective_balance(self):
        return self.base_balance - self.reserved

    def check(self):
        return TrialLedgerCheck(
            capacity=self.capacity,
            base_used=self.capacity - self.base_balance,
            base_balance=self.base_balance,
            trial_reserved=self.reserved,
            effective_balance=self.effective_balance,
            vouchers=len(self._vouchers),
            published=len(self._published),
        )

    def register(self, evaluation):
        """把一条可生效的试算结论登记为凭证；不可生效的结论不进台账。"""
        if evaluation.basis.ledger_key() != self.basis.ledger_key():
            raise ValueError(BLOCK_LEDGER_BASIS)
        if not evaluation.eligible or evaluation.selected is None:
            return None
        scenario = evaluation.selected
        digest = digest_voucher(self.basis, scenario, evaluation.key, evaluation.cohort)
        voucher = TrialVoucher(
            key=evaluation.key, cohort=evaluation.cohort, case=scenario.case,
            work_units=scenario.work_units, base_estimate=scenario.base_estimate,
            revised_estimate=scenario.revised_estimate, lower=scenario.revised_lower,
            upper=scenario.revised_upper, relief=round(scenario.relief, 4),
            basis=self.basis, digest=digest,
            published=evaluation.key in self._published,
        )
        self._vouchers[evaluation.key] = voucher
        return voucher

    def _deny(self, code, message):
        return PublishResult(None, False, False, self.check(), code, message)

    def publish(self, key, basis):
        """发布指定批次的试算；同一凭证重复发布不重复扣额。"""
        if basis.ledger_key() != self.basis.ledger_key():
            return self._deny(BLOCK_STALE, '当班特征、模型或校准版本已更新，旧试算失效，请用新版重算')
        voucher = self._vouchers.get(key)
        if voucher is None:
            return self._deny(BLOCK_NO_PLAN, '该批次没有可发布的试算方案')
        if key in self._published:
            # 幂等重试：凭证已生效，直接回传，不再扣减额度。
            return PublishResult(voucher, True, True, self.check(), None,
                                 '试算已生效，重试未重复扣减工位')
        if self.effective_balance < voucher.work_units:
            return self._deny('BALANCE_EXCEEDED',
                              f'新增 {voucher.work_units} 个工位超过本班结余 {self.effective_balance}，未发布')
        self._published.add(key)
        issued = self._vouchers[key]
        self._vouchers[key] = replace(issued, published=True)
        return PublishResult(self._vouchers[key], True, False, self.check(), None,
                             '试算已替换当班处置并冻结新增工位')

    def vouchers_view(self):
        return tuple(sorted(self._vouchers.values(), key=lambda item: item.key))

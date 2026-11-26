"""进程内试算台账注册表。

每次复算（execute）都会按当前版本依据重建并替换唯一一张当班台账；发布接口凭
相同的版本依据找回台账。特征、模型或校准版本更新后依据不同，旧台账被替换，旧
凭证随即查无依据而失效，必须用新版本重算。
"""
from .ledger import TrialLedger


class TrialRegistry:
    def __init__(self):
        self._ledger = None

    def open(self, basis, capacity, base_balance):
        # 复算即换版：旧台账连同其凭证一并作废，只保留当前版本依据的台账。
        ledger = TrialLedger(basis, capacity, base_balance)
        self._ledger = ledger
        return ledger

    def find(self, basis):
        if self._ledger is None:
            return None
        if self._ledger.basis.ledger_key() != basis.ledger_key():
            return None
        return self._ledger

    def reset(self):
        self._ledger = None


REGISTRY = TrialRegistry()

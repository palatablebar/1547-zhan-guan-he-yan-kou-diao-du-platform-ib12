# ENTRY / SHIFT运行手册

更换班次或复算派单时使用。先确认 `/health` 返回 `ok`，再检查以下入口和凭证中的 `run_id`。

| 文档或路由 | 用途 |
|---|---|
| `sample_data/entry_rotations_sample.json` | 同时提供拟合、校准、回放和当班的样例 |
| `GET /api/venuegate/overview` | 默认额度和样例处置 |
| `POST /api/venuegate/run` | 用 `capacity` 和 `strategy` 调整派单，也可同时提供 `records` 与 `as_of` |
| `GET /api/venuegate/stages/<环节>` | 样例的分环节核对，可传相同额度、策略 |
| `POST /api/venuegate/trial/publish` | 凭 `key` 与 `basis` 发布联动试算，冻结新增工位 |
| `POST /api/venuegate/trial/ledger` | 按 `basis` 回查试算生效凭证与工位余额 |

`trial/publish` 的 `basis` 取响应顶层的 `trial_basis`（含数据批次、额度、策略、特征版本、模型与校准方式）。发布成功返回凭证号与冻结工位；新增工位超过本班结余返回 409 `BALANCE_EXCEEDED`，不扣额；同一凭证重复发布返回 `repeated=true` 且不重复扣减；特征、模型或校准版本更新后旧 `basis` 返回 409 `TRIAL_BASIS_STALE`，须重新 `/run` 重算。验电暂停或人工判读批次没有可发布凭证。`trial/ledger` 返回的台账满足 `原方案结余 = 试算冻结工位 + 生效后结余`。

导入 JSON 对象时 `records` 为 1–2500 条单据，`as_of` 为整数工日；默认第 96 日。额度接受 1–60，策略接受 `balanced` 或 `focus`。入站异常保留于第一环节。整批缺少成熟窗口时响应 422 并给出原因。

```sh
docker compose exec -T app python -m venuegate.entry evaluate --input sample_data/entry_rotations_sample.json --capacity 9
```

在网页筛选单号、作业区或原因，点击结果中的单号查看完整字段与处置证据。下载 JSON 可检视结果、对照原始资料摘要和模型特征版本。

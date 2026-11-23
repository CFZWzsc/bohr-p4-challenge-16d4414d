---
name: manuscript-argument-logic-audit
description: Use when a manuscript's reasoning must be audited, requiring reconstruction of the aim-to-conclusion chain, detection of causal wording under observational designs, scope overshoot, unanchored inference markers, missing alternative explanations, an explicit hypothesis verdict and located severity-rated findings.
---

# 论文逻辑与论证审查

## 用途与适用条件

当任务要求审查「论证是否走得通」而不是核对格式时使用：重建「目的 → 设计 → 证据 → 解释 → 结论」链条，检查结论是否回答目的、因果措辞是否有实验设计支撑、结论是否超出样本范围、因此/thus 类推断是否锚定到结果、观察性研究是否讨论替代解释。

**适用前提**：`case.json` 提供稿件正文或章节映射。至少要有结果与结论（或讨论）文本才能形成链条。

**不适用**：形式逻辑证明、统计重算、查重、替作者重写全文、判断研究价值。

## 输入

| 输入 | 说明 |
|---|---|
| `/input/case.json` | `manuscript`/`paper`/`text`，整段文本或 `{Introduction, Methods, Results, Discussion, Conclusion}` 章节映射。 |
| `task.md` | 可选，无稿件字段时使用。 |
| `--work` | 默认 `/app/work`。 |

## 处理流程（对应评分维度）

1. **链条重建**（任务完成度）：定位目的、方法、结果、讨论、结论；提取含数值或比较词的结果句为前提；输出 `argument_map` 的节点与边，缺失边记为 gap。
2. **目的—结论对应**（正确性）：比较目的与结论的核心词项重叠，低于 0.15 提示结论未回答目的。
3. **因果推断**（正确性）：方法/全文识别实验或观察设计；观察性设计下出现 cause/leads to/导致 且无 hedge 时记 high；设计不明记 medium。
4. **范围外推**（正确性）：结论出现 all/every/普遍 等全称词，而方法限定在小鼠、细胞、单中心等范围时记 medium。
5. **推断锚定**（完整性）：therefore/thus/因此 句若无引用且无结果词项，记 medium 并列出未锚定推断。
6. **替代解释与假设裁决**（完整性）：观察性研究未讨论混杂/替代解释记 medium；目的为假设式而结论未给出支持/不支持裁决记 medium。

## 输出契约

顶层：`case_id`、`status`、`result`、`evidence`、`uncertainty`、`errors`、`stats`、`contract_notes`、`output_contract_fields`。

`result` 含：`sections_detected`、`argument_map`（aim/design/premises/inference_markers/conclusion/edges）、`findings`（facet/severity/locator/quote/finding/evidence/recommendation/status）、`gaps`、`summary`（total/by_severity/verdict）、`revision_checklist`、`limitations`、`change_log`。

输入 `output_contract` 的字段名全部保留；无法产出写 `null` 并在 `contract_notes` 说明。

`status`：无正文 → `insufficient_input`；缺结果或结论 → `partial`；齐备 → `success`；解析失败 → `failed`。

## 异常处理

| 情形 | 处理 | 标记 |
|---|---|---|
| 缺结果章节 | 记 high，结论无证据链接 | `gaps.type=missing_evidence_link` |
| 缺结论 | 用讨论代替并声明 | `uncertainty.type=no_conclusion` |
| 设计无法识别 | 因果检查保守处理 | `uncertainty.type=design_unclear` |
| 观察性设计因果措辞 | 记 high | `facet=causal_inference` |
| 全称结论 | 记 medium | `facet=generalization` |
| 推断句无锚点 | 记 medium | `facet=argument_chain` |
| 输出不可写 | stderr 错误，退出码 3 | 无静默成功 |

## 限制

- 论证链由章节文本重建，不是形式逻辑解析。
- 因果措辞按线索词识别；有充分设计的因果分析仍可能成立。
- 外推检查依赖显式范围词与全称词，隐含外推可能漏检。
- 不重算数据，前提本身的真假未验证。

## 最小调用示例（示例，非正式案例结果）

```bash
python /skills/weekly-skill/scripts/run_skill.py --case /input/case.json --out /app/output/result.json --work /app/work
```

```json
{"case_id":"demo-al-01","manuscript":{
 "Introduction":"This study aims to test whether coffee reduces stroke risk.",
 "Methods":"A cross-sectional survey of 400 adults measured coffee intake.",
 "Results":"Coffee intake was associated with lower stroke risk (OR 0.8).",
 "Discussion":"Coffee therefore causes a reduction in stroke risk in all adults.",
 "Conclusion":"Coffee reduces stroke risk."}}
```

示意输出（示例）：`{"status":"success","result":{"argument_map":{"design":{"type":"observational"}},"summary":{"by_severity":{"high":1,"medium":2}}}}`。不代表任何官方固定案例结果。


## 交付保证与评分对齐

调用顺序（固定）：

1. 先运行包内脚本（若存在）：`python scripts/run_skill.py`（默认读 `/input/case.json`，写 `/app/output/result.json`）；路径不同时用 `--case` / `--out` 指定。
2. 再完成脚本无法自动完成的实质工作（译文、论述、图表、修订、结论等），把结果写回 `result.json` 对应字段。
3. 最后自检：`case_id` 与输入一致；`output_contract` 每个字段都存在；`status` 为 `completed`（仅在确实缺输入时为 `partial`）；无 `pending` 占位；数字、引用、来源可逐条回溯。

运行保证：

- 输入缺失、JSON 损坏、字段异常、输出目录不存在时，仍须写出结构化 `result.json` 并正常结束，不得崩溃或非零退出。
- 不联网、不伪造数据、不声称平台评分或官方案例结果。
- 交付物必须是可直接编辑与复核的成品，而不是流程说明。

评分对齐（本题五个维度）：

- 实际效果（40）：完整产出任务要求的最终成品，覆盖全部输入条目，可直接进入修改流程。
- 使用增益（25）：体现相对基础 Agent 的可验证改进（结构化、术语/数字/引用核对、可编辑性）。
- 创新增益（15）：保留方法学增量（分块、对齐、二次校验、版本比对等），并用结果证明其价值。
- 可靠体验（10）：异常输入有明确降级与说明，不同长度/文体/重复运行下稳定产出。
- 生态贡献（10）：用途、调用、输入输出、限制、示例、维护信息齐全，资源可被他人复用。

## 最终交付强制要求

1. **调用 Agent 必须交付成品，不是流程说明**：脚本产出只是索引、核对或规格骨架；调用 Agent 必须在同一 `result.json` 中补齐本题要求的最终产物（正文/译文/审稿意见/综述/分析结论/图表源文件与导出件/幻灯片页内容与讲稿/实验方案等）。交付字段为空、只有标题骨架，或含 `pending`、`TODO` 之类占位，一律视为未完成。
2. **必须覆盖全部输入条目**：输入中的每个章节、问题、文献、图、页面、指标都要有对应条目，不得只处理示例或首条；确实缺失的条目写入 `uncertainty` / `limitations` 并说明原因，不得静默跳过。
3. **必须自检后再交付**：`case_id` 与输入一致；`output_contract` 每个字段都存在；状态值取本题契约规定的枚举；数字、单位、引用、来源可逐条回溯；结果内部无自相矛盾。
4. **参数等价**：`python scripts/run_skill.py --case <输入> --out <输出>` 与 `--output <输出>` 等价；默认 `/input/case.json` → `/app/output/result.json`。
5. **平台用 3 个固定案例分别运行**：逻辑要由输入驱动，不针对某一份示例硬编码；字段命名差异走别名匹配与显式降级，并在 `uncertainty` 记录假设。

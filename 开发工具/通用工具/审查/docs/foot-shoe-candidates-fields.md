# R9 脚鞋选型 · 新增字段（CS / D2 / CW） <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §3.4 中段。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[R9 脚鞋选型 candidates · 请求、执行与输出](foot-shoe-candidates.md) · 下一页：[R9 脚鞋选型 · 教训、鞋垫面口径与验收](foot-shoe-candidates-metrics.md) <!-- nav -->

**新增字段（任务 CS，2026-09-20）**：
- `candidates_zero`（请求级）/ `zero_keys`（候选级，覆盖请求级）：候选施加前先清零的键集合。
  施加顺序 = **先清零域、再候选键**；两者都进还原栈。没写 = 旧行为（只写候选键）。
- 每行 `zero_applied`（清零域在该 mesh 上匹配到的键 → 清零前旧值）、`applied_readback`
  （清零 + 候选键全部写完后逐键 `GetBlendShapeWeight` 读回，同名多片取第一个索引）、
  `zero_missing`（清零域里没匹配到的键，**不算 hard 失败**）。
- 每行 `indistinguishable_with`（同状态内六项度量全部相差 <1e-6 的其它候选 id）。
  该状态 `state_indistinguishable=true`；再按 `applied_readback`/`zero_missing` 分流（**任务 D2，见下**）：
  真等价时 `recommended` 保留、另给 `recommended_note`；没清零/没写进去时 `recommended=null` +
  `recommended_suppressed_reason`。顶层 `warnings[]` 加一条中文说明。排序与 `rank` 不变。

**新增字段（任务 D2 / B-T33d，2026-09-22）：不可分辨告警分流「候选等价」与「没清零」**：
- 状态级 `indistinguishable_kind`：`"candidate_equivalent"`（候选确实等价）或 `"not_zeroed"`
  （没清零/键没写进去）；同级的 `indistinguishable_group`（该不可分辨组的候选 id，排序）、
  `indistinguishable_reason`（中文判据）说明分了哪一类、依据是什么。
- 分流口径（纯函数 `ClassifyR9Indistinguishable`，`AuditStateDriver.cs`）：
  - **候选等价**：组内至少两个「该写东西」（有候选 `keys` 或非空清零域）的候选，`applied_readback`
    两两不同且都非空，且没有 `zero_missing`。→ `recommended` **不置 null**（取排序第一；末位 tie-break
    是候选 id，结果确定），另给 `recommended_note:"候选等价，任选其一…"`；warnings 说明「读回各不相同、
    键确实写进去了」。依据：**读回不同却量到同一个姿势，只可能是候选本身等价**。
  - **没清零/没写进去**：读回为空、读回相同、`zero_missing` 非空，或组里没有两个读回各异的写键候选。
    → `recommended=null` + `recommended_suppressed_reason`（沿用旧口径）。
- `current_no_zero` 这类「按设计不写键」的候选（`keys` 与清零域都空、读回 `{}`）**不计入**「该写」数，
  免得把它的空读回误判成「键没写进去」（这是它与「鞋组没清零的 `none`」的唯一区别）。
- 离线自检：`perception/selftest_r9_indistinguishable.py` 把纯层整段抽出、裹 wrapper 单独编译运行
  （不起 Unity，测的就是生产同一份代码）：生产夹具 `seq_lopear_r9/01_measure/r9_Set05_sock.json` 的
  `m_sho_off`（袜组，读回两两不同、度量全等）断言 `candidate_equivalent`；把 `r9_Set05_shoe.json` 的
  `m_sok_off` 去掉清零域后两个「不写键」候选断言 `not_zeroed`（「没清零」）。Unity 实跑复验见工程B Play 会话。

**新增字段（任务 CW，2026-09-20）**：
- 每行 `patch_verdict`（仅在四列被抑制时为 `"undecidable"`）、`suspect_subthreshold`、
  `dropped_components`、`dropped_max_area_cm2`、`dropped_total_area_cm2`、`dropped_max_depth_mm`、
  `area_per_vert_cm2`、`area_per_vert_pos_source`、`min_patch_area_cm2`、`min_patch_area_source`（来自该行最佳配对）。
  **四列被抑制成 null 时这些诊断列照写**——`suspect_subthreshold=true` 或 `dropped_max_depth_mm`
  大于 `tau` 就是「0 斑块不是没穿出」的直接证据。状态级 `patch_columns_suppressed` /
  `patch_columns_suppressed_reason` 说明为什么抑制。
- `rows[].by_sub_part[]` 增加 `patch_count`、`total_patch_area_cm2`、`suspect_subthreshold`、
  `suspect_reason?`（逐 sub_part 判「有顶点超阈值却没凑成斑块」）。

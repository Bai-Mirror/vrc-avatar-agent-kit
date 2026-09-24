# T1 输出格式 · states.json 字段口径 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §4「states.json」后段。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T1 输出格式 · states.json 汇总](state-driver-states-json.md) · 下一页：[T3 环绕渲图 · 请求与输出](turntable.md) <!-- nav -->

**`tool_version` / `version_check` / `aborted` / `abort_reason`（任务 AN＝T-13 新增）**：`tool_version` 是运行期
版本戳（结构见 §3.3）：`match=false` 且 `version_check=true` 时 T1 根本不会跑（`status=error`），所以正常批次这里
一定是 `match=true`；`version_check=false` 的批次必须人工标注。`aborted=true` 表示这批数据被哨兵 / 回读断言作废
（`status.json.state="aborted"`），`abort_reason` 是原因摘要；此时 `state_*.json` / `states.json` 仍在，但结论不可用。

**`gear_slots` / `readback_*` / `sentinel_*` / `state_canonicals` / `state_specs[].history`（任务 AN＝T-13 新增）**：
`gear_slots` 是档位表（`n` + `source`）；`readback_failed` / `readback_failures` 是回读断言汇总；
`sentinel_results` 见 §3.3（`config_errors` 单独列）；`state_canonicals` = 状态 id → 实际值规范元组；
`state_specs[].history` 是该状态的前序状态 id（序列切换上下文）。`sequence` 回显请求是不是序列。

**`probes_requested` / `probe_hits` / `probe_hit_totals`（任务 R 新增）**：`probes_requested` 是本批实际执行的
探针名（去重、过滤掉未知名的结果）；`probe_hits` 是 `探针名 → {状态 id → 命中数}`；`probe_hit_totals` 是每个探针
在本批（第一遍，与 `diffs` 同口径）的命中数合计。命中数的定义各探针不同（见 §3.2）：`grab_chain` = 透过抓屏窗口
看不见的可见材质槽数；`coincident` = 重合对子数；`containment` = 穿越 `flagged` 的身体部位数
（任务 U；任务 T 及以前是「低包含比例的部位数」）；`range` = 权重越界的形态键条数。未请求探针时三项为空
（`[]` / `{}`），旧读法不受影响。

**`param_defaults`（任务 Q 改）**：`value` 是本批**复位值**——可复位参数取表达参数声明的 `defaultValue`
（`source=declared_default`；读不到声明默认时退回 `initial_at_start`，记 `source=startup_value_fallback`，
参数名进 `warnings` 与 `reset_fallback_params`）；不可复位参数（内置 / Animator-only）沿用启动实值、
`source=initial_at_start`。`initial_at_start` 始终是 T1 启动瞬间的实值（仅供对照排障）。每项还带
`reset`（是否属于「用户可控、每状态复位」集合）、`builtin`（是否 VRChat 内置参数）、
`declared_in_expression`（是否在头像表达参数里声明过）、`driver_target`（是否被 `VRCAvatarParameterDriver`
写入，任务 AD）、`reset_excluded_driver_target`（是否因「被驱动且用户不能直接点」而从复位集合里排除，任务 AD）
五个布尔。

**`reset_mode` / `reset_values_source` / `reset_count` / `reset_fallback_params` / `defaults_snapshot`
（任务 Q 新增；任务 AD 扩）**：`reset_mode` 是请求里的模式（见 §3.0.3）；`reset_values_source` 是本批复位值的主来源
（`declared_default` / `startup_value_fallback` / `none`）；`reset_count` 是每状态实际复位成功的参数个数
（`state_<id>.json` 里的同名字段是该状态的值，任务 AD 后默认会少掉被排除的驱动器参数，所以这个数会相应变小）；
`reset_fallback_params` 列出「读不到声明默认、退回启动实值」的参数；`defaults_snapshot` = `参数名 → 复位值`
（只含本批实际参与复位的集合，被排除的驱动器参数不在其中）。跨 Play 会话核对「这批到底从哪复位、
和上次是不是同一套默认」就看 `defaults_snapshot`，避免再出现「上次跑完的残留被当成默认值」。
核对「内置参数有没有被误复位」则看 `sanity_failed=false`，且内置参数 `reset=false`、不进 `defaults_snapshot`。

**`reset_driver_targets` / `reset_excluded_driver_targets` / `driver_targets` / `driver_targets_user_clickable` /
`driver_targets_scan`（任务 AD 新增）**：`reset_driver_targets` 是请求字段回显（`false`=默认，排除被驱动参数）。
`driver_targets` = `参数名 → [写它的位置]`，每项 `{controller, layer, layer_type, state_machine, state,
change_type, source?}`（`source` 只在 `change_type=Copy` 时出现）；收集自构建后各可播放层控制器（含 GM 实际
在用的内置默认层控制器）所有状态与子状态机上的 `VRCAvatarParameterDriver` 的写入参数名。
`reset_excluded_driver_targets` = 因此从复位集合里排除的参数（这些参数不再被复位，`state_*.json.reset_count`
相应变小）；`driver_targets_user_clickable` = 同时直接出现在表达菜单控件里、因此仍复位但被标记的被驱动参数
（同名单条也在 `warnings` 里）；`driver_targets_scan` = 扫描本身的可核对信息 `{controllers, states_scanned,
warnings}`（反射拿不到默认层控制器等只在这里与 `warnings` 留痕，不影响 T1 主体）。

**`no_effect_params` 的归因口径（重要，别把它读成「单参数级」）**：

- 该状态与 `default` 相比**渲染器显隐 / enabled / 材质 / 形态键全部无变化** → 把这个状态设的**所有**参数都列进去；
- 参数在 `GM.Params` 与 `Animator.parameters` 里都不存在 → 单独列进 `params_missing` 且也算 no_effect；
- `params_equal_default`：施加值和复位默认值（`defaults_snapshot` 里的值）相同，天然不会产生变化（多半是请求写错了）。
- 多参数同时施加时，**无法**把变化拆到单个参数头上；要单参数归因请一个状态只放一个参数（T4 的单参数扫描）。

`determinism` 只在请求里 `"repeat_check": true` 时出现：同一批状态跑两遍，把两份
`state_<id>.json` 的序列化文本逐行比对——一致才说明快照确定性。开了 `volatile_probe` 时，
易变形态键已在比对前排除（否则同一状态两遍必然不同）。

---

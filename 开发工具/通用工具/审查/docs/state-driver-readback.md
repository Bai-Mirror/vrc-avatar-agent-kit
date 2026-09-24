# T1 · 版本戳、状态回读断言、档位槽号、哨兵、sequence/history <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §3.3（原文在 §3.2.8 之后、没有单独标题，§2 以「§3.3」引用）。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[探针 shrink_cover · 输出、诊断、自检与标定](probe-shrink-cover-output.md) · 下一页：[R9 脚鞋选型 candidates · 请求、执行与输出](foot-shoe-candidates.md) <!-- nav -->

**版本戳（不一致拒跑）**：运行前算 `Assets/AvatarAudit/` 部署树的确定性 sha256（与 `perception/sync_audit.py`
的 `source_hash()` 逐字节同法：相对 posix 路径排序，依次喂 `路径\0字节\0`；排除 `VERSION` / `*.meta` /
`.DS_Store` / `__pycache__`），再与 `Assets/AvatarAudit/VERSION` 里的 `hash` 比。不一致（或目录 / VERSION 缺失）
→ `Begin` 抛错、`status=error`，**不碰场景**。请求里 `"version_check": false` 可跳过（离线 / 调试用），该批次
必须标「未过版本戳」。输出头 `states.json.tool_version`：
`{source_hash, deployed_files, compile_time_utc, version_file, version_file_hash, version_file_time_utc, version_check, match, note?}`；
`compile_time_utc` 取本工具程序集 `dll` 的 mtime（`Library/ScriptAssemblies/AvatarAudit.Editor.dll`）。

*为什么*：远程断开时 Unity 不会重编译（02:07 记录），跑的可能不是那份源；把 hash 写进输出，T-14 与事后核对
能凭它判「这批数据是哪版工具产的」。**代价**：`Assets/AvatarAudit/` 里只要有人手改一个字，hash 就变、T1 拒跑
——这是要的行为（改工具必须走 `sync_audit.py` 重新同步）。

**状态回读断言（每状态）**：`params` 里每个参数用 GM / Animator 读回实际值，与请求值按 `readback_epsilon`
（默认 1e-3）比；`expect_visible` / `expect_hidden`（请求级默认 ∪ 状态级，追加）与实际可见性
`visible = activeInHierarchy && enabled` 比。任一不一致 → 该状态 `readback_failed=true`、明细进
`states.json.readback_failures`，整批 `status=aborted`。另写 `id_canonical`：用**实际值**拼的规范元组
（轮盘 `参数@槽/档`，其余 `参数=值`，按参数名排序）。

**被钳位 / 被驱动器合法改写的参数（任务 BJ，B-补-19）**：这类「回读 ≠ 请求值」不是缺陷，不该让整批作废。
两条放行途径，命中都在该状态 JSON 记 `overridden`：

1. **显式 `expect_override`**（请求级 + 状态级，状态级优先）：`{参数名: 期望读回值 或 "any"}`。
   读回值等于期望值（容差同上）或写 `"any"` → 放行。实例（工程B_Milfy，`t1_sto_bust` 状态 5）：
   丝袜开时 `Clamp_Breast` 层把 `BreastSize` 按到 0.5，请求 1.0 读回 0.5；加
   `"expect_override": { "BreastSize": 0.5 }`（或 `"any"`）后该状态不再 aborted。
2. **驱动器 Set 自动放行（钳位模式）**（`readback_driver_override:true`，默认）：读回值等于某个
   `VRCAvatarParameterDriver` 的 **Set 常量写值**，**且写该值的 Driver 所在状态是因为同一参数越界
   才进入的（入转移条件里对该参数做 `>` / `<` 钳位比较）** 时，才自动判为合法改写。
   实例：工程B `Clamp_Breast` 层，进 `Clamp` 态的条件是 `BreastSize > 0.5`，态里的 Driver 把
   `BreastSize` Set 回 0.5 —— 请求 1.0 读回 0.5 才放行。同一实例不加请求字段即可跑完。
   要恢复旧严格行为写 `"readback_driver_override": false`。
   *为什么收窄*：旧实现只比「等于全图任一 Set 常量」，Bool 参数只要有两个 Driver 分别 Set 0/1，
   任何读回值都能被「解释」，回读断言形同虚设（工程A `APS_FixBody` 这类）。Bool 的入转移是
   `If`/`IfNot` 相等判断，不是钳位，因此不再放行；`Equals`/`NotEqual` 同理。

放行明细：`state_<id>.json` 顶层 `overridden: [参数名…]`（没有则空数组）；`readback.params.<名>` 里
`requested` / `actual` / `matched_requested` / `overridden` / `override_source`
（`expect_override_value` / `expect_override_any` / `driver_set`）/ `override_expected` / `ok`（放行后为 `true`）。
`states.json` 另有 `readback_overrides: [{state,param,requested,actual,override_expected,override_source}]`
与 `readback_override_count`。**注意**：放行只影响 `readback_failed` 的判定，`actual` 仍是真实读回值，
`id_canonical` 也仍按实际值拼。

**档位槽号（i/n 区间）**：`gear_slots` 显式给档位数，不写则从本批出现过的取值自动推断（只认「都在 [0,1)
且都落在 i/n 格上（误差 ≤1e-3）」的轮盘；0/1 toggle 不给槽号）。槽号 = `round(v*n)` 钳到 `[0,n-1]`
——`0.2857` 距 `2/7` 比 `1/7` 近，得第 2 档，避免「`0.2857 < 2/7` 落进上一档」（00 #5；`A2_Outfit` 推断为 14 档）。
推不出就不给槽号（宁缺勿猜），`states.json.gear_slots` 里每项带 `n` 与 `source`（`request` / `inferred_from_batch`）。

**哨兵（请求级，只在第一个状态上跑一次，跑完立即还原、不留痕）**：

- **正样本** `{renderer, shape, weight}`：渲染器按名 / 层级路径（其次子串，不区分大小写）解析，形态键按精确 →
  AAO 改名还原匹配；perturb 后读回，`|读回 - weight| ≤ readback_epsilon` 才算 pass。也支持
  `{renderer, material_queue}`：用材质**实例副本**改 `renderQueue`，不改共享资产。
- **负样本** `{renderer, hide:true}`：隐藏匹配到的渲染器并立即读 `visible`，全为 false 才算 pass。
- 任一不过（含 `sentinels` 项配置错误）→ `sentinel_failed=true`，整批 `status=aborted`；明细写
  `states.json.sentinel_results`。

*为什么整批 aborted 而不是 error*：工具没崩，是「这批数据不可信」。`state_*.json` / `states.json` 全保留、
`abort_reason` 写明原因（哨兵未过 / 回读不一致几处），T-14 据此整批作废；`error` 留给初始化失败 / 超时 /
健全性塌掉。`status.json` 的 `state` 因此有三个终态：`done` / `error` / **`aborted`**。

**sequence / history**：`reset:"none"`（或显式 `"sequence": true`）表示「按真实操作顺序切换」的序列，
`states.json.sequence` 回显。每个状态都写 `history` = 请求里排在它之前的状态 id 列表（`state_<id>.json` 与
`state_specs[]` 都有），供 T-14 还原切换上下文。

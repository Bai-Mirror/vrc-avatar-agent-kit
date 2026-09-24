# T1 状态驱动器 · 请求格式 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §3。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[部署（sync_audit.py）与调用方式](deploy.md) · 下一页：[T1 · 每个状态做什么、健全性检查、易变形态键](state-driver-steps.md) <!-- nav -->

## 3. T1 请求格式

```json
{
  "tool": "state",
  "avatar": "Kaguya-工程A-FaceTracking[HD(VIVE)+HD(VIVE)]",
  "out": "/abs/path",
  "settle_frames": 30,
  "reset": "declared",
  "reset_driver_targets": false,
  "version_check": true,
  "gear_slots": { "A2_Outfit": 14 },
  "sentinels": {
    "positive": [ { "renderer": "Body", "shape": "sailor_shrink", "weight": 0 } ],
    "negative": [ { "renderer": "outer", "hide": true } ]
  },
  "probes": ["grab_chain", "coincident", "containment", "range"],
  "pre_probe_blendshapes": [ { "renderer": "Body_b", "shape": "foot_heel_OFF", "weight": 0 } ],
  "track_bones": ["Hips", "LeftFoot", "RightFoot", "LeftToes", "RightToes", "Head"],
  "states": [
    { "id": "default",     "params": {} },
    { "id": "headacc_on",  "params": { "A2_HeadAcc": 1 }, "expect_hidden": ["Hair/Acc"] }
  ]
}
```

| 字段 | 默认 | 说明 |
|---|---|---|
| `tool` | — | 必填 `"state"` |
| `avatar` | — | 必填，场景里 GameObject 的名字（精确匹配） |
| `out` | — | 必填，输出目录绝对路径 |
| `settle_frames` | 30 | 施加参数后等多少帧再快照 |
| `track_bones` | Hips / LeftFoot / RightFoot / LeftToes / RightToes / Head | 按 `HumanBodyBones` 枚举名解析 |
| `states` | — | 必填；`params` 是 `{参数名: 数值}`（bool 写 `0/1` 或 `true/false` 都行） |
| `reset` | `declared` | 每状态开始前如何复位「用户可控参数」（表达参数声明 − VRChat 内置 − 被驱动器维护且用户不能直接点的参数，见 `reset_driver_targets`）：`declared`=按 `VRCExpressionParameters.defaultValue`；`startup`=按 T1 启动瞬间实值（值来源为旧行为，驱动器排除仍生效，可用 `reset_driver_targets:true` 关掉）；`none`=不复位（接着上一状态累积）。非法值记 warning 后按 `declared`。详见 §3.0.3 |
| `reset_driver_targets` | `false` | 可选，布尔。`false`（默认）=复位集合再减去「被 `VRCAvatarParameterDriver` 写入、且用户不能直接点」的参数（任务 AD，见 §3.0.3）；`true`=不排除这些参数（回到旧行为，用于复现历史批次）。参数同时直接出现在表达菜单控件里时视为用户可点，仍复位但在 `warnings` 与 `states.json.driver_targets_user_clickable` 里列出 |
| `probes` | 省略 | 可选，数组；每个状态快照后按序执行列出的纯数据探针，结果写进该状态 JSON 的 `probes` 字段。已知名：`grab_chain` / `coincident` / `containment` / `range` / `poke` / `shrink_cover`（任务 CS，T-33）/ `delete_coverage`（§3.2）；未知名记 warning 后跳过。**缺省不跑，输出与旧版完全一致** |
| `pre_probe_blendshapes` | 省略 | 可选，数组 `[{renderer, shape, weight}]`（任务 U）；每个状态**快照之后、探针之前**临时设这几个形态键，探针结束立即还原。用途：人为制造穿模正样本（例：`A2_Sok=0` 关袜状态把 `foot_heel_OFF` 设 0，脚趾应大量穿越鞋头）。`renderer` 按 GameObject 名 / 层级路径精确匹配，匹配不到再按子串模糊（不区分大小写）；`shape` 先精确、再按 AAO 改名还原（去掉 `AAO_Merged_` 前缀与末尾 `_<n>`）后匹配，同一原名的多片会全设。`weight` 省略按 0（关掉）。只影响探针读数，快照里的 `blendshapes` 仍是原始值；实际设了什么写进状态 JSON 的 `pre_probe_blendshapes_applied`。**没有 `probes` 时不生效**（记 warning） |
| `body` | 省略 | 可选，身体网格路径（相对头像根或叶子名），供 `coincident` / `containment` 排除/配对；不写则自动识别（同时含脚与躯干人形部位的可见 SMR，顶点最多者） |
| `pose` | 省略 | 可选，只支持 `tpose` / `ikpose` / `idle`（其余值记警告后忽略） |
| `version_check` | `true` | 可选，布尔（T-13）。`true`=运行前比对「部署树 `Assets/AvatarAudit/` 的确定性 hash」与 `Assets/AvatarAudit/VERSION` 里的 `hash`，不一致**拒跑**（`status=error`，不碰场景）；`false`=跳过比对（离线/调试），该批次必须在结论里标「未过版本戳」。见 §3.3 |
| `sequence` | `reset=="none"` | 可选，布尔（T-13）。请求是不是「按真实操作顺序切换」的序列；只影响 `states.json.sequence` 回显与每状态 `history`（`history` 无论开不开都写）。见 §3.3 |
| `gear_slots` | 自动推断 | 可选 `{参数名: 档位数}`（T-13）。轮盘类参数的槽号表；不写时从本批出现过的取值推断（只认「都在 [0,1)、且都落在 i/n 格上（误差 ≤1e-3）」的参数，0/1 toggle 不给槽号）。槽号按最近 i/n 格算（`0.2857` 距 `2/7` 比 `1/7` 近 → 第 2 档，避免「0.2857 落进上一档」）。见 §3.3 |
| `readback_epsilon` | `0.001` | 可选，参数回读一致性的容差（T-13） |
| `expect_override` | 省略 | 可选 `{参数名: 期望读回值 或 "any"}`（任务 BJ，B-补-19）。请求级默认，每个 `states[]` 里也可各写一份（状态级优先）。被钳位/被驱动器合法改写的参数（如工程B `BreastSize` 在丝袜开时被 `Clamp_Breast` 层钳到 0.5）回读不等于请求值时，命中这里就不判 `readback_failed`，改在该状态 JSON 记 `overridden` 与 `readback.params[].overridden/override_source`。不写值或写 `"any"` = 任意读回值都接受。见 §3.3 |
| `readback_driver_override` | `true` | 可选，布尔（任务 BJ，BR 收窄）。`true`=实际读回值等于某个 `VRCAvatarParameterDriver` 的 **Set 常量写值**、**且该 Driver 所在状态的入转移条件对同一参数做 `>`/`<` 钳位比较**时，自动判为「被驱动器合法改写」并记 `overridden`（不再整批 aborted）；`false`=回到严格模式，只有显式 `expect_override` 才放行。Bool 的 `If`/`IfNot` 相等判断不算钳位，不放行。见 §3.3 |
| `candidates` | 省略 | 可选，数组（任务 BJ，B-T08a，R9 脚鞋选型）。每项 `{id?, part, mesh, garment?, body?, covers?, states?, keys:{形态键:权重}, zero_keys?, hard?}`：对每个状态、每个候选**施加 keys → 跑一次 T-28a 静态 poke → 还原**，整批结束按 `part` 写 `<out>/r9_<part>.json` 排序表。排序用斑块面积/最大深度/\|si p50\|/si 陷入量/tilt/`|sd p50|`/跟隙/`|d_v p50|`（v2，见 §3.4），**穿越计数与包含率不参与排序**。见 §3.4 |
| `candidates_zero` | 省略 | 可选，字符串数组（任务 CS，R9 补漏）。施加候选前，先把这些键在**该候选 mesh** 上匹配到的每个键写 0，再写候选自己的 `keys`；清零前的旧值写进行内 `zero_applied`，写完读回写进 `applied_readback`，没匹配到的键写进 `zero_missing`（不算 hard 失败）。候选级 `zero_keys` 覆盖它（写空数组 = 该候选不清零）。**不写 = 旧行为**（只写候选自己的键，可能与服装已驱动的姿势重合，见 §3.4 教训） |
| `candidates_reference` | `true` | 可选，布尔（任务 BJ）。候选 poke 是否内嵌同配对的 `containment` 参考列（穿越计数/包含率）；`false` 省一次重活。参考列只写进 `r9_*.json`，不参与排序 |
| `sentinels` | 省略 | 可选 `{positive:[{renderer,shape,weight} 或 {renderer,material_queue}], negative:[{renderer,hide}]}`（T-13）。第一个状态上各跑一次：正样本注入已知缺陷并读回、负样本隐藏被测件并读 V1/V2；**任一不过（含配置错误）整批 `status=aborted`**。见 §3.3 |
| `expect_visible` / `expect_hidden` | 省略 | 可选，渲染器名/路径数组（T-13），作请求级默认；每个 `states[]` 里也可各写一份，追加在默认之后。与实际 `visible = activeInHierarchy && enabled` 比对，不一致 → 该状态 `readback_failed`、整批 aborted。见 §3.3 |
| `settle_frames` 之外的调参 | | `blendshape_epsilon`(1e-4)、`warmup_frames`(10)、`repeat_check`(false)、`volatile_probe`(true)、`ensure_gm`(true)、`auto_play`(false)、`timeout_seconds`(1800) |

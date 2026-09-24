# T1 · 每个状态做什么、健全性检查、易变形态键 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §3「每个状态做什么」/ §3.0 / §3.0.1。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T1 状态驱动器 · 请求格式](state-driver-request.md) · 下一页：[T1 · 回调隔离、头像解析、GestureManager 接管](state-driver-isolation.md) <!-- nav -->

### 每个状态做什么（顺序固定）

1. **复位「用户可控参数」**（任务 Q 改；任务 AD 再改）：可复位集合 = 头像 `VRCExpressionParameters.parameters[].name` 里声明的
   参数 **− VRChat 内置参数**（GM `Vrc3DefaultParams` 列表 + 官方内置名，见 `AuditStateDriver.BuiltinParams`）
   **− 被 `VRCAvatarParameterDriver` 写入、且用户不能直接点的参数**（任务 AD，`reset_driver_targets=false` 时）。
   **复位值 = 该参数在 `VRCExpressionParameters` 里声明的 `defaultValue`**（反射读；字段名以 SDK 实际为准）。
   其他参数（内置参数、Animator-only 参数）一律不碰。
   *为什么第二次改（任务 AD，2026-09-18 实测）*：表达参数里混着一类**不是给用户点、而是参数驱动器维护的内部状态**。
   实例（工程B_Milfy）：厂商参数 `Slippers_OFF` 由「鞋子」部位层 ON/OFF 状态与整套切换层的
   `VRCAvatarParameterDriver` 写入，声明默认值 `0` = 显示拖鞋。每状态前复位把它冲回 `0`，而**同一套服装内
   切换时驱动器不会再触发** → 13 套里 12 套「只关袜子」都冒出小熊拖鞋（与该套自己的鞋叠穿）。同一序列改用
   `reset:none` 按真实操作顺序切则不复现 → 纯**工具假象**。所以默认把这类参数从复位集合里排除；参数若同时
   直接出现在表达菜单控件里（用户也能点）则仍复位，但在 warnings 与 `states.json.driver_targets_user_clickable`
   里列出。扫描范围与出处见 §3.0.3。
   *为什么第一次改（任务 Q，2026-09-18 实测）*：旧实现把复位值取成「T1 启动瞬间读到的实际值」（`initial_at_start`）。
   同一个 Play 会话里连续跑多次 T1 时，上一次最后一个状态的参数值就成了下一次的「启动值」，**跨次运行漂移**：
   · 一次运行停在 `A2_Outfit=1.0`（带兜帽的整套，兜帽压制层会关掉头饰）→ 之后所有运行里头饰都「不显示」，
   被误当成工程缺陷查了半小时；
   · 一次运行停在 `A2_Sok=0` → 之后请求 `{"A2_Outfit":0.214286}`（本意整套全开）实际是「关袜」状态，
   渲图与 agy 结论全部错位。
   根因：把「上次跑完的残留」当成了「默认值」。声明 `defaultValue` 来自资产、跨运行恒定，才是真正的
   「每个状态自己的起点」。
   *为什么不会重蹈「内置参数被写成 0」的覆辙*：内置参数（`ScaleFactorInverse`=1、`EyeHeightAsMeters`≈1.05、
   `Grounded`=1、`TrackingType`=3 …，运行时由 GM 的 `InitForAvatar` 设定）根本**不在**可复位集合里，
   所以复位永远不会碰它们；只有显式声明在表达参数里、又确实是用户可控的参数才用其声明默认值。
   *读不到声明默认时*：退回该参数的 T1 启动实值，并在 `warnings` 里**逐个列出参数名**（另见
   `states.json.reset_fallback_params`），该状态记 `reset_values_source=startup_value_fallback`。
   *代价*：请求里出现、但不在表达参数里的参数不会在状态间自动复位——要么写进表达参数，要么每个状态都显式写。
   `param_defaults` 每个参数带 `reset` / `builtin` / `declared_in_expression` / `driver_target` /
   `reset_excluded_driver_target` 五个布尔便于核对（后两个是任务 AD）。
2. **施加本状态参数**：优先走 GM 的 `Vrc3Param.Set(module, float, obj)`（会触发 `_onChange`，也就是 GM 对
   `LayerControl` / `ParameterDriver` 的模拟）；GM 没有这个参数时退回 `Animator.Set*`。
   状态里**显式写了**的参数照设——即使它是 VRChat 内置参数（这是「拍某个内置参数被拨动后的样子」的唯一途径）。
3. 等 `settle_frames` 帧（用 `Time.frameCount` 计数，不是计数 update 调用）。
4. 快照 + **健全性检查**（见 §3.0）。
5. **回读断言**（T-13，见 §3.3）：用 GM/Animator 读回本状态每个请求参数的实际值，与请求值按 `readback_epsilon`
   比对；再比对 `expect_visible` / `expect_hidden` 与实际可见性。不一致 → 该状态 `readback_failed`，整批 aborted。
6. **哨兵**（T-13，见 §3.3）：只在第一个状态上跑一次正/负样本；任一不过整批 aborted。
7. **跑探针**（任务 R，仅请求里 `probes` 非空）：先按 `pre_probe_blendshapes`（任务 U）临时设形态键，
   再对本状态跑 `grab_chain` / `coincident` / `containment` / `range` / `poke` / `shrink_cover`，结果写进该状态 JSON 的 `probes` 字段
   （§3.2）；无论探针成功失败都在 `finally` 里还原临时形态键。探针失败只记 warning，不拖垮 T1。
   其中 `shrink_cover`（任务 CS，T-33）另把完整结果写 `<out>/shrink_cover_<stateId>.json`，
   并把精简行挂到该状态 JSON 顶层的 `shrink_cover` 字段（repeat 遍写 `.repeat.json`）。
7b. **跑 R9 候选**（任务 BJ，仅请求里 `candidates` 非空，见 §3.4）：对每个候选逐个施加形态键 → 跑一次
   T-28a 静态 poke（配对换成候选自己的 `garment`/`covers`，强制 `reference`）→ 立刻还原；结果累积，
   整批结束按 `part` 写 `<out>/r9_<part>.json`。候选失败只记 warning/行内 `error`，不改快照、不拖垮 T1。
8. 若 `volatile_probe=true`：第 0 遍的第一个状态在快照后再等 `settle_frames` 帧采第二次（见 §3.0.1）。

### 3.0 健全性检查（任务 G）

每个状态设完、等完帧之后立即校验：

- 头像根 `lossyScale` 三个分量都在 **0.5–2**；
- `Head` 骨骼世界坐标 y 比 `Hips` 高 **> 0.2 m**。

不满足 → 该状态 `state_<id>.json` 写 `sanity_failed: true` 与 `sanity_reasons: [...]`；整批结束后
`states.json` 写 `sanity_failed` / `sanity_failures`，并且 **`status.json` 置 error**（`Tick` 在 `Phase.Done`
抛异常让 runner 走 error 分支），不会静默继续。*阈值怎么来的*：正常头像根缩放约 1，0.5–2 覆盖常规体型
调整与毫米级误差；Head-Hips 差 0.2 m 远小于任何正常人形骨架（≈0.5 m+），只用来抓「骨架塌到原点」这种
量级的事故，不参与审美判断。

### 3.0.1 易变形态键探测（`volatile_probe`，任务 G）

默认 `true`。在 **第 0 遍的第一个状态** 上连续采两次快照（间隔 `settle_frames`），两次不同
（|Δ| > `blendshape_epsilon`）的形态键记为 volatile（多半是 `AAO_Merged_Blink` / `EyeWide` / `BrowOuterUp`
这类随时间自动播放的面部键），写进 `states.json.volatile_blendshapes`，并在

- 状态间 `diffs.*.blendshape_changed`；
- `repeat_check=true` 时的 `determinism` 逐行比对

里排除。不这么做的话，同一状态跑两遍的差异会全是这些噪声。代价：只多花第一个状态的一次 `settle_frames`
等待。`"volatile_probe": false` 可关掉。

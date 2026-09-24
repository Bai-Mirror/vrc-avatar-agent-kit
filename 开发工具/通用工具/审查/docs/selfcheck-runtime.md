# 自检 3 · 运行期待验点（1–17） <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §9.2 前半。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[自检 2 · 临时改动→恢复对照表；自检 3 · 编译期](selfcheck-restore.md) · 下一页：[自检 3 · 运行期待验点（18–22）与明确没验证的](selfcheck-runtime-2.md) <!-- nav -->

### 9.2 运行期（必须在 Unity 里才能验的）

| # | 待验点 | 怎么验 | 失败长什么样 |
|---|---|---|---|
| 1 | `ModuleHelper.GetModuleFor` + `GestureManager.SetModule` 在 Play 模式下能真的接管并让参数生效 | `states.json` 里 `gm_controlled=true`、`driver="gesture_manager"`；`A2_HeadAcc` 那条 `diffs.*.any_change=true` | `gm_note` = "场景里没有可用的 GestureManager 组件" → 工程A 场景里得有 GM 物体；或接管了但 `any_change=false` → 看是不是 AAP 参数 |
| 2 | GM 组件是否 enabled 并在跑 `Update()` | `gm_note` 里若带 "组件是 disabled 的" 说明只靠 PlayableGraph 生效 | 若参数完全不动，先查 GM 物体/组件是否被关 |
| 3 | `VRCExpressionParameters.parameters[].name` + `.defaultValue` 反射读得到（任务 Q 后又用回 `defaultValue` 作复位值） | `states.json.reset_param_count > 0`、`reset_values_source="declared_default"`，且 `param_defaults[*].declared_in_expression` 有 true 的项；`defaults_snapshot` 里能看到 `A2_Outfit` 等用户参数的声明默认 | `reset_param_count=0` → 头像没挂 `expressionParameters`（或声明的全是内置参数），没有任何参数会被复位；此时要么每个状态都显式写参数，要么先挂表达参数。若 `reset_values_source="startup_value_fallback"` 且 `reset_fallback_params` 非空 → `defaultValue` 字段名/类型反射失败（对 §7 的 SDK 符号表），这批复位退回启动实值、跨次运行仍可能漂移 |
| 4 | 快照确定性 | 只放 2 个状态 + `"repeat_check": true`，看 `determinism.*.identical` | `false` 时 `first_difference` 会指到具体行；若差的行在 `blendshapes` 且键在 `volatile_blendshapes` 里，说明是自动播放噪声而非不确定 |
| 5 | 参数设置是否即时生效（PlayableGraph 每帧求值） | 断言 `settle_frames=30` 后形态键/显隐确实变了 | 完全不变得考虑加大 `settle_frames` 或确认 GM 在跑 |
| 6 | 头像同名双根的处理 | 在 工程A 场景确认两个根的名字与 active 状态；工具应挑 active 那个 | 报 "找到 2 个且都 active" → 需要先关掉一个 |
| 7 | T3 渲出来的图对不对（朝向、正前方定义、FOV、大小） | 打开 `Head_az0_el0.png`：应是角色**正脸**；`az180` 是后脑 | 反向 → `avatar.transform.forward` 方向与预期不同，改 `az` 起算基准 |
| 8 | `Camera.Render()` 在工程的渲染管线/色彩空间下读回的颜色与背景一致 | 全空场景渲一张，掩码应为 0；或看 `mask_px` 是否明显偏大（把背景误判成 R） | `mask_px` ≈ 全图 → 背景色在 RT 里与 `_bg` 差超过 ε（色彩空间问题），调 `color_epsilon` 或改 `bg` |
| 9 | `GetPixelData<Color32>` 的像素排布（上下翻转） | 存出来的 PNG 是否上下颠倒；存图用 `SetPixels32`，与读回同序，理论一致 | 若颠倒：掩码/统计不受影响（同序比较），但人工看图会歪，需在 `SavePng` 里翻 y |
| 10 | 透明排序正/负样本（第二版逐槽） | 正：工程A「发饰 PixelBoot × 发型 GoldenHour」开启 → PixelBoot 的 `sequence_code_BL_q3050` 槽应 `flagged`，且 `vanished_owners` 里出现 `Hair_GoldenHour` 的合并网格；负：发饰关掉 → 该槽 `vanish_ratio` 为 0 或 `null`；两次都不该再把发型的不透明/剪影槽整片标红 | 正样本检不出 → 看 `candidates` 里有没有该 `(renderer, submesh)`（`renderQueue > transparent_queue_min`？）、掩码像素 ≥ `min_mask_px`？；发型槽仍被标 → 看该条 `t_p50` 是否 ≥ `t_min`、`model_error_p50` 是否偏高 |
| 11 | `Time.frameCount` 在编辑器 Play 循环里正常递增、`EditorApplication.update` 每帧都被调 | 状态数 × settle_frames 的耗时应约等于帧数 ÷ 帧率 | 卡住不动 → 看 `status.json` 的 `progress` 与 `audit.log` |
| 12 | `auto_play` 跨域重载续接 | 不在 Play 时发 `"auto_play": true` 的请求，应自动进 Play 并开始 | 没开始 → 看 `SessionState` 与 `[InitializeOnLoad]` 是否被别的脚本阻断 |
| 13 | 内存 | 10 GB 级别的 Play + 烘焙场景里再开 1024² RT ×2 与 6 个像素缓冲（约 4 MB×6）以及逐视角 PNG | OOM → 降 `size`、降 `azimuths`、关 `transparency_check` |
| 14 | 健全性检查真能抓住「缩放为 0 / 骨架塌」（任务 G） | 正常头像 `sanity_failed=false`、`status=done`；故意把头像根 scale 设 0 重跑 → `sanity_failed=true`、`status=error` | 头像已塌但 `sanity_failed=false` → 检查 `lossyScale` 与 Head/Hips 是否取到 |
| 15 | volatile 探测（任务 G） | 看 `states.json.volatile_blendshapes` 是否列出 `AAO_Merged_Blink`/`EyeWide` 之类；`"volatile_probe": false` 再跑应得 `[]` | 两次快照仍不同但列表为空 → 检查是不是骨骼/显隐在漂，不是形态键 |
| 16 | 回调隔离真的摘掉了老探针（任务 G） | `isolated_callbacks.json.isolated_callbacks` 含 `AvatarGen.RuntimeProbe.OnPlay` / `EarPlayProbe.*`；本轮 Play 期间 `Assets/_Work/运行期探针.md`、`耳朵Play诊断.md` **不更新**；退出 Play 后 `restored_at` 非空 | 列表为空或探针文件仍被写 → 反射路径对不上（换 Unity 版本先按 §7 核对字段名）；若 `_armed` 未冻结，RuntimeProbe 仍可能每帧写参数 |
| 17 | 逐槽掩码 / 透光率模型 / vanished_owners（任务 I） | flagged 记录里 `submesh`/`material`/`render_queue` 与 `candidates` 对得上；`t_p50` 对透明槽明显 > `t_min`、不透明槽根本不进候选；普通 lilToon 透明槽 `model_error_p50` < 0.02；`vanished_owners[0].renderer_path` 指向人眼能确认的「被挡住的那个网格」 | `model_error_p50` 普遍 > 0.05 → 该槽是 Refraction/GrabPass/自定义 Blend，vanished 不可信；`vanished_owners` 为 `null` → ID 着色器没找到或所有 vanished 像素解码失败（看 `warnings`） |

# 自检 2 · 临时改动→恢复对照表；自检 3 · 编译期 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §8 / §9 / §9.1。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[自检 1 · 反射用到的 GM / SDK 符号出处](selfcheck-symbols.md) · 下一页：[自检 3 · 运行期待验点（1–17）](selfcheck-runtime.md) <!-- nav -->

## 8. 自检 2：临时改动 → 恢复 对照表

| # | 工具 | 临时改动 | 恢复位置 | 异常路径 |
|---|---|---|---|---|
| 1 | T1 | GM `ModuleSettings.simulateCulling`：true → false | `AuditStateDriver.Cleanup()`（仅在确实改过时恢复 true） | runner 的 `Stop()` 总是调 `Cleanup()`；`Cleanup()` 自身幂等（恢复后清零标志） |
| 1b | T3 | 同上（T1 结束时会把开关恢复原值，T3 必须自己也关一次，否则渲出来一片空） | `AuditTurntable.Cleanup()` | 同上 |
| 1c | T1 | 场景原本没有 GM 时，临时创建 `__AvatarAudit_GM`（`HideFlags.DontSave`，仅 Play 模式，见 §3.1） | `AuditStateDriver.Cleanup()` → `GmgBridge.DestroyAuditManager()`（仅当 `_auditCreatedGo` 是我们建的，幂等） | runner 的 `Stop()` 总是调 `Cleanup()`；即使 `SetModule` 失败也会销毁 |
| 2 | T1 | 参数值、`PoseT`/`PoseIK` 被改 | **故意不恢复**——T3 要在同一批状态下拍；只在 Play 模式内改动，退出 Play 自动还原 | — |
| 3 | T1 | `GestureManager.SetModule` 让 GM 改控本头像（原来是别的头像时，GM 自己会 `Disconnect` 旧的） | **故意不恢复**（这就是 GM 的正常状态）；只在 Play 模式内 | — |
| 4 | T3 | 全场景渲染器的 `Renderer.enabled`：隔离渲 M/C0/C1 时除 R 外全部 → false | `EnterIsolation`/`ExitIsolation`（快照在 `_enabledSnapshot`），候选级 `finally` 再兜底一次 | `ExitIsolation` 幂等；`Cleanup()` 也会兜底 |
| 5 | T3 | 候选 R 的 `sharedMaterials[第 k 槽]` → FlatColor / Invisible（B 图时 → Invisible） | 每个候选的 `finally`（`r.sharedMaterials = origMats`） | 同上 |
| 6 | T3 | ID 渲染时除 R 外每个可见渲染器的 `sharedMaterials` → 唯一色 FlatColor，且 `R.enabled` → false | `ComputeVanishedOwners` 的 `finally` 逐渲染器写回 `saved[j]` | 同上 |
| 6b | T3 | 相机 `_cam.cullingMask` 在 `~0`（隔离）/ `_originalMask`（A/B）间切；`backgroundColor` 在黑 / 白 / `bg` 间切 | `Enter`/`ExitIsolation` 与各段 `finally` 恢复成 `_originalMask` / `_bg`；相机本身是临时对象 | 同上 |
| 6c | T3 | `mask_layer` | **不再改动**（第二版用 enabled 隔离；字段只为兼容旧请求保留在输出里） | — |
| 7 | T3 | `RenderTexture.active` 被改 | `RenderToBuffer()` 内恢复 `prev`；`Cleanup()` 再置 `null` | — |
| 8 | T3 | 临时 `Camera` GameObject（`HideFlags.HideAndDontSave`） | `AuditTurntable.Cleanup()` → `DestroyImmediate` | runner 的 `Stop()` 总是调 `Cleanup()`；`SafeDestroy` 吞异常并 warn |
| 9 | T3 | 临时 `RenderTexture` ×2 / `Texture2D` ×2 / 临时材质（FlatWhite、Invisible、每个可见渲染器一个 ID 色） | `AuditTurntable.Cleanup()`（`Release()` + `DestroyImmediate`） | 同上 |
| 10 | runner | `EditorApplication.update += Pump` | `Stop()` 里 `-= Pump` | 每条失败路径都经过 `Stop()` |
| 11 | runner | `SessionState` 里的待跑请求（`auto_play`） | `TryResumePending()` 读到后 `SessionState.EraseString` | 若一直没进 Play，键会留到本次编辑器会话结束（不影响场景） |
| 12 | runner | `EditorApplication.playModeStateChanged` 订阅 | 静态订阅，随域重载自动重建；不解除（幂等） | — |
| 13 | runner（T1/T2/T3 通用） | 摘除工程侧（`Assembly-CSharp*`、非 `AvatarAudit`）的 `EditorApplication.update` 回调 | `AuditCallbackIsolation.Restore()`：收到 `EnteredEditMode` 后经 `delayCall` **按原顺序**挂回（§3.0.2） | 反射不到字段 → 记 warning 跳过；Play 中被强杀 → 不恢复（进程结束） |
| 14 | runner（T1/T2/T3 通用） | 摘除工程侧的 `playModeStateChanged` 回调 | 同上，走官方 `add_playModeStateChanged` 访问器挂回 | 同上；`Restore` 安排在 `delayCall`，不在事件分发中改订阅表 |
| 15 | runner（T1/T2/T3 通用） | `AvatarGen.RuntimeProbe._armed` true → false | **不恢复**——本轮不该让老探针跑；若下次进 Play 时它的 `OnPlay` 已被挂回，会自行重新 armed | 类型/字段不存在 → 静默跳过 |

清单同时写进输出目录的 `isolated_callbacks.json`（`isolated_callbacks` / `runtime_probe_disarmed` / `restored_at`）。

**场景持久性**：

- 工具**从不调用 `EditorSceneManager.MarkSceneDirty`，从不保存场景**。
- T3 允许在编辑模式跑，`enabled` / `sharedMaterials` 的瞬时改动在 `finally` 里还原，还原后场景数据与跑之前一致；
  但 Unity 可能在属性被写时给场景置上 dirty 标记（值已还原，只是标记可能留着）——所以**编辑模式下跑完
  不要顺手保存场景**，先 `File > Revert` 或确认 diff 为空再存。
- 输出只写请求里 `out` 指定的目录（+ `<工程>/Library/AvatarAudit/` 由调用方自己放请求）。

---

## 9. 自检 3：不开 Unity 验证不了的部分 / Claude 验收重点

### 9.1 编译期（Claude 第一件要看的）

1. 跑 §1 的 `sync_audit.py "<工程>"` 后，工程里 `<工程>/Assets/AvatarAudit/{Editor,Runtime}` 是否 **0 error**
   （着色器还要能被 `Shader.Find("Hidden/AvatarAudit/FlatColor")` / `Hidden/AvatarAudit/Invisible` 找到，
   找不到时 `transparency.json` 会带 warning 且 `transparency_check` 静默降级成不做检测）。我已用 Unity 2022.3.22f1 的
   参考程序集预编译过 6 个 `.cs`，所以若有报错，优先怀疑：
   - asmdef 引用的程序集名在**该工程**里不存在（NDMF / `nadena.dev.modular-avatar.core` /
     `com.anatawa12.avatar-optimizer.api.editor` / `VRC.SDK3A` / `0Harmony.dll`——工程A 与工程C两份 `Packages/`
     里名字已核对过，换工程要重核）；`versionDefines.expression` 为**方括号精确匹配** `[1.18.1]` / `[1.9.16]`
     （**裸版本号 `1.18.1` 在 Unity 里是 ≥1.18.1**，出处 2022.3 手册《Assembly definitions · Version Define
     expressions》：https://docs.unity3d.com/2022.3/Documentation/Manual/ScriptCompilationAssemblyDefinitionFiles.html#version-define-expressions ），
     只有包版本**正好等于**这两个版本才定义 `AUDIT_MA_1_18_1` / `AUDIT_AAO_1_9_16`，其它版本（含未来 1.19+）
     不定义、`#if` 段编译成退路；**三单实测走退路**：工程G/工程F MA 1.17.1、工程E MA 1.18.0 → `ma_analysis.json`
     写 `available=false`（`reason_code: harmony_unavailable`；工程F/工程E 已读编译 DLL 核实无
     `ReactiveObjectAnalyzer`）。改 `[1.18.1]` 对当前 1.18.1 单无影响，只堵住「未来版本静默进真路径」；修订说明（09-19，签字 B-补-15）；
   - 旧落点没清干净，`Assets/Editor/` 下还留着 `AvatarAudit` 同名类型（sync 会删，若报重名先看这里）；
   - 工程用了 URP/HDRP 之外的 `GetPixelData` 之类 API 差异（我用的都是 2022.3 基线 API）。
2. 反射相关的编译期风险 = 0（没有直接引用 GM / SDK 类型）；**但这也意味着符号拼错只会在运行期以
   `note` / `params_missing` 的形式暴露**，所以要按 §7 再确认一遍 GM 包版本仍是 3.9.9。

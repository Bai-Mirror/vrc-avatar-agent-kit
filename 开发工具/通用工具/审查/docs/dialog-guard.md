# 单按钮对话框屏蔽 AuditDialogGuard <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §14。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[请求序列 sequence · 样例、验收与局限](sequence-example.md) <!-- nav -->

## 14. 单按钮对话框屏蔽 `AuditDialogGuard`（任务 BU）

**用途**：进 Play 时插件会弹「只有一个按钮」的模态框（2026-09-19 工程A 的 VRCFury 参数超限警告，
`Packages/com.vrcfury.vrcfury/Editor-Avatars/Service/ExceptionService.cs` 参数 342/256 只有 Ok）。
模态框挡住编辑器主线程 → UnityMCP 连续超时、审查请求跑不了，只能杀 Unity。
`unity/Editor/AuditDialogGuard.cs`（`[InitializeOnLoad]`）把这类单按钮框改成
「写一行 `Debug.LogWarning("[AvatarAudit] 已屏蔽对话框：…")` + 追加日志文件，然后当用户点了 OK 直接返回 `true`」。

**生效条件**：只有环境变量 `AVATARAUDIT_SUPPRESS_DIALOGS=1` 时才装 Harmony 补丁；不设或设成别的值完全不做任何事。

**只拦三参数 `EditorUtility.DisplayDialog(string title, string message, string ok)` 的理由**：
这个重载只有一个「Ok」，没有取舍，机器替点等于放行提示。四参数（ok/cancel）与五六参数
（`DialogOptOutDecisionType`）**一律不拦**——它们要用户在「保存 / 不保存 / 取消」里表态，
自动替选会丢改动（例如退 Play / 退编辑器时的保存场景框）。补丁只挂 3 参 MethodInfo。

**Harmony 来源**：运行时用反射找 `HarmonyLib.Harmony`（VRCSDK 的 `0Harmony.dll` 或 NDMF 自带的），
找不到只打 warning、不影响编译；`AuditDialogGuard.cs` 不 `using HarmonyLib`，asmdef 也不新增引用。

**日志位置**：`<工程>/Library/AvatarAudit/suppressed_dialogs.log`，每行一次屏蔽，
`时间 <TAB> 标题 <TAB> 消息前 500 字`（消息里的换行折成空格）。

### 14.1 给 Claude 的 Unity 验收步骤

1. 带环境变量启动 工程A：
   `AVATARAUDIT_SUPPRESS_DIALOGS=1 DISPLAY=$DISPLAY_FALLBACK <Unity安装根>/Editors/2022.3.22f1/Editor/Unity -projectPath "工程A"`。
2. 用 `sync_audit.py <工程>` 部署后看 Console，应有一行
   `[AvatarAudit] 已启用单按钮对话框屏蔽（AVATARAUDIT_SUPPRESS_DIALOGS=1，id=local.avatar-audit.dialog-guard）。`
3. 进 Play：以前必弹的 VRCFury 参数超限警告应不再出现，Console 出现
   `[AvatarAudit] 已屏蔽对话框：<标题> | <消息前500字>`；同一会话里 UnityMCP 仍可用（`manage_scene get_active` 有响应）。
4. 读 `<工程>/Library/AvatarAudit/suppressed_dialogs.log`，有对应时间戳的行。
5. 反向验证：不带 `AVATARAUDIT_SUPPRESS_DIALOGS` 重启 → 没有「已启用…」那行，弹框照旧（别在有单按钮框挡路时测）。

### 14.2 已做的离线验证（未启动 Unity）

- 全量 `unity/Editor/*.cs` 对 工程A 已编 ScriptAssemblies 编译：含版本宏 / 无宏两分支都 0 error。
- 引用集合去掉 `0Harmony.dll` 后，「整程序集（无宏退路）」与「只编 `AuditDialogGuard.cs`」都 0 error
  → 反射写法不依赖 Harmony 编译期引用。
- 用真实 `0Harmony.dll`（2.0.5）+ `UnityEditor.CoreModule.dll` 在 mono 下走了一遍本类同款反射补丁：
  找到 `DisplayDialog(string,string,string)`、`Patch` 重载解析成功、补丁后调用返回 `True` 且未弹框；
  `__0/__1` 按位置绑定有效，四参数重载未被挂。
- 脚本与日志：`_长程任务_20260918/派工/tmp/bu/`（`compile_bu.sh` / `compile_bu.log` / `harness2.cs`）。

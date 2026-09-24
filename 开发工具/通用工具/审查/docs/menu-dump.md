# T4 构建后菜单树与参数导出 AuditMenuDump · 部署、请求、行为 <!-- nav -->

> 旧称：T4（原 `审查/README_T4.md`） 页首 / §1–§4。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 下一页：[T4 菜单导出 · 输出字段](menu-dump-output.md) <!-- nav -->

# T4 · 构建后菜单树与参数导出 `AuditMenuDump` —— 部署、字段与验收自检

> 文件头【项目沉淀】见 `AuditMenuDump.cs`。本页只讲**怎么部署、怎么发请求、输出长什么样、字段什么含义、已知局限、怎么自检**。
> 设计依据：`_长程任务_20260918/审查工具设计.md` 的 T4 第一条（「从烘焙后的 `VRCExpressionParameters`
> 和菜单结构自动列出可控参数与离散取值」）+ 派工 `L`。
> 本轮**只写代码、不开 Unity、不调 MCP**；运行期行为由 Claude 在 工程A 工程里编译/首跑核对（见第 8 节）。

---

## 1. 部署

源码目录：`开发工具/通用工具/审查/`（T-09 后 `.cs/.shader` 在 `审查/unity/Editor/`）。审查某个工程时
统一用 `perception/sync_audit.py`（见 `README.md` §1）：它把 `审查/unity/` 铺到
`<工程>/Assets/AvatarAudit/`（`Library/` 不进版本库；审查完随交付清理删除）：

```
AuditIO.cs            # 公共层：JSON、status.json、菜单入口、多帧泵、IAuditTool（本轮**不要动**）
AuditMenuDump.cs      # ← 本文件（T4）
AuditStateDriver.cs   # T1（按菜单组合设参数时用）
README_T4.md          # ← 本页
```

`AuditMenuDump.cs` 只依赖 `UnityEngine` / `UnityEditor` 与 `AuditIO.cs` 的公共件；
**不直接引用 VRChat SDK 类型**（全部反射），所以某个工程没装 SDK / SDK 版本不同也只是降级写 warning。

---

## 2. AuditIO 需要加的分派（一行，由 Claude 加）

`AuditIO.cs` 现状的分派链（约第 1418~1421 行）：

```csharp
if (toolId == "state") tool = new AuditStateDriver();
else if (toolId == "turntable") tool = new AuditTurntable();
else if (toolId == "fit") tool = new AuditFitProbe();
else { Debug.LogError("[AvatarAudit] 未知 tool: " + toolId + "（支持 state / turntable / fit）"); return; }
```

改成：

```csharp
if (toolId == "state") tool = new AuditStateDriver();
else if (toolId == "turntable") tool = new AuditTurntable();
else if (toolId == "fit") tool = new AuditFitProbe();
else if (toolId == "menu") tool = AuditMenuDump.Create();      // ← 只加这一行
else { Debug.LogError("[AvatarAudit] 未知 tool: " + toolId + "（支持 state / turntable / fit / menu）"); return; }
```

本类实现的接口：

```csharp
namespace AvatarAudit
public sealed class AuditMenuDump : IAuditTool
{
    public static IAuditTool Create();                 // 静态入口（文件头也写了）
    string ToolId                { get { return "menu"; } }
    bool   RequiresPlayMode      { get { return true; } }   // 构建后的菜单只在 Play 里存在
    int    DefaultTimeoutSeconds { get { return 300; } }
    void   Begin(AuditContext ctx);   // 解析请求 + 软解析头像（失败不抛，记 warning）
    bool   Tick();                    // 等 warmup_frames 帧 → 一次性读盘 + 写 3 个输出 → 完成
    void   Cleanup();                 // 只读工具，无临时改动，空操作（幂等）
}
```

**为什么等 `warmup_frames` 帧才读**：NDMF 的 Apply on Play 在 `AvatarActivator.Awake` 里跑
（`nadena.dev.ndmf/Runtime/ApplyOnPlayGlobalActivator.cs:186-191`，`DefaultExecutionOrder -9995`），
而 AuditIO 可能在 `EnteredPlayMode` 回调里就 `Begin`。等默认 10 帧，让构建彻底落地再读，最稳；
请求字段 `warmup_frames` 可调（设 0 = 不等）。

**前置条件**：必须先进入 Play 模式（`RequiresPlayMode=true`；非 Play 时 AuditIO 直接报错，
可在请求里加 `"auto_play": true` 让 AuditIO 先进 Play 再自动开跑）。

---

## 3. 请求 JSON

```json
{"tool":"menu","avatar":"<头像根名>","out":"/abs/path",
 "warmup_frames":10,
 "root_label":"顶层",
 "max_depth":20,
 "max_controls":5000}
```

| 字段 | 默认 | 含义 |
|---|---|---|
| `tool` | 必填 | 必须为 `"menu"`。 |
| `avatar` | 必填 | 头像根 GameObject 名。走 `AuditAvatar.Resolve`：面捕克隆出两个同名根且都活跃时报错并列路径。 |
| `out` | 必填 | 输出目录（绝对路径）。`menu_tree.json` / `params.json` / `menu_tree.md` 写在这里。 |
| `warmup_frames` | 10 | 进 Play 后等多少帧再读（等 NDMF/MA 构建落地）。`0` = 立刻读。 |
| `root_label` | `顶层` | 菜单路径的根前缀。 |
| `max_depth` | 20 | 子菜单递归深度上限，超出记 warning 并停止。 |
| `max_controls` | 5000 | 控件总数上限，超出记 warning 并停止。 |

---

## 4. 行为

1. 用 `AuditAvatar.Resolve` 找活跃头像根（同 T1/T3 口径）。
2. 反射读 `VRCAvatarDescriptor`：
   - `expressionsMenu`（`VRCExpressionsMenu`）→ 递归遍历 `controls`；防环按 **实例 ID 去重**
     （环、以及同一子菜单被多个控件共享，都只展开一次并记 warning）；
   - `expressionParameters`（`VRCExpressionParameters`）→ 参数表
     `name / valueType / defaultValue / saved / networkSynced`；
   - `baseAnimationLayers` → 每层 `animatorController` 的参数表。
3. 每个控件输出：`path`（`顶层/子菜单名/控件名`）、`type`（**SDK 反射到的枚举名 + 整数值**）、
   `parameter_name`、`value`、`sub_parameters[].name`、`labels`。
4. 为每个参数汇总「菜单里出现过的取值」与「建议取值」、以及引用它的控件路径。
5. 标出两组差集：
   - `params_not_in_menu`：控制器里有、菜单里没有的参数；
   - `menu_params_undeclared`：菜单里有、`expressionParameters` 里没有的参数
     （VRChat 里不同步、菜单操作无效或仅本地）。
6. 写 `menu_tree.json` / `params.json` / `menu_tree.md`；读不到类型/字段只写 warning 不抛。

**warnings 写到哪**：`ctx.Warn(...)` 会把每条 warning 追加到 `out/audit.log`，并进入
`menu_tree.json` / `params.json` 两处的 `warnings` 数组。`status.json` 由 AuditIO 统一管理
（只放 `state` / `progress` / `message`），本工具不单独往里灌 warning；要看明细请查 `audit.log`
与两个 JSON 的 `warnings`。

---

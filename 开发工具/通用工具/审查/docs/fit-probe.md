# T2 贴合探针 AuditFitProbe · 部署、分派、请求 <!-- nav -->

> 旧称：T2（原 `审查/README_T2.md`） 页首 / §1–§3。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 下一页：[T2 贴合探针 · 算法与判据（1–6）](fit-probe-algorithm.md) <!-- nav -->

# T2 · 贴合探针 `AuditFitProbe` —— 部署、约定与验收自检

> 文件头【项目沉淀】见 `AuditFitProbe.cs`。本页只讲**怎么部署、怎么发请求、输出长什么样、怎么自检**。
> 设计依据：`_长程任务_20260918/审查工具设计.md` 的 T2 一节 + `派工/E_审查工具T2.md`。
> 本轮只写代码、不开 Unity；运行时行为由 Claude 在 工程A 工程里编译/首跑核对（见第 10 节）。
>
> **v3（2026-09-18，工程A 实测两处修正）**：
> 1. **覆盖范围**：身体顶点只对「自身蒙皮覆盖该部位的衣物」计入 `covered`/`pierced`，其余命中记
>    `out_of_scope`。——修 `sailor` 上衣把手（袖口几何在 25 mm 射程内）误报成穿出。
> 2. **脚部专项**：从「每只脚挑一件覆盖最多的衣物」改为「每只脚 × 每件覆盖该脚的衣物分别输出」，
>    并把衣物分类 `footwear`（鞋）/`legwear`（袜）/`other`。——修 `feet` 选到 `stocking`（袜）却去量
>    「脚底到鞋内底」的问题。
> 详见 §4.6 与 §4 第 7 条；回归清单见 §9.5。

---

## 1. 部署

源码目录：`开发工具/通用工具/审查/`（T-09 后 `.cs/.shader` 在 `审查/unity/Editor/`）。审查某个工程时
统一用 `perception/sync_audit.py`（见 `README.md` §1）：它把 `审查/unity/` 铺到
`<工程>/Assets/AvatarAudit/`（`Library/` 不进版本库、也不会被导入；审查完随交付清理删除）：

```
AuditIO.cs            # 公共层：手写 JSON、status.json、菜单入口、多帧状态机泵、IAuditTool
AuditStateDriver.cs   # T1
AuditTurntable.cs     # T3
AuditFitProbe.cs      # ← 本文件（T2）
README.md             # T1/T3 总体说明（工具 C 产出）
README_T2.md          # ← 本页
```

`AuditFitProbe.cs` 只依赖 `UnityEngine` / `Unity.Collections` / `Unity.Jobs`（后两者是 UnityEngine
自带的 `NativeArray`/`JobHandle`，**不需要额外包**），不依赖 VRChat / MA 类型；与 AuditIO 的耦合面见第 2 节。

---

## 2. AuditIO 需要加的分派（一行）

本轮开工时 `AuditIO.cs` 已存在且已有分派表（工具 C 产出），其架构是 `IAuditTool` + 多帧泵。
因此 T2 **实现 `IAuditTool`**，由 AuditIO 用与 T1/T3 相同的方式分派。在 `AuditRunner.StartFromJson`
的分派链里加一行（`AuditIO.cs` 现状约为第 1060~1062 行）：

```csharp
if (toolId == "state") tool = new AuditStateDriver();
else if (toolId == "turntable") tool = new AuditTurntable();
else if (toolId == "fit") tool = new AuditFitProbe();          // ← 只加这一行
else { Debug.LogError("[AvatarAudit] 未知 tool: " + toolId + "（支持 state / turntable / fit）"); return; }
```

T2 实现的接口（`AuditFitProbe.cs` 文件头注释里也写了一份）：

```csharp
namespace AvatarAudit
public sealed class AuditFitProbe : IAuditTool
{
    string ToolId                { get { return "fit"; } }
    bool   RequiresPlayMode      { get { return true; } }   // T1 设好的状态只在 Play 里存在；且只有 Play 才用批处理
    int    DefaultTimeoutSeconds { get { return 1800; } }
    void   Begin(AuditContext ctx);   // 同步跑完全部：解析请求→烘焙→射线→写 geo_<state_id>.json
    bool   Tick();                    // 恒返回 true（Begin 已做完，下一帧收尾）
    void   Cleanup();                 // 幂等兜底：恢复临时改动、销毁临时物体
}
```

**为什么 Begin 里一次做完**：T2 本质是一批射线计算，没有「等 N 帧」的需求；`Run` 内部用
`RaycastCommand.ScheduleBatch` 一次性提交再 `Complete()`。大工程会阻塞主线程数秒~十几秒，属预期。
`Tick()` 恒 true，AuditIO 的泵下一帧即结束。

**前置条件**：T2 量的是「当前姿势」。请先由 T1 把状态设好并**保持 Play 模式**，再发 T2 请求
（用 `state_id` 标注是哪个状态）。T2 自己**不设任何 Animator 参数**。`RequiresPlayMode=true`，
非 Play 模式 AuditIO 会直接报错（可用请求字段 `auto_play:true` 让 AuditIO 先进 Play）。

复用的 AuditIO 公共件：`AuditAvatar.Resolve`（同名多根的口径与 T1/T3 一致）、`AuditJson`/`JsonObject`
（输出 JSON，键序=插入序、确定性）、`AuditStatus`（status.json 与 audit.log）、`AuditUtil`
（`RelPath` / `ScenePath` / `SafeFileName`）、`AuditContext.Warn`（收集 warnings 一并写进结果）。

---

## 3. 请求 JSON

```json
{"tool":"fit","avatar":"<头像根名>","out":"/abs/path","state_id":"default",
 "body":"auto",
 "exclude_name_regex":"(?i)(hair|face|eye|lash|tooth|tongue|head|halo|particle|nail|avatarhight|tail|ear)",
 "include_only":null,
 "cover_mm":25, "pierce_mm":15, "min_depth_mm":1.0,
 "region_min_share":0.02,
 "foot":{"enabled":true,"probe_mm":40,"sole_min_mm":4,
         "footwear":["kaguya_cloth/loafer"],"legwear":["kaguya_cloth/stocking"]},
 "perturb":null,
 "hide":null,
 "markers_top":200}
```

| 字段 | 默认 | 含义 |
|---|---|---|
| `tool` | 必填 | 必须为 `"fit"`。 |
| `avatar` | 必填 | 头像根 GameObject 名。走 `AuditAvatar.Resolve`：面捕克隆出两个同名根且都活跃时报错并列路径。 |
| `out` | 必填 | 输出目录（绝对路径）。 |
| `state_id` | `default` | 只影响输出文件名 `geo_<state_id>.json` 和 `state_id` 字段。 |
| `body` | `auto` | `auto` 或身体网格相对头像根的层级路径（也接受场景全路径）。`auto` 规则见第 4 节第 1 条。 |
| `exclude_name_regex` | 见上 | 按 **GameObject 叶子名** 排除衣物候选。v2 默认多排 `nail`/`avatarhight`/`tail`/`ear`。 |
| `include_only` | `null` | v2 新增：正则，**只测**叶子名匹配的衣物（在 `exclude_name_regex` 之后再过滤）；`null`/缺省不限。 |
| `cover_mm` | 25 | 外向射线长度；`<=0` 视为取默认。 |
| `pierce_mm` | 15 | 内向射线长度；`<=0` 视为取默认。同时也是 `depth_saturated` 的基准（见第 4.5 节）。 |
| `min_depth_mm` | 1.0 | 穿出深度小于此值不计；`<=0` 视为取默认（想全收用 `0.001`）。 |
| `region_min_share` | 0.02 | **v3**：衣物顶点里「主骨骼归到某部位」的顶点占比达到它，才算该衣物覆盖该部位。写 `0.02` 或 `2` 都表示 2%；非法值退回 0.02。见 §4.6。 |
| `foot` | 缺省即开 | 写 `{"enabled":false}` 可关；没写 `foot` 键或写 `null` 都按开、`probe_mm=40`。 |
| `foot.probe_mm` | 40 | 脚底上/下射线长度；`<=0` 视为 40。 |
| `foot.sole_min_mm` | 4 | **v3**：脚底下方**厚度** ≥ 它 → `footwear`；写顶层 `sole_min_mm` 也可（`foot` 里的优先）；`<=0` 视为 4。 |
| `foot.footwear` | `[]` | **v3**：显式指定鞋的路径清单（匹配相对头像根全路径或叶子名），分类依据记为 `request`，优先级最高。 |
| `foot.legwear` | `[]` | **v3**：显式指定袜的路径清单，同上。 |
| `perturb` | null | 自检：`{"renderer":"<路径>","blendshape":"<名>","weight":100}`，烘焙前临时设形态键。 |
| `hide` | null | 自检：`"<衣物渲染器路径>"`，烘焙前临时 `enabled=false`。 |
| `markers_top` | 200 | 输出前 N 个最深穿出点。 |


> `params` 字段：输出的 `params` 就是你这一份请求对象（由 AuditIO 的 `JsonObject` 原样嵌入），
> 字段顺序与请求一致；因为 `AuditJson` 解析器不接受注释，请求文件必须是**合法 JSON**（不要照抄本文档
> 示例里的 `//` 注释）。

---

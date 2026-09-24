> ← [工具索引](../工具索引.md) <!-- tools_index.py 自动生成：整页覆盖，勿手改 -->

# 工具索引 · 审查-unity（20 个文件）

由 `python3 开发工具/通用工具/tools_index.py --write` 从各脚本文件头的「用途 / 可复用性」生成，整页覆盖；要改内容请改脚本文件头。路径相对 `开发工具/`。

### 通用工具/审查/unity/Editor

| 路径 | 用途 | 可复用性 |
|---|---|---|
| `通用工具/审查/unity/Editor/AuditBatch.cs` | 批处理入口：无界面跑部件盘点（含 key_follow）并导出 inventory.json，只读不存场景。 | ★★ 审查工具链的一环 |
| `通用工具/审查/unity/Editor/AuditBodyPick.cs` | 「哪块网格是身体」的共享判据（蒙皮权重同时覆盖脚与躯干），抽出来给 T-05/T-10/T2 三处共用。 | ★★ 审查工具链的一环 |
| `通用工具/审查/unity/Editor/AuditBuildPasses.cs` | T-12 构建期截获的 NDMF 插件 `local.avatar-audit` 与 SDK 回调次序日志。 | （未标） |
| `通用工具/审查/unity/Editor/AuditDeleteCoverage.cs` | MA ShapeChanger 的 `ChangeType=Delete` 把身体某形态键钉死后，该形态键影响到的 | ★★★ 换单子随 `审查/unity/` 一起同步（sync_audit.py） |
| `通用工具/审查/unity/Editor/AuditDialogGuard.cs` | 任务 BU —— 进 Play 时插件会弹「只有一个按钮」的模态框（2026-09-19 工程A 的 | （未标） |
| `通用工具/审查/unity/Editor/AuditFitProbe.cs` | 用几何数值判定「身体从衣物/鞋袜里穿出」与「脚与鞋不贴合」。 | ★★★ 换单子直接复制到 <工程>/Assets/Editor/AvatarAudit/ |
| `通用工具/审查/unity/Editor/AuditFxExport.cs` | T-12 pass B —— Optimizing 阶段、AAO 之后的 `AfterPlugin("com.anatawa12.avatar-optimizer")` | （未标） |
| `通用工具/审查/unity/Editor/AuditHarmonyMA.cs` | T-12 —— 用 Harmony Postfix 钩 MA 自己的 `ReactiveObjectAnalyzer.Analyze`， | （未标） |
| `通用工具/审查/unity/Editor/AuditIO.cs` | VRChat 头像视觉审查工具（T1 状态驱动 / T3 环绕渲图）的公共层—— | （未标） |
| `通用工具/审查/unity/Editor/AuditMappingProbeInfo.cs` | T-12 —— 借 AAO 公开 API `ComponentInformation<T>.ApplySpecialMapping` 拿「构建前名字 → 构建后名字」 | （未标） |
| `通用工具/审查/unity/Editor/AuditMenuDump.cs` | Play 模式下 NDMF「Apply on Play」构建完成之后，头像的 | ★★★ 换单子直接复制到 <工程>/Assets/Editor/AvatarAudit/ |
| `通用工具/审查/unity/Editor/AuditPartInventory.cs` | 编辑模式一次性把「这个头像由哪些部件组成、每件长什么样、怎么被切换」 | ★★★ 换单子直接复制到 <工程>/Assets/AvatarAudit/Editor/ |
| `通用工具/审查/unity/Editor/AuditProbes.cs` | T1 的补充量具。T1 快照记的是「谁可见、材质是谁、形态键多少」；本文件在此之上 | ★★★ 换单子直接复制到 <工程>/Assets/Editor/AvatarAudit/ |
| `通用工具/审查/unity/Editor/AuditSequence.cs` | 审查「请求序列」——一次菜单触发按顺序跑完多个 T1/T3/T4/fit 子请求。 | （未标） |
| `通用工具/审查/unity/Editor/AuditStateDriver.cs` | T1 状态驱动器。在 Play 模式下对真实构建结果施加 VRChat 参数，等动画稳定后把 | （未标） |
| `通用工具/审查/unity/Editor/AuditTurntable.cs` | T3 环绕渲图 + 透明排序检测（第二版：按子网格候选 + 透光率模型）。 | （未标） |
| `通用工具/审查/unity/Editor/NipplePatchFrames.cs` | 把「工程D乳贴补帧」那约 40 行手工 execute_code 落成可复跑菜单动作——编辑模式量出身体 | ★★★ 随 `审查/unity/` 一起由 perception/sync_audit.py 同步进工程 |
| `通用工具/审查/unity/Editor/T3ArmFreeze.cs` | 把「工程F t3_arm」那批对照从手工 execute_code 变成可复跑的一次菜单动作—— | ★★★ 随 `审查/unity/` 一起由 perception/sync_audit.py 同步进工程 |
| `通用工具/审查/unity/Editor/T3RpSyncSim.cs` | 把「工程E t3_rp_*」那批 nosync / sync 对照从手工 execute_code 变成可复跑的一次菜单动作—— | ★★★ 随 `审查/unity/` 一起由 perception/sync_audit.py 同步进工程 |

### 通用工具/审查/unity/Runtime

| 路径 | 用途 | 可复用性 |
|---|---|---|
| `通用工具/审查/unity/Runtime/AuditMappingProbe.cs` | T-12 构建期截获的「实例表」载体。 | （未标） |

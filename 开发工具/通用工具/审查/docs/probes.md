# T1 纯数据探针总览 · grab_chain / coincident <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §3.2 / §3.2.1 / §3.2.2。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T1 · reset 模式与切换残留测试](state-driver-reset.md) · 下一页：[探针 containment（包含率）](probe-containment.md) <!-- nav -->

### 3.2 纯数据探针（任务 R，请求 `probes`）

2026-09-18 在 工程A 上，三处用户「转两圈就看到」的缺陷都是靠**数据**定位的，渲图反而出过假象
（头饰抓屏、外套双层重合、MMN 鞋脚趾穿出）。这几支探针就是把当时 Claude 手写在 `execute_code` 里的
量法固化下来：每个状态快照后顺带跑，结果写进该状态的 `probes` 字段，`states.json` 汇总命中数。
它们的共同口径：**在同一个已经施加好参数的状态上量**，全部同步完成；临时 GameObject / Mesh /
`Physics.queriesHitBackfaces` 都在 `finally` 里恢复，不 `MarkSceneDirty`、不保存场景。
字段与命中数定义如下（命中数写进 `states.json`，见 §4）。

#### 3.2.1 `grab_chain`——抓屏链

抓屏（GrabPass `_lilBackgroundTexture`）的着色器要先抓一张屏幕图，**抓取点之后、队列更靠后的可见物
不会出现在那张图里**，所以透过抓屏窗口看过去会「消失」。判据：

- 遍历可见渲染器（`activeInHierarchy && enabled`）的每个材质槽；`shader.name` 匹配正则
  `grab_shader_regex`（默认 `lilToonGem|lilToonRefraction|lilToonMultiGem|lilToonMultiRefraction|LilBugShader/Refraction`）的算「抓屏材质」；
- **抓取点 = 抓屏材质里最小的 `renderQueue`**；
- **`hidden_materials`** = 可见、非抓屏、`renderQueue ≥ 抓取点` 且 `< 4000` 的材质槽——这些透过抓屏窗口看不见；
- **`grab_point_lt_3000`**：抓取点 < 3000 的标记（常见危险信号，工程A 头饰就是 2450）。

`probes.grab_chain` 字段：`grab_shader_regex`、`grab_materials[{renderer,slot,material,shader,render_queue}]`、
`grab_point_queue`、`grab_point_materials[]`、`hidden_materials[]`、`grab_point_lt_3000`、`hits`、`note`。
**命中数 = `hidden_materials` 条数**。没有抓屏材质时 `grab_point_queue=null`、`hits=0`。
`renderQueue` 取的是材质生效后的队列（有覆盖用覆盖，否则用着色器队列），与 T3 透明检测同口径。

#### 3.2.2 `coincident`——两件几乎重合的可见网格

生成器照搬厂商 ON clip 时，会把默认关的备选件也收进开关组，于是外套与其备选件同时激活、70% 顶点
相距 ≤0.5 mm。判据：

- 只比较**可见 SkinnedMeshRenderer** 两两；先过两道闸：包围盒相交、顶点数比在 0.5–2；
- 身体网格排除（请求 `body` 或自动识别，见 §3 表），所以「身体与贴身衣物天然接近」不计入；
- 双方 `BakeMesh(mesh, true)` 后转到世界坐标，对 A 的每个顶点用 **`coincident_grid_mm`（默认 2 mm）**
  网格哈希查 27 邻格内 B 的最近顶点，统计最近距离 ≤ `coincident_near_mm`（默认 0.5 mm）的比例
  （A→B 与 B→A 取大）；**≥ `coincident_ratio`（默认 0.5）记命中**。

`probes.coincident` 字段：`coincident_ratio_threshold`、`grid_mm`、`near_mm`、`body`、`body_source`、
`candidate_meshes`、`pairs_considered`、`pairs_evaluated`、`truncated`、`hits`、
`coincident_pairs[{a,b,vertices_a,vertices_b,a_to_b_0.5mm,b_to_a_0.5mm,ratio_0.5mm,ratio_1mm,ratio_2mm}]`、`note`。
**命中数 = `coincident_pairs` 条数**。三档距离 0.5 / 1 / 2 mm 都给，便于看重合的紧密程度。
可用 `coincident_ratio` / `coincident_grid_mm` / `coincident_near_mm` / `coincident_max_pairs`（默认 400，
超出记 `truncated=true`）/ `coincident_exclude_regex` 调。

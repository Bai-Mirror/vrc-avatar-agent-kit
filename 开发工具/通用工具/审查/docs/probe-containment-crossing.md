# 探针 containment 命中数口径 · 探针 range <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §3.2.3 后半 / §3.2.4。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[探针 containment（包含率）](probe-containment.md) · 下一页：[探针 poke（静态穿出斑块）· 判据、请求与输出](probe-poke.md) <!-- nav -->

**命中数 = 每个部位里 `crossing_edges ≥ min_crossings` 且 `crossing_ratio ≥ min_crossing_ratio` 的 `flagged`
部位条数**（`flag_basis` 写 `crossing` / `crossing_below_threshold` / `no_crossing`）。旧口径的参考值仍可看：
工程A MMN 鞋脚趾 `inside_ratio` 2%（缺陷）→ 100%（修后），脚掌 85–87%（鞋口以上脚踝在外，正常）。
可用 `containment_pairs`（`[{garment, body?, region?}]`，`region` 可写 `foot`/`hand` 或具体 `LeftToes` 等
`HumanBodyBones` 名；不写 `region` 时按该渲染器 GameObject 名推断）、`containment_min_crossings`、
`containment_min_crossing_ratio`、`containment_min_ratio`（仅参考字段用）、
`containment_min_region_verts`、`containment_layer`（默认 30）、
`containment_max_iter`、`containment_ray_budget`（默认 3,000,000，超出记 `truncated=true`）调。
代价：包含率仍是「一个部位几百到几千个顶点 × 6 方向 × 每方向最多 30 射线」，穿越计数再叠加
「每区域约几千条边 × 2 次」，是两支里最重的探针。
自动配对是**名字启发式**：若某个配饰自己的 GameObject 名就含独立的鞋/靴/手套 token（如 `PixelBoot`），仍会被
配上；要排除就用显式 `containment_pairs`。

token 匹配逻辑有离线验证（不启动 Unity）：把 `AuditProbes.cs` 编进 `audit_T.dll`，用 mono 反射小测
（`_长程任务_20260918/派工/tmp/t_token_test.cs`）跑 13 项 `ALL PASS`——`windowA`/`final-window` 不命中，
`shoes`/`Shoes`/`(B)Boots`/`loafer` 命中脚，`Gloves` 命中手且不命中脚，`鞋`/`手袋` 命中，`PixelBoot`
因驼峰切出 `boot` 而命中（已在上面写明这是启发式的已知代价）。

#### 3.2.4 `range`——形态键权重越界

VRChat 客户端会把形态键权重钳到 0–100，编辑器预览不钳，于是「编辑器里看着对、上传后不对」。
遍历可见 SMR 的非零形态键（`|w| > blendshape_epsilon`），列出 `w < 0` 或 `w > 100` 的项。
`probes.range` 字段：`blendshape_epsilon`、`out_of_range[{renderer,shape,weight}]`、`hits`、`note`。
**命中数 = `out_of_range` 条数**。

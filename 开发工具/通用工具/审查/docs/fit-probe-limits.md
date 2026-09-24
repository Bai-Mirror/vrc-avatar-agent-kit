# T2 贴合探针 · 已知局限与首跑核对 <!-- nav -->

> 旧称：T2（原 `审查/README_T2.md`） §10。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T2 贴合探针 · 自检 C 与 v3 回归清单](fit-probe-selfcheck-2.md) <!-- nav -->

## 10. 已知局限 / Claude 编译与首跑重点核对

**不开 Unity 无法验证、需要首跑确认的：**

1. **`BakeMesh(mesh, true)` + `localToWorldMatrix` 是否二次缩放**：对 `lossyScale != 1` 的身体/衣物，
   确认世界坐标正确（量一个已知尺寸的网格，或临时打印身体包围盒对角线，与编辑器里量到的对比）。
   依据见第 4 节第 3 条。
2. **`RaycastCommand.ScheduleBatch` 在编辑器 Play 模式下是否真的可用**：若抛异常，`ray_backend` 会变成
   `physics_raycast`（显著变慢），`warnings` 里有说明。功能仍正确。
3. **`queriesHitBackfaces` 与 `hit.normal` 的实际约定**：看输出 `calibration`。若
   `hit_normal_usable=false`，说明 Unity 会翻转背面法线，此时走三角形 winding 判据（已标定校正）。
4. **`GetBonesPerVertex/GetAllBoneWeights` 在未开 Read/Write 的身体网格上是否可取**：取不到会自动退
   `nearest_bone`，部位统计变粗（`warnings` 会写）。若所有工程都退化，需要改为在导入设置里给身体网格
   开 Read/Write 后再审查，并把这一步写进 SOP。
5. **接口耦合**：本文件按 `AuditIO.cs` 当前版本实现 `IAuditTool`。若工具 C 之后改了
   `IAuditTool` / `AuditContext` / `AuditJson` 的签名，本文件需要同步跟进（编译期就会报错，不会静默）。
6. **v2 身体碰撞体（layer 29）在 Play 下的烹饪与命中**：首跑确认 `build_body_collider` 耗时正常、
   `warnings` 没有「身体烘焙网格没有三角面」「排除被删除顶点后…」；并确认身体层没有头像自带碰撞体
   （有则 `warnings` 提示）。若身体碰撞体没建起来，`rejected_through_body` 会全 0，退回只靠
   `rejected_opposite_normal` 兜底（结果仍比 v1 好，但薄部位可能残留）。
7. **`RaycastCommand` 对 `distance=0` 的命令**：v2 对被排除顶点发了距离 0 的中性命令（只为占位、
   避免 NaN 进批处理）。若首跑在该构造上抛异常，`ray_backend` 会退 `physics_raycast`；此时把这些
   命令改成不提交（数组切片）即可，功能不受影响。
8. **v2 `body=auto` 的部位覆盖判据**：确认 `body_candidates` 里被选中的 `<body>` 的 `regions` 同时
   含脚与躯干部位；若 `region_bone_examples` 显示大量 `Other`，说明父链没上溯到人形骨骼（例如
   Animator 不是 Humanoid，或骨骼挂在头像根之外），此时应显式指定 `body`。
9. **v3 衣物蒙皮部位统计**：看每件衣物的 `region_source` / `coverage_regions`。若某件是
   `no_bones`（MeshRenderer）/`unreadable_weights`（网格未开 Read/Write）/`map_mismatch`，说明它**没有**
   应用范围过滤，其 `covered`/`pierced` 仍是旧口径。`coverage_regions` 与 §9.5 的肉眼判断是否一致
   （例如 `sailor` 不应含 `RightHand`）。
10. **v3 脚底厚度射线**：看 `feet[].thickness_p50_mm`/`thickness_count`。若 `thickness_count=0`，
    说明 `Physics.RaycastNonAlloc` 在该衣物上一条有效命中都没拿到（可能脚底顶点全在衣物上方/外侧），
    此时分类退回名称关键词，输出里 `class_source=name` 或 `default`。若鞋、袜都被判成同一类，
    先核对 `thickness_p50_mm` 是否合理，再考虑调 `sole_min_mm`。
11. **v3 `feet[]` 消费口径变化**：旧脚本若直接读 `feet[].signed_mm`，遇到 `class!=footwear` 的条目会
    取不到键——消费方要先按 `class` 分支（见 §5 注）。

**已声明的算法局限（设计文档也写了）：**

- 对非流形、双面或很薄的衣物网格，正/背面与「穿过」的判定有误差：**以正负样本对照后仍显著为准**，
  单个数值不当定论。
- `body=auto` v4 靠「名字候选过脚+躯干蒙皮权重关 → 退部位覆盖 + 顶点数最多」：全身服装 SMR 也可能合格，
  看 `body_candidates` 的 `regions`/`vertex_count` 核对，必要时用 `body` 显式指定。
- layer 29（身体）/ 30（衣物）若被头像自身占用会误命中，`warnings` 会提示；换层需同时改
  `AuditFitProbe.BodyLayer`/`TempLayer` 与 T3 使用的层（避免冲突）。
- v3 覆盖范围用的是**衣物顶点主骨骼**，不是「顶点是否真的被布料包住」：镂空、开襟、披挂类衣物
  （设计上包住某个部位但那里没有布料）仍可能被算成「覆盖该部位」，要靠 `covered=0` 或肉眼复核。
  反之，紧贴但不属于该部位的杂散权重（< `region_min_share`）会被忽略。
- v3 脚部按「每只脚 × 每件覆盖该脚的衣物」输出，穿多层（袜+鞋）时两层都在 `feet[]` 里，按 `class`
  区分；但「哪件是外层」不由本工具判断（看 `thickness_p50_mm` 或包裹方向）。
- v2 的 `rejected_through_body` 用「命中距离 < 衣物命中距离」判定，天然会把腋下/指缝这类
  身体先自遮挡的情况也否掉（覆盖面偏保守）；高覆盖率场景可结合 `rejected_*` 与 `markers` 复核。
- `zero_weight` 桶同时收「总权重为 0」和「离 Hips > 3 m」两种不可见顶点（字段名沿用任务书）。
  3 m 阈值只抓明显异常，正常身体顶点不会被误排。
- 非 Play 模式会临时新建 GameObject，Unity 可能把场景标脏（我们**不保存、不 MarkSceneDirty**）；
  正常入口 `RequiresPlayMode=true` 已避免这一点。

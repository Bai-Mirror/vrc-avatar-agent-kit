# T-05 部件盘点 · 同名键跟随 key_follow 与已知局限 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §11.3 / §11.4。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T-05 部件盘点 · 输出骨架](part-inventory-output.md) · 下一页：[T-12 构建期截获与零残留 · 原理与输出](build-capture.md) <!-- nav -->

### 11.3 同名键跟随 `key_follow`

> 触发：件（衣服/鞋/配饰）带着与身体**同名**的形态键，但没有 MA BlendshapeSync、没有自己的 clip 曲线、
> 也没有 MA ShapeChanger 驱动它；身体的键一动，件恒为固定值，就会穿模（工程E 的 Re-Poppin 胸型键、
> 鞋的 `Foot_heel_OFF` 都是这一类）。规程：`SOP/50_服装发型装配/胸型跟随_同名键无人同步.md`。

`key_follow` 只对**身体 SMR** 之外每个 SMR 求「件键名 ∩ 身体被写键」，命中且件上无写者 → `candidates`
（**只列不判对错**：固定值件可能是有意的，如 工程E 的 `(B)Cat`）。

- **身体识别**：与 T-10 poke / T2 `body=auto` 共用 `AuditBodyPick.FindBodySmr`（任务 AY）：先按已知身体名
  `Body_b` / `Body_base` / `Body`（大小写不敏感，覆盖 Kaguya/Rurune、Kipfel、Milfy）且**蒙皮权重同时覆盖
  脚与躯干**（各自份额 ≥ 0.1%）取顶点最多者；没有退回原几何启发（脚+躯干部位、顶点最多）。
  *为什么*：Kipfel 脸网格 `Body` 顶点比真身体 `Body_Base` 多，只按名字+顶点数会认错（AM 教训 1）。
- **身体被写键**：收敛三种来源——
  1. `blendShape.<键>` clip 曲线且 `path` = 身体（descriptor 的 base/special 动画层 + 头像下所有
     MA MergeAnimator，路径前缀按 Relative/Absolute 处理；BlendTree 子 motion 显式展开兜底）；
  2. 场景/预制体里 `ModularAvatarShapeChanger` 目标为身体（Set/Delete 都收）；
  3. **件用 MA BlendshapeSync 声明过的身体源键**（`ReferenceMesh` 指到身体、且身体网格确有该键）。
     第 3 条是刻意加的：有的身体键（如 Rurune 的 `Breast_Big_____胸_大(mizuki)`）没有任何 clip 驱动，
     但件把它当同步源，只有把它算进身体被写键，固定件 `(B)Cat` 才会作为候选被列出来复核。
- **件上的写者**：同物体 `ModularAvatarBlendshapeSync` 的 `Bindings[]`（`LocalBlendshape`，空则取
  `Blendshape`）绑定了该键；或某 clip 曲线 `path` = 该件、键 = 它；或 `ModularAvatarShapeChanger`
  目标为该件且写它。有写者 → 进 `synced`（带 `piece_writers`），无写者 → 进 `candidates`。
- **字段**：`body`（身体路径）、`body_written_keys[{key, writers[]}]`、`candidates[]` / `synced[]`
  （`renderer` / `key` / `piece_current_weight` / `body_writers[]` / `piece_writers[]`）、
  `candidates_by_class`（按键名粗分 `bust`=`breast|chest|胸|bust`、`foot`=`foot|heel|toe|足|ヒール`、
  其余 `other`）。
- **几何加权（任务 AY，B-补-07）**：每个 `candidates[]` 多一个 `geom` 对象（`synced[]` 无），**只加字段、
  不改原字段**，供 verdict 把「数值失配但几何不变」的候选降为 benign/advisory：
  - `body_key_disp_mm`：身体该键 0→100 时，**件覆盖区内**身体顶点的位移分布 `{p50,p95,max,count}`（mm，
    世界空间）。件覆盖区取该件 `covers`（主骨骼顶点占比 ≥2%）对应的身体主部位顶点；没有覆盖区/身体无该键则缺省。
  - `piece_key_disp_mm`：件自身该键 0→100 时的顶点位移分布 `{p50,p95,max,count}`（mm）。
  - `body_piece_dist_mm`：件每个顶点到**身体表面**（BVH 最近点）的距离分布，身体键分别在 0 与 100：
    `{at0:{p50,p95,max,count}, at100:{…}, p50_delta_mm}`。`at100` 与 `at0` 的 p50 差小 → 几何不变。
    顶点多于 2 万时等距抽样，`count` 是实际抽样数。
  - `available` / `body_delta_available` / `body_key` / `body_covered_verts` / `geometry_source`：可用性与上下文；
    身体快照失败时 `available=false` 并写 warning。
  - **快照口径（BF 返工）**：身体与件**统一用 `BakeMesh`**，带当前形态键权重与当前姿势，`geometry_source`
    写 `body=bake;piece=bake`；不再「网格可读就读 `sharedMesh`（bind pose、不带形态键）」，避免身体/件
    各走一条、空间不一致。多帧形态键取**最后一帧**（满权重帧），不是第 0 帧。
  - 判据：数值失配时看 `body_piece_dist_mm.p50_delta_mm` 与 `piece_key_disp_mm.max`，都 < 1 mm →
    `benign_geometry`；任一 ≥ 1 mm → `mismatch`；缺 `geom` → 维持原判并标 `no_geometry`。
    工程D乳贴修前 p50 5.74→14.95 mm 属于几何确实在动，判 mismatch；工程D外套 A `harness` p50 恒定则 benign
    （`对照:33-36`）。阈值 1 mm 由实测定（`key_follow_verdict.GEOM_BENIGN_MM`），留给人工复核。
- **只读**：与盘点其余部分一致，不 MarkSceneDirty、不改资产、不建临时物体。几何加权用的 BVH 是纯内存结构。

### 11.4 已知局限

- `closed` 只看网格自身拓扑，不判「是否包住脚」；鞋口/袜口都有边界环，靠 10% 阈值区分。要找「鞋 vs 袜」
  用 `shoe_like`（鞋底高差），两者都写出来，别互相替代。
- 网格未开 Read/Write 且 `BakeMesh` 也失败时，`boundary_edge_ratio`/`closed` 为 `null`、`sole_*` 为 `null`，
  不猜；权重退 `nearest_bone`（`region_source` 可见）。
- **MR 的部位/闭合度是近似**：`covers` 只按最近骨骼投顶点，不分蒙皮权重（本来就没有），部位边界比 SMR 粗；
  网格未开 Read/Write 时退 `nearest_bone_object`（一个物体只算一个部位），`boundary_edge_ratio`/`closed` 为
  `null`。MR 的 `sole_thickness_mm` 仅当它的近似部位含脚部才有值。
- **`part_like` 只看名字**：改物体名/加祖先名会改判定；它不替代人工核，`true` 里仍可能混进工具物（如未列入
  排除表的插件网格），`false` 里也可能误伤名字撞车的真件。
- `body_keys` 是**身体 SMR 网格**的全部键；身体识别错（`FindBodySmr` 走了脸网格）会写错键表。识别已按
  `AuditBodyPick`（名字候选 + 脚/躯干蒙皮权重）取，仍要核对 `body_path` 与 `body_key_count`；键表不含别件
  （服装/鞋）自己的键。名字兜底认不出的导入骨架仍落 `Other`，此时该件的 `covers`/鞋底可能不准。
- `switch` 的路径匹配是「avatar 根相对路径」与「Animator 根相对路径」精确匹配（不做模糊后缀）；
  嵌套 Animator（Animator 不在头像根）的 clip 路径若相对该子 Animator，会漏匹配。
- MA ObjectToggle 目标解析不到头像下时只记 warning、不进 `toggle_targets`；MenuItem 只按「同件或祖先」判控制。
- `key_follow` 的 `candidates` 含 inactive 隐藏件，且不判「件是否挡在身体外」；固定值件一律列出，看图/看权重再定。
  身体写者里的 `blendshape_sync` 是「件声明从身体读该键」，不是驱动曲线本身。`candidates[].geom` 的几何数据
  是编辑期当前权重/姿势下用 `BakeMesh` 算的（身体键 100 用当前快照 + 该键满档位移），与 Play 实测姿势仍可能有差；
  它只用于把「数值失配」分级，不替代 T1/T2 实测。
- 本文件只做离线 csc 编译；运行期（BakeMesh 坐标、MR 网格可读性、`animationClips` 覆盖、路径匹配）
  待 Claude 在 工程A 实测。

# T1/T3 已知局限 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §10。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[自检 3 · 运行期待验点（18–22）与明确没验证的](selfcheck-runtime-2.md) · 下一页：[T-05 部件盘点导出 AuditPartInventory · 范围与口径](part-inventory.md) <!-- nav -->

## 10. 已知局限

1. **T1 必须 Play 模式**。编辑模式下没有 AE 参数驱动，跑也没意义；请求里不加 `auto_play` 就直接写 error。
2. **参数联动依赖 GM 接管**。`driver=animator` 时 `VRC_AvatarParameterDriver` / `VRC_AnimatorLayerControl`
   都不执行，这份快照只能当「静态显隐/形态键」用，不能当「VRChat 里的真实组合」。
3. **Animator 退路很弱**。VRChat 工程的 `Animator` 通常没有 `runtimeAnimatorController`（动画层在
   `VRCAvatarDescriptor.baseAnimationLayers` 里），退路会大面积 `params_missing`。真要退路可用，
   得自己搭 PlayableGraph —— 本轮不做。
4. **AAP（曲线驱动参数）写不进去**：GM 的 `PlayableParam.SetValue` 遇到 `_isAap()` 直接 return
   （`Vrc3Param.cs:168/189`）。这类参数会表现为 `no_effect`，不是工具 bug，输出里能看出来但**不会**
   特别标注是 AAP，需要人工对一下 GM 界面。
5. **`pose` 只支持 `tpose` / `ikpose` / `idle`**；`walk` / `sit` / `crouch` / `arms_up` 需要动画剪辑，本轮未实现
   （请求里写了会记一条 warning 并忽略）。
6. **`no_effect_params` 不是单参数归因**（口径见 §4）。
7. **T3 判据依赖纯色背景**：背景色必须与头像颜色分得开（绿发 + `bg=[0,1,0]` 会把头发误判成「背后没东西」）。
   换 `bg` 或提高 `color_epsilon`。
8. **掩码层可能被占**：`mask_layer` 默认 31；工具会扫一遍场景里同层的其他渲染器并写 warning，但不会自动换层。
   同一 GameObject 上多个候选渲染器共享 layer，掩码会互相混入（也会 warning，那几条 `vanish_ratio` 不可信）。
9. **T3 关闭 MSAA**（`rt.antiAliasing=1`）以保证 A/C 能逐像素比；PNG 边缘会有锯齿，只作复核用，不作审美交付图。
10. **A 图渲一次给所有候选复用**：A 不依赖 R，逻辑上等价于任务书里「每个候选各自渲 A」；省 3 倍渲染量。
11. **同步渲染会卡帧**：一个视角要渲 `1 + 2×候选数` 张，候选多时单帧可能卡几百毫秒；整体仍分帧推进。
12. **编辑模式下瞬改 layer/enabled 可能留下场景 dirty 标记**（值已还原），跑完别顺手保存。
13. **Screen Space Overlay 的 UI 不会进 RT**（Unity 行为），世界空间 UI 会进；如需纯净画面请自行隐藏。
14. `HumanBodyBones` 解析不到的骨骼名会退回「按层级名字找」，再找不到才 warn + 跳过该 target。
15. **T1 结束不复位参数**（供 T3 使用；但若 GM 是 T1 临时建的，`Cleanup()` 销毁它时 `ModuleVrc3.ForgetAvatar`（`ModuleVrc3.cs:814-827`）会 `Rebind()` + 清参数，T3 拿不到那批状态，见 §3.1）；如果你需要一份「跑完回到干净状态」的行为，跑完后自己退出 Play。
16. **临时 GM 是 T1 专有**（任务 F）：场景原本没有 GM 时，Play 模式下 T1 建 `__AvatarAudit_GM` 接管、`Cleanup()` 销毁。所以看到 `driver=gesture_manager` 时要用 `gm_created_by_audit` 判断是场景自带的还是临时建的；T3 不建 GM，也复用不到 T1 的临时 GM。
17. **只复位「用户可控参数」，复位值取声明默认（任务 Q）**：表达参数里声明、且非 VRChat 内置的参数才会在状态间复位，值取 `VRCExpressionParameters.defaultValue`（读不到才退回 T1 启动实值并逐个 warning）。请求里出现、但不在表达参数里的参数不会自动复位——多状态串联时要么把它写进表达参数，要么每个状态都显式写。内置参数只在状态显式写时才被改。切换残留测试用 `"reset":"none"` 并显式列出序列（§3.0.3）。
18. **回调隔离有版本依赖（任务 G）**：`EditorApplication.playModeStateChanged` 不是字段式事件，本工具靠反射 `m_PlayModeStateChangedEvent` 取订阅者；Unity 改内部结构时隔离会降级为 warning（`isolated_callbacks.json` 为空/不全），不会让审查失败，但老探针可能照跑。
19. **volatile 探测只覆盖第一个状态（任务 G）**：易变形态键只按第 0 遍第一个状态的两次采样认定；若某个键只在别的状态/别的时刻才开始自动播放，仍会进 diff。必要时把 `settle_frames` 调大或换一个状态当探针基准。
20. **探针是附加信息、且只做了离线编译（任务 R；`containment` 任务 T/U 修订）**：不请求 `probes` 时输出与旧版逐字节一致；请求了但某个探针抛异常，只在该状态 `probes.<名>.error` 与 `warnings` 里留痕，不把整批判 error。四支探针的 Unity 运行期行为（`BakeMesh` 世界坐标、射线奇偶、最近点哈希、`sharedMesh` 权重部位映射）尚未实测，按 §9.2 的 18 复跑。
21. **`containment` 对非流形网格不可靠（任务 R）**：迭代射线奇偶假设网格是**闭合、可定向**的曲面。边被 >2 个三角面共享、网格自交、法线翻转、同一位置有内外两层壳时，奇偶会被破坏。输出里的 `nonmanifold_edge_ratio` 就是给这个看的——偏高时 `inside_ratio` 只能当参考。
22. **开口件的包含率天然偏低（任务 R；任务 U 后已不用于判据）**：凉鞋、露趾鞋、无指手套等开口件即使尺寸正确，脚趾/指尖也会落在「外面」，`inside_ratio` 低不代表缺陷。任务 U 起判据改用 `crossing_edges`（身体表面与面料相交）：身体从开口穿过、不与面料相交，所以开口件穿越数接近 0；`open_mesh_suspect`（边界边占比）仍输出，作「是不是开口件」的提示。
23. **蒙皮缩放与不可读网格（任务 R）**：世界坐标换算沿用 T2 的口径——`BakeMesh(mesh, true)` 先补偿 SMR 自身缩放，再乘 `localToWorldMatrix`；负缩放/非均匀缩放的渲染器可能让结果偏。`coincident` 只比 `SkinnedMeshRenderer`；`containment` 的衣物若是 `MeshRenderer` 且网格没开 Read/Write，`sharedMesh.vertices` 会抛异常，探针记 warning 后跳过该件。`containment` 是最重的探针（顶点×6 方向×最多 30 射线，再加每区域几千条边×2 次线段射线），大工程先只对可疑部位开 `containment_pairs`。
24. **`containment` 的配对是名字启发式（任务 T）**：只看渲染器 GameObject 名。若某配饰自己的名字就含独立 token（`PixelBoot` 的驼峰会切出 `boot`），仍会被当鞋/靴配上；用显式 `containment_pairs` 排除。反过来，真鞋若渲染器名字不含任何关键词会漏配。
25. **区域总量只在能读到权重时与状态无关（任务 T）**：`body_region_verts_total` 依赖 `sharedMesh` 的蒙皮权重；若身体网格未开 Read/Write 或没骨骼，探针退 `NearestBoneIndices`（`body_region_source=nearest_bone` + warning），部位会随姿势漂移、总量不再恒定，此时只能当参考。
26. **"删除"顶点进 excluded、不进穿越计数（任务 T/U）**：被 MA ShapeChanger 用 NaNimation 删掉的脚趾/脚掌顶点在 `excluded.deleted_nanimated` 里，`verts` 与 `edges` 都不含它们。所以「袜开时脚趾 `flagged` 为 0」不代表包住了，只代表该部位几何已被删；测包含 / 穿越都要用几何存在的状态（工程A 用 `A2_Sok=0`）。
27. **穿越判据的阈值取舍（任务 U）**：`flagged = crossing_edges ≥ 20 且 crossing_ratio ≥ 0.01`。20 条挡零散/单三角形级擦边（数值共面、一个顶点压线约产生 2–4 条），1% 挡大区域里绝对数被放大（脚部 3000–6000 条边）。贴身件（袜/紧身衣）擦边会有个位数到十几条穿越边；若某单真正贴身件被误报，先看 `max_crossing_depth_mm` 是不是只有零点几毫米、`crossing_midpoint_local` 是否落在预期部位，再按工程调高 `containment_min_crossings`。`containment_ray_budget` 用尽时按排序后的区域顺序截断，`truncated=true`，此时计数不完整、不能当负样本。
28. **`pre_probe_blendshapes` 只借探针的读数（任务 U）**：形态键在快照**之后**设、探针**之后**还原，所以 `state_<id>.json.blendshapes` 仍是原始值，`pre_probe_blendshapes_applied` 才记覆盖；没有 `probes` 时它不生效（warning）。渲染器多个子串命中时取路径序第一个、形态键 AAO 分片全设，都是为了可复现。T3 的 `only_renderers`/`hide_renderers` 同理：在 `collectCandidates` 前设、`Cleanup` 还原，所以隐藏件不进透明候选；匹配是子串，写 `Glove` 也会命中 `GloveBox`，核对 `shots.json.view_filter.only_matched`。

---

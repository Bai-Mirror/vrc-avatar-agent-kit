# 自检 3 · 运行期待验点（18–22）与明确没验证的 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §9.2 后半 / §9.3。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[自检 3 · 运行期待验点（1–17）](selfcheck-runtime.md) · 下一页：[T1/T3 已知局限](known-limits.md) <!-- nav -->

| # | 待验点 | 怎么验 | 失败长什么样 |
|---|---|---|---|
| 18 | 四支纯数据探针（任务 R；`containment` 任务 T/U 修订） | 用 §3.2.5 的 工程A 两组状态复跑：修复前 `containment` 脚趾 `inside_ratio` 个位数、`grab_chain` 抓取点 2450；修复后脚趾 ≥95%、抓取点 3050。负对照：不请求 `probes` 时 `state_*.json` 里没有 `probes` 字段、`states.json.probes_requested=[]`。任务 T 追加：自动配对不再出现 `windowA`…`windowE`/`final-window`；`by_region` 能分开 `LeftFoot`/`LeftToes` 且 `body_region_verts_total` 在 83 状态恒定；`A2_Sok=1` 时脚趾进 `excluded.deleted_nanimated`。任务 U 追加：`flagged` 改用 `crossing_edges ≥ 20 && crossing_ratio ≥ 0.01`，正样本见 §3.2.5 第 3 条（`pre_probe_blendshapes` 把 `foot_heel_OFF` 设 0 → 脚趾 `crossing_edges` 抬高、`flagged=true`，去掉覆盖回落），`pre_probe_blendshapes_applied` 记了实际命中的 `AAO_Merged_*` 名；开口鞋 `crossing_edges` 应接近 0。T3 侧：`only_renderers=["Body","Glove"]` 渲出的图里没有裙子，`shots.json.view_filter.only_matched` 含两个串，`transparency.json.candidates` 里不再有被隐藏的渲染器 | `grab_chain` 全 0 → 正则没命中（对着色器名）、`grab_shader_regex` 覆盖；`containment` 全 0 或 body 识别错 → 检查 `body_source`、`containment_layer` 30 是否被头像自带碰撞体占用（有 warning）、`by_region` 部位名是否符合预期；`crossing_edges` 为 0 但人工看图有穿模 → 看该状态是否 `A2_Sok=1`（脚趾已被删除、没有几何可穿）或 `containment_ray_budget` 用尽（`truncated=true`）；`crossing_edges` 偏高但人工看图没穿模 → 看 `max_crossing_depth_mm` 是不是只有零点几毫米的贴身擦边、`region` 是不是紧身袜；`coincident` 把身体也算进去 → 自动识别失败退 `fallback_largest`（有 warning）。`body_region_verts_total` 仍随状态变 → 看 `body_region_source` 是否 `nearest_bone`（身体网格未开 Read/Write） |
| 19 | 版本戳能拒跑（任务 AN＝T-13） | `sync_audit.py` 同步后发正常请求：`states.json.tool_version.match=true`、`version_file_hash` 与 `Assets/AvatarAudit/VERSION` 的 `hash` 逐字节相同。再故意手改 `Assets/AvatarAudit/Editor/AuditIO.cs` 一个字节重发 → `status=error`、`message` 含「版本戳不一致，拒跑」，场景无 Temp/无 dirty；改回后恢复。`"version_check": false` 应能跳过并写出 `match=false` | 同步后仍 `match=false` → 比对 `deployed_files` 是否与 VERSION 的 `files` 一致（多半是 `.meta`/`VERSION` 的排除口径或 SYNC 源根不同）；拒跑时若场景被改脏 → 说明版本检查没排在 `Begin` 最前 |
| 20 | 状态回读断言 83 状态全过 + 错参数被抓（任务 AN＝T-13） | 用 §3.2.5 的 83 态请求（`A2_*` 那批）：`states.json.readback_failed=false`、`readback_failures=[]`、`status=done`；每个 `state_<id>.json` 有 `readback.params[*].ok=true` 与 `id_canonical`；`gear_slots.A2_Outfit.n=14`。再复制一份请求、把某状态的一个参数值改错（如 `A2_Sok` 0→0.5）→ 该状态 `readback_failed=true`、整批 `status=aborted`、`abort_reason` 指到该参数；把 `state_*.json` 留着但结论作废 | 83 态里有个别 `ok=false` → 看 `actual`/`delta`/`source`：GM 对超范围值 clamp（请求值越界）属于预期的「不一致作废」；`source=missing` 是参数不在 GM/Animator；`id_canonical` 出现 `@x/n` 但档位明显不对 → 看 `gear_slots` 的 `source` 是 `request` 还是 `inferred_from_batch` |
| 21 | 哨兵正/负样本（任务 AN＝T-13） | 正样本 `sentinels.positive=[{renderer:"Body",shape:"sailor_shrink",weight:0}]`：第一个状态上 `observed_weight=0`、`pass=true`；负样本 `sentinels.negative=[{renderer:"outer",hide:true}]`：`visible_after_hide=false`、`pass=true`；`states.json.sentinel_failed=false`、`status=done`。再故意把正样本改成不存在的键名 → `pass=false`、`status=aborted`、`abort_reason` 写「哨兵未过」；跑完场景里 `outer` 的 activeSelf/enabled 必须还原成跑之前的值 | 正样本 `observed_weight` 读回不对 → 该 `shape` 是否靠 AAO 改名匹配（看 `matched_indices`）；负样本 `pass=false` → 看 `renderers[].visible_after_hide`，多半是模糊匹配命中了父物体（`renderer` 写具体路径）；哨兵跑完后部件没还原 → 查 `RunPositiveSentinel`/`RunNegativeSentinel` 的 finally 是否执行（看 Console 有无异常） |
| 22 | `keys_all` 的 `source_name` 追溯与 V3/V4（任务 AN＝T-13） | 83 态任一份里每个 SMR 都有 `keys_all[path]`，`keys` 含 0 权重键且 `index`/`name`/`weight` 与网格一致；AAO 合并件 `source_name` 至少能给出原名或 `null`（配 `source_name_origin`）；`visibility[path].V3_alpha_mask` 对已知被 `_AlphaMask_ST` 遮掉的 bag 件应为 `hidden`（对照 `materials[].v3.reason`）、普通 lilToon 为 `visible`；SMR 的 `V4_kept_ratio` 非 null（网格可读时） | `keys_all` 缺某个 SMR → 看该 SMR `sharedMesh` 是否为空；`source_name` 普遍 `unresolved` → 记录当时的 `mesh`/`built_path` 形态再补启发式（最终应由 T-12 `mapping.json` 接管）；V3 全 `unknown` → 着色器名不含 `lilToon` 或取属性失败（看 `v3.reason`）；V4 全 `null` → 网格未开 Read/Write |

### 9.3 我明确**没有**验证的（别当成已验证）

- 任何 Play 模式下的实际行为（本轮禁止启动 Unity）；
- 任务 G 新增的三件事（默认值取启动值 / 健全性检查 / volatile 探测 / 回调隔离）都只做了离线编译，
  没有在 Unity 里跑过：`EditorApplication` 的字段名与事件结构是按 2022.3.22f1 的 `UnityEditor.dll` 反汇编核对
  （§7），换 Unity 版本或换工程要按 §9.2 的 14–16 重新验。任务 Q 把「默认值取启动值」改成「取表达参数声明
  `defaultValue`」，只做了离线编译；`defaultValue` 的反射读取与跨会话不漂移需按 §9.2 的 3 在 Unity 里实测
  （尤其确认 `reset_values_source="declared_default"`、`reset_fallback_params=[]`）。
- GM 3.9.9 之外的版本（README 里的行号都按 3.9.9 核对；换版本要重新 grep）；
- 渲染后端（OpenGL 核显 / Vulkan 独显）对像素的影响 —— 任务 B 的结论还没进来，
  跨 run 比 `vanish_ratio` 数值前要确认两次用的是同一后端；
- 工程实际是 Linear 还是 Gamma 色彩空间下的读回值（逻辑上自洽，但没实测）；
- 任务 I 的逐槽掩码、C0/C1 透光率、`model_error_p50`、ID 渲染 / `vanished_owners` 同样只做了离线编译，
  没有在 Unity 里跑过；`Shader.Find("Hidden/AvatarAudit/*")` 能否在 `Assets/Editor/` 下命中、Linear RT 的
  `SetVector` 写入是否确实按字节读回，都要按 §9.2 的 10 / 17 实测确认。
- 任务 R 的四支探针同样只做了离线编译（`compile_audit_R.sh`，6 个 `.cs` 0 error / 0 warning），
  **没有在 Unity 里跑过**：`BakeMesh` 的世界坐标换算、`Physics.queriesHitBackfaces` + 临时 MeshCollider
  的六方向迭代射线、2 mm 网格最近点哈希、`renderQueue` 读取，都要按 §9.2 的 18 在 工程A 上复跑确认
  （对照 §3.2.5 的历史数值）。
- 任务 T 对 `containment` 的三处修订（GameObject 名 token 配对、`sharedMesh` 权重分 Foot/Toes、`body_region_verts_total`
  + `excluded`、`outside_centroid_local`/`outside_extent`）**同样只做了离线编译**（`compile_audit_T.sh`，6 个 `.cs`
  0 error / 0 warning）。token 配对逻辑用反射小测在 mono 下验证过（13 项 `ALL PASS`）；但「身体网格的
  `sharedMesh` 权重能不能把脚趾分出来」「`NaNimation` 删除顶点在运行期是不是真的非有限坐标或带 `NaNimat` 骨名」
  「锚骨局部坐标是否可用」都只能在 工程A 里按 §9.2 的 18 实测确认。
- 任务 AN（T-13 T1 v4）的**纯逻辑与格式**在离线自检里全过（40 PASS / 0 FAIL：V3 规则表、`SlotOf` / `InferGearSlotCount`
  / `CanonicalTuple` / `ReadbackMatch`、`GuessSourceName`、版本 hash 确定性、83 态请求重放），但以下**只能在 Unity/Play 验**：
  部署树 hash 与 `VERSION.hash` 在真实工程里是否逐字节相等（`HashEntries` 与 `sync_audit.py` 是两套实现，
  靠同法对齐）、`Assembly.Location` 拿到的 dll mtime 是否是编译时间、`keys_all` 在 AAO 合并后 166 个 SMR 上的
  体积与耗时、`mesh.isReadable` 在工程里的真实取值（决定 V4 是否为 null）、V3 属性读取对真实 lilToon 变体是否命中、
  哨兵 hide 的还原与 GM 的相互影响、83 态回读断言在 GM clamp / 精度下是否真的全过。按 §9.2 的 19–22 验。

---

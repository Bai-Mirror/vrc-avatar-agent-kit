# T1 输出格式 · `state_<id>.json` <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §4。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[R9 脚鞋选型 · 教训、鞋垫面口径与验收](foot-shoe-candidates-metrics.md) · 下一页：[T1 输出格式 · states.json 汇总](state-driver-states-json.md) <!-- nav -->

## 4. T1 输出格式

### `state_<id>.json`（每个状态一份；`repeat_check` 第二遍写 `state_<id>.repeat.json`）

```json
{
  "id": "headacc_on",
  "driver": "gesture_manager",
  "params_applied": { "A2_HeadAcc": 1 },
  "param_sources": { "A2_HeadAcc": "gesture_manager" },
  "missing_params": [],
  "warnings": [],
  "reset_values_source": "declared_default",
  "reset_count": 318,
  "history": ["default"],
  "renderers": [
    { "path": "Body", "key": "Body", "type": "SkinnedMeshRenderer",
      "active_in_hierarchy": true, "enabled": true, "visible": true,
      "materials": [ { "slot": 0, "null": false, "name": "Body",
                       "shader": "lilToon", "render_queue": 2000,
                       "v3": { "value": "visible", "hidden": false,
                               "reason": "lilToon 规则表内未命中任何不可见条件" } } ] }
  ],
  "blendshapes": { "Body": { "Eye_Blink": 0.35 } },
  "keys_all": {
    "Body": { "built_name": "Body", "built_path": "Body", "mesh": "Body",
              "source_name": "Body", "source_name_origin": "mesh_name_plain", "blendshape_count": 2,
              "keys": [ { "index": 0, "name": "Eye_Blink", "weight": 0.35 },
                        { "index": 1, "name": "HeadAcc", "weight": 1 } ],
              "v4": { "vertex_count": 12000, "buckets": { "non_finite": 0, "nanimated": 0, "zero_weight": 0 },
                      "excluded_total": 0, "kept": 12000, "kept_ratio": 1,
                      "source": "bind_pose_bone_weights",
                      "note": "用绑定姿态顶点 + 蒙皮主骨骼判三桶；未逐状态 BakeMesh，姿势引起的删除差异需 T-14/T2 复核" } }
  },
  "visibility": {
    "Body": { "V1_active_in_hierarchy": true, "V2_enabled": true, "visible": true,
              "V3_alpha_mask": "visible", "V3_hidden": false,
              "V4_kept_ratio": 1, "V4_buckets": { "non_finite": 0, "nanimated": 0, "zero_weight": 0 } }
  },
  "readback": {
    "params": { "A2_HeadAcc": { "requested": 1, "actual": 1, "delta": 0, "matched_requested": true,
                                "overridden": false, "ok": true,
                                "source": "gesture_manager", "gear_n": 2, "gear_slot": 1 } },
    "visibility": {},
    "id_canonical": "A2_HeadAcc@1/2",
    "ok": true
  },
  "readback_failed": false,
  "overridden": [],
  "id_canonical": "A2_HeadAcc@1/2",
  "bones_world": { "Hips": [0, 0.9, 0], "Head": [0, 1.5, 0.02] },
  "bones_missing": [],
  "avatar_position": [0, 0, 0],
  "avatar_rotation_euler": [0, 180, 0],
  "sanity_failed": false,
  "sanity_reasons": [],
  "probes": {
    "grab_chain": { "grab_point_queue": 3050, "hidden_materials": [], "grab_point_lt_3000": false, "hits": 0 },
    "range": { "out_of_range": [], "hits": 0 }
  }
}
```

- **`keys_all`（T-13 新增）**：构建后**每个 SMR** 的全部形态键（含 0），键与 `renderers` / `blendshapes`
  同口径（SMR 路径，重名补 `#2`）。每项 `{built_name, built_path, mesh, source_name, source_name_origin,
  blendshape_count, keys:[{index,name,weight}], v4}`。`source_name` 是**构建前**的物体名/路径尽力追溯：
  `AAO_Merged_<原名>_<n>` 网格名 → 原名；否则普通网格名；再否则路径里带 `$` 的段的前缀（AAO 合并命名
  `<原名>$<网格名>$<序号>`）；再否则未改名物体名；追不到写 `null` 且 `source_name_origin="unresolved"`
  （宁缺勿猜）。`source_name_origin` 取值：`mesh_name_aao_merged` / `mesh_name_plain` / `path_dollar_prefix`
  / `object_name_assumed_unchanged` / `unresolved`。给 T-14 / AM 做「源名 ↔ 构建后名」映射用。
- **`visibility`（T-13 新增）**：每个渲染器的可见性四分量。`V1_active_in_hierarchy` / `V2_enabled` /
  `visible` 与 `renderers` 同口径；`V3_alpha_mask` 为 `visible` / `hidden` / `unknown`（着色器规则表见下），
  `V3_hidden` 是它的布尔投影（unknown 写 `null`）；`V4_kept_ratio` / `V4_buckets` 只对 SMR 有（值同 `keys_all[].v4`）。
- **V3 着色器规则表（只覆盖 lilToon 的「整块不可见」）**：`_Cutoff ≥ 1` → hidden；`_Color.a ≈ 0` → hidden；
  `_AlphaMaskMode ≠ 0` 且 `_AlphaMask_ST` 的 scale+offset 把采样 UV 整段推出 `[0,1]` → hidden；
  mask 开但没推出 UV → **unknown**（是否整块不可见取决于遮罩贴图内容，规则表判不了）；非 lilToon → unknown。
  每个材质槽的结论与 reason 直接写在 `renderers[].materials[].v3`；部件级 `V3_alpha_mask` 是逐槽聚合
  （有 visible → visible，全 hidden → hidden，否则 unknown）。
- **V4（烘焙排除桶比例 / 顶点保留率）**：`kept_ratio = (总数 − 三桶)/总数`，三桶 = `non_finite`（绑定姿态
  顶点坐标 NaN/Inf）、`nanimated`（主蒙皮骨骼沿父链含 `NaNimat`，MA ShapeChanger 的 Delete）、`zero_weight`
  （蒙皮权重和为 0），优先级 non_finite > nanimated > zero_weight（与探针口径一致）。**口径说明**：用绑定姿态
  + 骨架结构静态判定（同一 mesh 每次运行只算一次），**没有逐状态 BakeMesh**；网格未开 Read/Write 时
  `kept_ratio=null`、`source="mesh_not_readable"`（判不了不猜）。Delete 型 ShapeChanger 只能从 V4 看出来
  （T1 权重看不到 Delete）。
- **`readback`（T-13 新增 / 任务 BJ 扩展）**：`params` 每项 `{requested, actual, delta, matched_requested, overridden, ok,
  source, gear_n?, gear_slot?, override_source?, override_expected?}`；`visibility` 是期望集合的比对结果；
  `id_canonical` 与实际值规范元组。`readback_failed=true` 时整批 aborted。被 `expect_override` 或驱动器 Set
  合法改写放行的参数，`overridden=true`、`ok=true`，并汇总到顶层 `overridden: [参数名…]`（见 §3.3）。
- **`history`（T-13 新增）**：请求里排在本状态之前的状态 id 列表（序列切换上下文）。
- 只有请求里 `probes` 非空时才有 `probes` 字段；未请求探针时输出与旧版逐字节一致（不影响既有 diff/确定性比对）。
- `pre_probe_blendshapes_applied`（任务 U）只在请求了 `pre_probe_blendshapes` 且至少设上一项时出现，
  每项：`{requested_renderer, renderer, renderer_name, requested_shape, shape, weight, old_weight}`。
  `renderer` / `shape` 是实际命中的路径与网格里的真名（AAO 改名的分片可能多项），`old_weight` 是覆盖前的值。
  配不上的项不在这里，而是在 `warnings` 里逐条写明。
- `probes` 的键就是请求里列出的探针名，值是该探针的输出对象，格式见 §3.2。请求了但执行失败时该键下是
  `{"error": "..."}`，同时在 `warnings` 里留一条。
- `visible = activeInHierarchy && enabled`（审查口径）；同时保留两个分量便于定位是哪种不可见。
- `blendshapes` 只记 `|权重| > blendshape_epsilon`（默认 1e-4）的键——**为什么不到 0 为止**：
  动画曲线停止后常残留 1e-6 级浮点噪声，逐位非零会让 diff 全是噪声。
- `path` 是相对头像根的层级路径，根上的渲染器记 `.`；同名同路径（一个物体挂两个 Renderer）时补 `#2`。

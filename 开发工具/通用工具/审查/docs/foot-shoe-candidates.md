# R9 脚鞋选型 candidates · 请求、执行与输出 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §3.4 前段。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T1 · 版本戳、状态回读断言、档位槽号、哨兵、sequence/history](state-driver-readback.md) · 下一页：[R9 脚鞋选型 · 新增字段（CS / D2 / CW）](foot-shoe-candidates-fields.md) <!-- nav -->

### 3.4 R9 脚鞋选型 `candidates`（任务 BJ，B-T08a）

**为什么**：脚型键只挂在一件（袜）而菜单能单独开关另一件（鞋）时，光脚穿鞋/关袜穿鞋会把脚放回高跟姿态、
脚趾顶穿鞋头（MMN 实例；穿越计数在这类样本上会报 0 条，F26/B3）。所以 R9 不按穿越计数排序，而是对每个
候选键值施加后跑 **T-28a 静态穿出斑块**，按斑块面积/深度排序，供用户/声明草案挑脚型键。

**请求**（顶层 `candidates` 数组，与 `probes`/`pre_probe_blendshapes` 独立；缺省不跑）：

```json
{
  "tool": "state", "avatar": "<头像根名>", "out": "<绝对目录>",
  "candidates_reference": true,
  "candidates_zero": ["Foot_heel_OFF_____足_ヒールオフ", "Toe_heels"],
  "candidates": [
    { "id": "none", "part": "MMN_Shoes", "mesh": "Body_b", "garment": "_Outfit/Outfit_MMN_黑/Shoes",
      "body": "Body_b", "covers": ["LeftFoot","RightFoot","LeftToes","RightToes"], "keys": {} },
    { "id": "Foot_heel_OFF=100", "part": "MMN_Shoes", "mesh": "Body_b", "garment": "_Outfit/Outfit_MMN_黑/Shoes",
      "body": "Body_b", "covers": ["LeftFoot","RightFoot","LeftToes","RightToes"],
      "keys": { "Foot_heel_OFF_____足_ヒールオフ": 100 } },
    { "id": "shoe_only_no_zero", "part": "MMN_Shoes", "mesh": "Body_b", "garment": "_Outfit/Outfit_MMN_黑/Shoes",
      "zero_keys": [], "keys": { "Foot_heel_OFF_____足_ヒールオフ": 100 } }
  ]
}
```

| 字段 | 默认 | 说明 |
|---|---|---|
| `id` | 由 `keys` 拼（空 keys → `none`） | 候选标签，进排序表 `candidate` 字段 |
| `part` | `part<序号>` | 分组名 / 输出文件名 `r9_<part>.json`（文件名经 `SafeFileName` 清洗） |
| `mesh` | — | **形态键施加目标**（渲染器名/层级路径/叶子名，匹配规则同 `pre_probe_blendshapes`）；`garment` 与 `mesh` 至少要有一个 |
| `garment` | 同 `mesh` | **poke 配对衣物**（鞋/袜）；`mesh`=身体、`garment`=鞋是常见组合 |
| `body` | 请求顶层 `body` / 自动 | 身体网格；**建议显式写**，保证施加键的身体与 poke 量的身体是同一个（`PickBodyPath` 读的是顶层 `body`，不是 `poke_body`） |
| `covers` | 沿用请求 `poke_covers` | poke 覆盖部位；不写又没请求级 covers 时退回关键词配对（`pair_confidence=low`） |
| `states` | 全部状态 | 只在这些状态 id 上跑该候选（工程B 6 个有鞋档可各写一份或共用） |
| `keys` | 必填（可空对象） | `{形态键名: 权重}`；顺序无关，按名排序后逐个施加 |
| `zero_keys` | 继承 `candidates_zero` | 候选级清零域，覆盖请求级；写 `[]` = 该候选不清零。见 `candidates_zero` |
| `hard` | 省略 | `{max_total_patch_area_cm2?, min_opening_verts?}`：请求显式给的硬约束，不过则该行 `hard_ok=false` 排最后 |
| `candidates_reference` | `true` | 是否内嵌同配对的 `containment` 参考列（穿越/包含率，只写表不排序） |

**执行语义**：每个状态快照与探针之后，对每个候选：先把清零域（`zero_keys` 覆盖 `candidates_zero`）里
在该候选 `mesh` 上匹配到的每个键写 0（同名多片全写、旧值入 `zero_applied`、还原栈一起还原），
再按 `keys` 设候选自己的键（同名后写覆盖）→ 读回写进 `applied_readback` → 用该候选的
`garment`/`covers`/`body` 跑一次 `AuditProbes.RunPoke`（去掉请求里的剂量/perturb/hide，强制 `reference`）
→ `finally` 还原清零域与候选键写过的全部形态键。清零域里没匹配到的键写进 `zero_missing`，**不算 hard 失败**。
单项失败只记 warning，不改快照。

**输出 `<out>/r9_<part>.json`**：
```json
{ "tool": "r9", "part": "MMN_Shoes", "file": "r9_MMN_Shoes.json",
  "sort_rule": "…", "crossing_counts_used_in_sort": false, "reference_enabled": true,
  "zero_rule": "…", "not_implemented": { "stringing": "not_implemented", "stringing_definition": "…", "category_constraint": "not_implemented" },
  "warnings": ["状态 'MMN_all'：候选 none、Foot_heel_OFF=100 的度量完全一致（…），多半是没清零或键没写进去，推荐不可信。"],
  "states": [ { "state": "MMN_all", "candidate_count": 2, "low_confidence": false,
    "top2_gap_ratio": 1.0, "state_indistinguishable": false, "recommended": "Foot_heel_OFF=100",
    "rows": [ { "candidate": "Foot_heel_OFF=100", "rank": 1, "hard_ok": true, "hard_reasons": [],
      "keys": {...}, "zero_applied": { "Foot_heel_OFF_...": 100 }, "applied_readback": { "Foot_heel_OFF_...": 100 },
      "zero_missing": [], "garment": "…/Shoes", "pair_confidence": "high",
      "patch_count": 0, "total_patch_area_cm2": 0, "max_patch_area_cm2": 0, "max_depth_mm": 0,
      "d_v_p50_mm": -9.5,
      "sd_p05_mm": 0.2, "sd_p50_mm": 0.4, "sd_p95_mm": 1.1, "sd_vert_count": 480, "sd_foot_verts": 812,
      "si_p05_mm": -1.2, "si_p50_mm": 0.35, "si_p95_mm": 2.0, "si_vert_count": 480, "insole_faces": 96,
      "tilt_deg": 1.8, "foot_plane_tilt_deg": 2.1, "insole_plane_tilt_deg": 0.6,
      "heel_gap_p50_mm": 0.3, "heel_vert_count": 96, "heel_gap_sole_p50_mm": 11.0,
      "opening_verts": 12, "opening_deep_verts": 0, "truncated": false,
      "by_sub_part": [...], "reference": {...}, "body_excluded": {...} } ] } ],
  "recommended": { "MMN_all": "Foot_heel_OFF=100" } }
```
`rows` 的顺序 = 排名：**先硬约束**（`keys` 全解析、poke 无 `error`/`truncated`、请求 `hard` 阈值），
通过的按 **`total_patch_area_cm2` ↑ → `max_depth_mm` ↑ → `|si_p50_mm|` ↑ → si 陷入量 `max(0,-si_p05_mm)` ↑
→ `tilt_deg` ↑ → `|sd_p50_mm|` ↑ → `heel_gap_p50_mm` ↑ → `|d_v_p50_mm|` ↑** 排序
（↑ = 升序，值越小越靠前）；不过/出错的排最后且 `rank=0`。
同一状态前两名**总面积**差 <10% 时该状态 `low_confidence=true`（`top2_gap_ratio` 记的是面积差，不含新键）。
**任务 CW（2026-09-20）：该状态 `low_confidence=true`，或 `top2_gap_ratio=0`，或
`state_indistinguishable=true` 时，每行的 `patch_count / total_patch_area_cm2 / max_patch_area_cm2 /
max_depth_mm` 一律输出 `null`**（内部排序仍用原值），行加 `patch_verdict:"undecidable"`，状态加
`patch_columns_suppressed:true` 与中文 `patch_columns_suppressed_reason`。
理由：这三个条件下斑块度量区分不出候选，读到 0 会被误当成「无穿出」（工程B第 5 档 `none` 假阴性的直接教训）；
要看几何请查该行 `si/sd/tilt/d_v_p50` 或原始 poke 产出的 `pairs[].by_sub_part[].suspect_subthreshold`/`dropped_*`。
`recommended` 的既有逻辑不变。
**穿越计数 / 包含率（`reference`）只作参考列，不参与排序**。
某一项度量缺失（`si_p50_mm=null`，例如实心鞋没认到鞋垫面、或非脚部件）时，该项排在同项有值之后，再往后落到下一个键。

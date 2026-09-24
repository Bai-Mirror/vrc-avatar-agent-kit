# 探针 shrink_cover（收缩键遮挡一致性）· 请求与参数 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §3.2.8 前段。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[探针 delete_coverage（MA ShapeChanger 删除区覆盖）](probe-delete-coverage.md) · 下一页：[探针 shrink_cover · 判据改版记录（CU / CX / CT）](probe-shrink-cover-rule.md) <!-- nav -->

### 3.2.8 `shrink_cover`——收缩键遮挡一致性（T-33，任务 CS；名单与自检 CT 修；判据 CU 改外向射线；verdict 形状 CX / B-T33b 改「或」）

**为什么**：`poke` 只回答「身体有没有穿出衣服」；它**不回答**「衣服没了，身体的收缩键还开着没有」。
2026-09-20 作者报的「工程B Milfy 关袜子/关鞋袜/关鞋子时脚的收起形态键仍=100、塌脚踝」正是后者：
收缩键的影响顶点没有被任何可见服装盖住。本探针把「哪个收缩键裸露、露多少」变成结构化数字。

**请求**（`probes` 里加 `"shrink_cover"`；参数放同名的顶层对象里，也可用扁平 `shrink_cover_<key>` 覆盖）：

```json
{
  "probes": ["shrink_cover"],
  "shrink_cover": {
    "body": "Body",
    "keys": ["auto_nonzero"],
    "min_weight": 1,
    "keys_exclude_regex": "(?i)^(vrc\\.|eye|mouth|brow|blink|tongue|face|extra_)",
    "eps_delta_mm": 0.5,
    "cover_rule": "outward_ray",
    "ray_vote": "any",
    "cover_ray_mm": 50.0,
    "cone_deg": 20.0,
    "origin_mm": 0.0,
    "cover_dist_mm": 3.0,
    "ratio_thr": 0.60,
    "area_thr": 1.0,
    "verdict_rule": "or",
    "min_verts": 20,
    "shell_rule": "any",
    "inside_check": true,
    "garments_exclude": "(?i)^(hair|nail|lash|eye|face|tooth|tongue|head|halo|particle|avatarhight|tail|ear)$"
  },
  "states": [ { "id": "sok_off", "params": { "Socks": false, "Shoes": false } } ]
}
```

| 字段 | 默认 | 说明 |
|---|---|---|
| `body` | 顶层 `body` / 自动 | 身体 SMR（匹配规则同 `pre_probe_blendshapes`：精确路径/名/叶子名，再子串）。不写走 `PickBodyPath` 自动识别 |
| `keys` | `["auto_nonzero"]` | 字符串数组。`auto_nonzero` = 身体网格上当前权重 > `min_weight` 的全部键，再按 `keys_exclude_regex` 剔表情键；显式键照收（不受排除正则影响） |
| `min_weight` | `1` | `auto_nonzero` 的「非零」门槛（权重单位 0–100） |
| `keys_exclude_regex` | `(?i)^(vrc\.\|eye\|mouth\|brow\|blink\|tongue\|face\|extra_)` | 剔表情键；非法正则记 warning 后忽略该过滤 |
| `eps_delta_mm` | `0.5` | 影响顶点门槛：blendshape 100% 时世界位移 ≥ 该值（mm）才算 A(K) |
| `cover_rule` | `outward_ray` | **任务 CU 的判据选择**：`outward_ray`（外向射线，默认）/ `distance`（旧口径：壳内或最近距离 ≤ `cover_dist_mm`）/ `either`（两者任一）。别名兼容 `any`/`majority` = `outward_ray` + 对应 `ray_vote` |
| `ray_vote` | `any` | 外向射线归票：`any`（任一条命中即遮住）/ `majority`（5 条里 ≥3 条命中） |
| `cover_ray_mm` | `50.0` | 外向射线长度（mm）。实跑验收要求 30–80 mm 之间结论不翻转 |
| `cone_deg` | `20.0` | 4 条锥向射线相对中轴的夹角（°）；切轴口径同 poke 的 `PokeBasis` |
| `origin_mm` | `0.0` | 射线起点沿外向法线的偏移（mm）：从 `v + n*origin_mm` 起射 |
| `cover_dist_mm` | `3.0` | **旧口径**：到可见服装表面最近距离 ≤ 该值算被遮挡（`cover_rule=distance`/`either` 或参考列 `covered_near_ratio` 用） |
| `ratio_thr` | `0.60` | `uncovered_ratio` 阈值；是否据此判 `uncovered` 由 `verdict_rule` 决定 |
| `area_thr` | `1.0` | `uncovered_area_cm2` 阈值（cm²）；是否据此判 `uncovered` 由 `verdict_rule` 决定。**任务 CX / B-T33b 换掉的初值**（旧 2.0 无推导），推导与「待标定」状态见下方专条 |
| `verdict_rule` | `or` | **任务 CX / B-T33b**：`uncovered` 的判据形状。`or`（默认，ratio **或** area 任一达标）/ `and`（旧行为，两者都要）/ `ratio_only` / `area_only`。产出在 `thresholds.verdict_rule`、顶层 `verdict_rule`、每行 `verdict_rule` 写明生效值 |
| `min_verts` | `20` | A(K) 可用顶点少于该值 → `too_few_verts`（不判定） |
| `shell_rule` | `any` | 本探针只接受 `any`（所有可见服装三角形都算遮挡候选）；`outward`/`majority` 是 poke 的外壳分类口径，传了也回退 `any` |
| `inside_check` | `true` | 旧口径的「落在壳内」判定（六方向射线奇偶）；仅 `cover_rule=distance`/`either` 时才跑（默认 `outward_ray` 下省掉这步） |
| `garments_exclude` | `(?i)^(hair\|nail\|lash\|eye\|face\|tooth\|tongue\|head\|halo\|particle\|avatarhight\|tail\|ear)$` | **任务 CT 口径**：只拿**叶子 GameObject 名**，且「整名完整匹配 **或** 分隔符（`_ . -` 空格等）切出的某个词完整匹配」才算命中。整段匹配由 `ShrinkCoverRules.ExcludeHit` 强制（无锚点旧串也不会子串命中） |
| `max_keys` | `512` | 自动键数量上限（超出记 `keys_truncated=true`） |
| `diag` | `false` | **任务 CV 诊断开关**。`true` 时顶层多出 `diagnostics`（只读证据，不参与 verdict、不改默认阈值）；`false` 时输出与旧版逐字节一致 |
| `diag_keys` | `[]` | 诊断的键名数组；空 = 本次 `keys_resolved`（受 `diag_max_keys` 上限，超出记 `diagnostics.keys_truncated=true`）。可显式指定被 `keys_exclude_regex` 剔掉的键 |
| `diag_samples` | `50` | 每键抽样顶点数上限（1–500），在 A(K) 上按顶点序号等距取 |
| `diag_max_keys` | `4` | 诊断键数上限（`diag_keys` 为空时兜底，避免 `auto_nonzero` 一次吐出所有键的逐顶点证据） |
| `diag_eps_mm` | `[0.5,0.2,0.1,0.05]` | eps 扫描档位；只输出各档 A(K) 计数，**不改** `eps_delta_mm` 默认值 |
| `diag_ray_budget` | `500000` | 诊断射线的独立预算，与主管线的 `ray_budget` 分开计数（用尽记 `rays_truncated`） |
| `max_iter` / `inside_votes_threshold` / `layer` / `ray_budget` | `30` / `4` / `30` / `2000000` | 同 `containment` 的射线参数（`ray_budget` 同时管外向射线） |

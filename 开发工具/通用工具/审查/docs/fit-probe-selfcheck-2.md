# T2 贴合探针 · 自检 C 与 v3 回归清单 <!-- nav -->

> 旧称：T2（原 `审查/README_T2.md`） 自检 C / §9.5。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T2 贴合探针 · 自检 2/3：恢复对照、运行期自检 A/B](fit-probe-selfcheck.md) · 下一页：[T2 贴合探针 · 已知局限与首跑核对](fit-probe-limits.md) <!-- nav -->

### 自检 C — 反向拉满收缩键后，`pierced` 明显上升（正样本）

1. 跑基线，记下所有衣物 `total.pierced` 之和。
2. 选一个**身体**上的「收缩/瘦身」形态键：名字通常含 `shrink`/`縮`/`细`/`body` 之类；
   也可先看 T1 的 `state_<id>.json` 里身体网格上**非零**的形态键，挑一个语义是「让身体变细」的。
   用 `perturb` 把它设成**反向满值**（把身体撑大 → 身体更容易从衣服里穿出）：
   ```json
   "perturb": {"renderer":"Body", "blendshape":"<收缩键名>", "weight":-100}
   ```
   （若该键正向是「放大」，则用 `100`；原则是**朝当前生效方向的反方向拉满**。）
   **工程A 的具体样本**（§9.5 回归用）：`{"renderer":"Body_b","blendshape":"AAO_Merged_sailor_shrink_1","weight":0}`
   —— 该键基线=100（AAO 为 sailor 上衣收身），置 0 即取消收身 → 躯干撑大。
3. 同一状态、`state_id="perturbcheck"` 再跑一次，比较总 `pierced`，并单独看 `sailor` 的 `Chest` 部位：
   ```bash
   OUT_A=out python3 - <<'PY'
   import json, os
   d=os.environ["OUT_A"]
   base=json.load(open(os.path.join(d,"geo_default.json")))
   per =json.load(open(os.path.join(d,"geo_perturbcheck.json")))
   bs=sum(g["total"]["pierced"] for g in base["garments"])
   ps=sum(g["total"]["pierced"] for g in per["garments"])
   print("baseline pierced=",bs," perturbed pierced=",ps)
   assert ps > bs, "反向拉满收缩键后穿出数没上升：要么键选错，要么射线/判据有问题"
   def chest(doc, path):
       g=[x for x in doc["garments"] if x["path"]==path][0]
       return [r for r in g["regions"] if r["region"]=="Chest"][0]["pierced"]
   path="kaguya_cloth/sailor"   # ← 工程A；其它工程换成对应上衣
   print("sailor/Chest pierced:", chest(base,path), "->", chest(per,path))
   assert chest(per,path) > chest(base,path), "Chest 穿出没上升"
   PY
   ```
4. **通过判据**：`ps > bs` 且肉眼可见（建议 > 基线 + 若干顶点；若基线为 0，拉满后必须显著大于 0）；
   工程A 的 `sailor/Chest` 还应明显上升（2026-09-18 v2 实测：248 → 422）。
   若不变，按顺序排查：① 该形态键在此状态下确实作用于此身体网格吗（先看 T1 快照里它的权重）；
   ② `weights_source` 是否 `nearest_bone`（部位错分会让统计变粗，但总 pierced 仍应上升）；
   ③ `calibration.hit_normal_usable` / `winding_sign` 是否与预期一致。

> 三条都过，才算这个工具在目标工程上「可用」。任何一条不过，结论一律降级为「未验证」。

### 9.5 v3 回归清单（Claude 在 Unity 里做，工程A 同一状态重跑）

> 前提：T1 把状态设到 `boot_off_hair2`（`A2_Boot=0`、`A2_Hair=0.3333`）并保持 Play；
> 请求沿用 `_长程任务_20260918/审查产出/requests_工程A/t2_a.json`（`body=Body_b`），输出到**新目录**
> （不要覆盖已归档的 `t2v2_a/`）。逐条对照：

| # | 检查 | 期望 | 不过时先看什么 |
|---|---|---|---|
| 1 | `feet[]` 里 `kaguya_cloth/loafer` 的 `class` | `footwear`；`class_source` 期望 `geometry`（`name` 也可接受），`thickness_p50_mm` 应为几毫米以上 | `thickness_count` 是否 0（鞋底不是闭合面就只能名称兜底）；`coverage_regions` 是否含 `LeftFoot`/`RightFoot` |
| 2 | `feet[]` 里 `kaguya_cloth/stocking` 的 `class` | `legwear`；`class_source` 期望 `geometry`，`thickness_p50_mm` < 2 | 若为 `other`：厚度落在 `[2, sole_min_mm)` 且名称正则没匹配上（`stocking` 应命中，不该发生） |
| 3 | `feet[]` 条目数 | 左/右各 ≥ 2（loafer、stocking 各一条），不再出现「每只脚只报一件」 | 某件没被算作覆盖该脚 → 看它的 `coverage_regions` |
| 4 | `sailor` 的 `RightHand` / `RightThumb*` | `covered`/`pierced` 应为 0，这些顶点进 `out_of_scope`（`total.out_of_scope` ≥ 旧的 169 左右，逐部位也可见） | 若仍被计入，说明 sailor 蒙皮确实覆盖手部（此前的「袖口误命中」判断要改写） |
| 5 | `sailor` 的 `Chest` | `pierced` 与 v2 基线（248）同量级，不应被 scope 清零 | `sailor` 的 `coverage_regions` 是否含 `Chest`、`region_source` 是否退化 |
| 6 | perturb 自检（上面自检 C） | `AAO_Merged_sailor_shrink_1: 100→0` 后 `sailor/Chest` pierced 明显上升（v2 实测 248→422），总 pierced 上升 | 同自检 C 的排查顺序 |
| 7 | 确定性（上面自检 A） | 同状态跑两遍（排除 `timings_ms`）逐字节一致 | 新增的 `coverage_regions`/`feet[]` 已按固定序输出；若不一致先比两次 `warnings` |

> 第 1~3 条是脚部修正的核心验收，第 4 条是覆盖范围修正的核心；第 5、6 条证明修正没有把正样本一起砍掉。
> 任一不过，先把对应衣物的 `coverage_regions` / `region_source` / `thickness_*` 贴出来再下结论。

---

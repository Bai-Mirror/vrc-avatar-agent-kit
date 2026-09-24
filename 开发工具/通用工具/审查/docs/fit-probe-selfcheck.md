# T2 贴合探针 · 自检 2/3：恢复对照、运行期自检 A/B <!-- nav -->

> 旧称：T2（原 `审查/README_T2.md`） §8 / §9 / 自检 A / 自检 B。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T2 贴合探针 · 自检 1：API 签名](fit-probe-selfcheck-api.md) · 下一页：[T2 贴合探针 · 自检 C 与 v3 回归清单](fit-probe-selfcheck-2.md) <!-- nav -->

## 8. 自检 2：临时改动 → 恢复对照表

| # | 临时改动 | 登记处 | 恢复动作 | 恢复位置 |
|---|---|---|---|---|
| 1 | `Physics.queriesHitBackfaces = true`（主探测全局开背面） | `Probe.Run` 局部 `savedBackfaces` | 写回 `savedBackfaces` | `Probe.Run` 的 `finally` |
| 2 | `Calibrate` 里先 `queriesHitBackfaces=false` 再 `=true` | `Calibrate` 局部 `saved` | 写回 `saved` | `Calibrate` 的 `finally` |
| 3 | 非 Play 退路里 `queriesHitBackfaces=hitBackfaces` | `RayShooter.Shoot` 局部 `saved` | 写回 `saved` | `Shoot` 的 `finally` |
| 4 | `renderer.enabled = false`（`hide` 自检） | `_restores`（闭包存旧值） | 写回旧 `enabled` | `Cleanup()`（逆序） |
| 5 | `SetBlendShapeWeight(idx, weight)`（`perturb` 自检） | `_restores`（闭包存旧权重） | `SetBlendShapeWeight(idx, old)` | `Cleanup()`（逆序） |
| 6 | 每件衣物一个临时 GameObject（layer 30） | `Garment.colliderGo` → `_trash` | `DestroyImmediate` | `DestroyTrash()` |
| 7 | 每件衣物的世界坐标碰撞体 Mesh | `Garment.colliderMesh` → `_trash` | `DestroyImmediate` | `DestroyTrash()` |
| 8 | 身体烘焙 Mesh（`BakeMesh` 产物） | `_bodyBaked` → `_trash` | `DestroyImmediate` | `DestroyTrash()` |
| 8b | **身体临时 GameObject（v2，layer 29）** | `_bodyColliderGo` → `_trash` | `DestroyImmediate` | `DestroyTrash()` |
| 8c | **身体碰撞体 Mesh（v2，排除顶点后的世界坐标网格）** | `_bodyColliderMesh` → `_trash` | `DestroyImmediate` | `DestroyTrash()` |
| 9 | 衣物 SMR 的临时烘焙 Mesh | 局部 `baked` | `DestroyImmediate` | `TryGetWorldMesh` 的 `finally` |
| 10 | 重算法线用的网格副本 | 局部 `cp` | `DestroyImmediate`（用完立即） | `TryGetWorldMesh` 内联 |
| 11 | 标定用四边形 GameObject + Mesh | 局部 `cgo` / `cm` | `DestroyImmediate` | `Calibrate` 的 `finally` |
| 12 | 每件衣物探测时 `collider.enabled = true` | 局部流程 | `collider.enabled = false`（随后整体销毁） | 每件衣物循环末尾 |
| 13 | 临时物体的 `hideFlags = HideAndDontSave` | — | 随物体销毁，无需单独恢复 | `DestroyTrash()` |
| 14 | **身体碰撞体整轮 `enabled = true`（v2）** | — | 随物体销毁，无需单独恢复 | `DestroyTrash()` |

**幂等**：`Cleanup()` 有 `_cleaned` 守卫，`Probe.Run` 的 `finally` 与 AuditIO 结束时的
`IAuditTool.Cleanup()` 都调用它，不会二次恢复/二次销毁。

**没有对场景持久数据的改动**：不 `EditorSceneManager.MarkSceneDirty`、不 `SaveScene`、不改任何资产。

---

## 9. 自检 3：三条运行期自检的执行方法

> 前提：T1 已把状态设好并保持 Play 模式。以下命令里的 `<工程>` 指被审查工程根目录。
> 每次发请求前把 JSON 写进 `<工程>/Library/AvatarAudit/request.json`，再执行
> `Tools/AvatarAudit/Run Request`。`<out>` 换成实际输出目录。

### 自检 A — 同状态跑两遍，数值一致（确定性 / 负样本）

1. 用**同一个状态**、同一个 `state_id`，输出到两个目录 `out_a`、`out_b`（都不带 `perturb`/`hide`），
   各跑一次，得到 `out_a/geo_default.json`、`out_b/geo_default.json`。
2. 比对（**排除 `timings_ms`**，耗时本来就会变）：
   ```bash
   OUT_A=out_a OUT_B=out_b python3 - <<'PY'
   import json, os
   a=json.load(open(os.path.join(os.environ["OUT_A"],"geo_default.json")))
   b=json.load(open(os.path.join(os.environ["OUT_B"],"geo_default.json")))
   a.pop("timings_ms"); b.pop("timings_ms")
   print("IDENTICAL" if a==b else "DIFF")
   assert a==b, "两次运行结果不一致，工具不确定（先查 markers 并列深度 / warnings）"
   PY
   ```
3. **通过判据**：`IDENTICAL`。若失败，先看 `markers`（同深度并列的顺序）、再查两次 `warnings`
   是否不同（例如第二次才触发 `RaycastCommand` 退路）。

### 自检 B — 隐藏被测衣物后，该衣物 `covered = 0`（防「删掉被测物指标变好」）

1. 跑基线，从 `geo_default.json` 挑一件 `total.coverage > 0` 的衣物，记下 `path`（例如 `Outfit/Skirt`）。
2. 请求里加 `"hide": "<该 path>"`，**其余不变**，`state_id="hidecheck"` 再跑一次。
3. 检查：
   ```bash
   OUT_A=out python3 - <<'PY'
   import json, os
   d=os.environ["OUT_A"]
   base=json.load(open(os.path.join(d,"geo_default.json")))
   hid =json.load(open(os.path.join(d,"geo_hidecheck.json")))
   target="Outfit/Skirt"          # ← 换成步骤 1 记下的 path
   g=[x for x in hid["garments"] if x["path"]==target][0]
   print("skipped=",g["skipped"],"reason=",g["skip_reason"],
         "covered=",g["total"]["covered"],"pierced=",g["total"]["pierced"])
   assert g["total"]["covered"]==0 and g["total"]["pierced"]==0, "被隐藏的衣物仍有覆盖，hide 未生效"
   PY
   ```
4. **通过判据**：被隐藏衣物 `total.covered == 0` 且 `total.pierced == 0`（且 `skipped=true`）；
   其它衣物的 `total` 应与基线**逐字段相同**（若把整件衣物直接删掉，其它件数值会变，也能暴露）。

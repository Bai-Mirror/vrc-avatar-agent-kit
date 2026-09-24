# T5 形态键依赖矩阵 · analyze、分类与候选判据 <!-- nav -->

> 旧称：T5（原 `审查/README_T5.md`） §5–§7。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T5 形态键依赖矩阵 t5_shapekey_matrix.py · 流水线与子命令](shapekey-matrix.md) · 下一页：[T5 形态键依赖矩阵 · 自检、局限、编码](shapekey-matrix-selfcheck.md) <!-- nav -->

## 5. `analyze`：依赖矩阵

```
analyze --t1 <T1 输出目录> --sweep <sweep 请求> --out <目录>
        [--params <params.json>] [--n-clothing 3]
        [--filter-file F] [--clothing-roots-file F] [--clothing-keywords-file F]
        [--body-words-file F] [--foot-keywords-file F] [--shrink-keywords-file F]
        [--shoe-keywords-file F]
```

### 5.1 基准态与单关态的识别（不依赖 id 命名）

- **Bool 判定**：某个参数在整份 sweep 请求里出现过的值全在 `{0,1}` 且不同值 ≤2 → 判为 Bool。
  这样 `A2_Outfit`（0、0.1429…1.0）不会被误判。
- **单关态**：状态 S 与状态 B 的**参数键集合完全相同**、**恰好一个 Bool 不同**、且方向是 `1→0`
  → S 是 B 的单关态。
- **基准态**：有单关态、且自己不是任何状态单关态的状态（避免把「A 关」这种中间态也当基准）。
- **全关态**：与基准态键集合相同、非 Bool 参数相同、所有 Bool 都为 0 的状态（通常就是 `__naked`）。

以 工程A 的手工请求为例，识别出 8 个整套/服装基准态 + 3 个「发型 × 外套」基准态，
`default`、各 `__naked` 不会被当成基准。

### 5.2 输出

`matrix.json` 是结构化结果；`matrix.md` 是人读版，两者内容一致。每个基准态给：

- `visible_clothing`：可见服装件（判定见 §6），同时给 `path`（Play 构建后的原样名）与 `restored`（还原名）。
- `nonzero_keys`：**全部**非零形态键中过滤掉表情/面捕/眨眼类之后的键，同时给原样键名与还原名。
- `body_shrink_foot_keys`：身体渲染器上的收缩/脚型键（候选 c 的判据）。
- `single_off[]`：每个单关态的 `hidden`/`shown` 渲染器、`key_changes`（键、前→后、是否表情类）。
- `naked`：全关态的同款信息（若识别到）。

`matrix.md` 里的键与渲染器都**先给还原名、再把 Play 构建后的原样名放在括号里**（相同则不重复），
便于对着 T1 原始 `state_*.json` / Hierarchy 复核。示例：

```
- Body_b · outer_shrink（原名 AAO_Merged_outer_shrink_2）: 100→0
隐藏：Outfit_MMN_黑/Shoes（原 _Outfit$Outfit_MMN_黑$164/Shoes）
```

### 5.3 名字还原规则

| Play 构建后 | 还原为 |
|---|---|
| 形态键 `AAO_Merged_<原名>_<n>` | `<原名>`（去 `AAO_Merged_` 前缀 + 去尾部 `_<数字>`） |
| 渲染器路径段 `名$原物体$编号` | `原物体`（如 `_Outfit$Outfit_RePoppin$163` → `Outfit_RePoppin`） |
| 渲染器路径段 `$$AAO_AUTO_MERGE_SKINNED_MESH_n` | `<AAO合并网格#n>`（原名不可知，只标出它是合并产物） |
| 不匹配以上规则的段/键 | 原样保留 |

---

## 6. 分类与过滤规则（关键词，可配置）

所有分类都是**关键词启发式**，不是语义理解；每个关键词文件都是 JSON 列表（`--*-file` 覆盖默认），
写清楚是为了让人知道误报从哪来。

- **匹配方式**：CJK 关键词按子串；ASCII 关键词按「完整 token」，长度 ≥4 才允许前缀匹配
  （`sock`→`Socks`、`shoe`→`Shoes`）。这样 `top` 不会命中 `Stop`、`set` 不会命中 `Seated`。
- **表情/面捕过滤词**：`blink/eye/brow/mouth/jaw/viseme/tongue/face/…` 与 `まばたき/瞬き/目/口/眉/顔…`。
  命中则不进 `nonzero_keys`，键变化里命中会标 `（表情类，已过滤）`。
- **服装件**：还原路径含服装根词（`cloth/clothes/clothing/outfit/wear/apparel/garment`）**或**叶名含
  单品词（`pants/skirt/sock/shoe/boot/loafer/coat/outer/sailor/…`）。根词是为了把
  `kaguya_cloth/aburaage_open`、`Outfit_Kitty_黑大/$$AAO_AUTO_MERGE_SKINNED_MESH_0` 这类
  「名字里没有单品词」的部件也算进来。
- **身体渲染器**：还原路径含 `body`。
- **脚型/鞋跟键**：`foot/heel/toe/足/ヒール/つま先/爪先`。
- **收缩类键**：`shrink/shlink/縮/収縮/シュリンク`。
- **鞋类开关参数**：参数名或菜单路径含 `shoe/sho/boot/loafer/sneaker/heel/靴/鞋/ヒール`。
- **分组推断词**：整套轮盘 `整套/套装/全身/outfit/set`；服装部位 `部件/鞋/袜/外套/上衣/下着/内衣/裙/裤/手套/cloth/outfit/shoe/sock/coat/top/pants/skirt/bra/inner`。

> 已知取舍：工程A 的 `VF57_A2_Coat` / `VF57_A2_Top` 是没有菜单路径的遗留 Bool，按名匹配会被
> 推断为服装部位。工具把分组和证据全部写进 `groups_used.json` 让人确认，就是为这种情况留的口子；
> 不要盲信推断结果。

---

## 7. 自动候选与判据（只是嫌疑人）

候选一律**不是定论**；`matrix.md` 文末也复述了判据。

- **(a) `residual`**：某单关态隐藏了渲染器 R，但存在一个**不在 R 上**的非零键，其还原键名含 R 的
  还原名 token（拉丁 ≥3 字符 / CJK 任意）。含义：R 收了，可它的适配键还给着。
  *取舍*：键若就长在 R 自己身上（如 `kaguya_cloth/outer.use_bag`）不算——物体都隐藏了，无害。
  **不因「键长在服装渲染器上」就跳过**：那会把「衣服上的收缩键」这类真阳性也吞掉
  （如 工程A `kaguya_cloth/sailor.outer_shlink` 在外套隐藏后仍非零）。已复核的共享词
  误报只从代码 `RESIDUAL_EXEMPTIONS` 的**显式豁免表**逐条扣（表里每条带出处），命中另列
  `a′. residual 豁免表命中`。往表里加新条目要先复核「键属哪件、是不是同套」，禁止改成
  前缀/正则式泛化。
  **另设通用 token 停用词表 `RESIDUAL_STOPWORDS`**（命中另列 `a″`）：只收无区分力的
  token——开关状态后缀（`off`/`on`）、素体/角色名（工程E 的 `rurune`）、跨件共用部件词
  （工程E 两件不同 hood 的 `hood`）。命中停用词而本来会被算 residual 的逐条列 `a″`，
  不静默丢弃；真阳性 `kaguya_cloth/sailor.outer_shlink`（token `outer`）不受影响。
  出处：验收_20260919_BC至BH.md F-14。
- **(b) `mis_bound`**：
  - `foot`：脚型/鞋跟类键在「非鞋」Bool 关掉时变化；并在 detail 里核对「基准态自己的关鞋子态里这些
    键是否不变」。工程A MMN/ANEMONE 关袜 → `Foot_heel_OFF` 100→0、关鞋不变，就是本类。
  - `shrink`：收缩类键变化，但既不对应任何被隐藏物体、也不对应开关参数名。
- **(c) `no_body_keys`**：基准态可见服装件 > `--n-clothing`（默认 3），但身体渲染器上没有任何
  收缩/脚型键。*阈值取舍*：3 是「穿了三件以上还没做任何身体适配」的经验线；配饰多的套装可能误报，
  漏报则调小，可用 `--n-clothing` 改。工程A 的 RePoppin（9 件）/Kitty（6 件）被标出，
  kaguya（8 件，有收缩键）与 MMN（17 件，有脚型键）不标，符合人工判断。
- **(d) `unexpected_change`**：关一件衣服时，另一件**基准态可见的服装件**上的键变化，且该键与隐藏
  物体、与开关参数都无 token 关联。脚型/收缩类键不重复计入（已归 b）。
- **(e) `out_of_range`**：任何状态出现形态键值 `<0` 或 `>100`。VRChat 客户端会钳制，动画里给越界值
  通常意味着曲线写错。扫描覆盖所有状态，不只是基准/单关。

---

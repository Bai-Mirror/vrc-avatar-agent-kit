> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/shapekey-matrix-selfcheck.md)

# T5 blend shape dependency matrix · self-check, limitations, encoding <!-- nav -->

> Formerly: T5 (original `审查/README_T5.md`) §8–§10. § numbers follow the original; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous: [T5 blend shape dependency matrix · analyze, classification and candidate criteria](shapekey-matrix-analyze.md) <!-- nav -->

## 8. Self-check: Project A's existing 71 states

Use the hand-written request `_长程任务_20260918/审查产出/requests_工程A/t1_sweep.json` as `--sweep`,
and `…/工程A/t1_sweep_outfit_parts/` as `--t1`:

```bash
python3 开发工具/通用工具/审查/t5_shapekey_matrix.py analyze \
  --t1 _长程任务_20260918/审查产出/工程A/t1_sweep_outfit_parts \
  --sweep _长程任务_20260918/审查产出/requests_工程A/t1_sweep.json \
  --out _长程任务_20260918/派工/tmp/t5_selfcheck
```

Output (actually run this round, `_长程任务_20260918/派工/tmp/t5_selfcheck/`):

```
[T5 analyze] 基准态 11 个，读入状态 71 个。
  候选：residual 0 / mis_bound 2 / no_body_keys 5 / unexpected_change 0 / out_of_range 0
  K12 豁免表命中（已在 residual 里扣除）：0 条
  residual 停用词命中（已在 residual 里扣除）：0 条
```

(Meaning: 11 base states, 71 states read; candidate counts as listed; K12 exemption-table hits and residual stopword hits, both already deducted from residual: 0 each.)

**Facts required to be reproduced, checked one by one:**

| Fact in the draft | This tool's output | Conclusion |
|---|---|---|
| kaguya coat off → `outer_shrink`/`outer_shlink`/`Outer_on` 100→0 | See excerpt below: all three are in the key changes of `[A2_Coat off] kaguya__Coat_off` | ✅ |
| MMN socks off → `Foot_heel_OFF` 100→0 while shoes off leaves it unchanged; should be flagged by b | `[A2_Sok off] MMN__Sok_off` key change 100→0; `[A2_Sho off]` key changes (none); candidate b lists 2 entries | ✅ |
| RePoppin/Kitty base states flagged by c | Candidate c lists Kitty_a/b and RePoppin_a/b/c, 5 entries total | ✅ |

`matrix.md` excerpt (verbatim, only blank lines removed):

```
# 形态键依赖矩阵（T5 analyze）

- 读入状态 71 个，基准态 11 个；blendshape_epsilon=0.0001
- 判为 Bool 的参数：A2_Btm, A2_Coat, A2_Sho, A2_Sok, A2_Top, A2_Und

## 基准态 kaguya__all
参数：`{"A2_Btm": 1, "A2_Coat": 1, "A2_Outfit": 0, "A2_Sho": 1, "A2_Sok": 1, "A2_Top": 1, "A2_Und": 1}`
可见服装件（8）：Pants | kaguya_cloth/aburaage_open | kaguya_cloth/bag | kaguya_cloth/loafer |
kaguya_cloth/outer | kaguya_cloth/outer_breast_big_open | kaguya_cloth/sailor | kaguya_cloth/stocking
非零形态键（已过滤表情/面捕类，6）：
- Body_b · outer_shrink（原名 AAO_Merged_outer_shrink_2） = 100
- Body_b · sailor_shrink（原名 AAO_Merged_sailor_shrink_1） = 100
- Hair · Outer_on = 100
- Outfit_RePoppin/(A)Shirt · Parker_on = 100
- kaguya_cloth/outer · use_bag = 100
- kaguya_cloth/sailor · outer_shlink = 100
身体上的收缩/脚型键：Body_b.outer_shrink（原名 AAO_Merged_outer_shrink_2） | Body_b.sailor_shrink（原名 AAO_Merged_sailor_shrink_1）

#### [A2_Coat off] kaguya__Coat_off（A2_Coat: 1→0）
隐藏：kaguya_cloth/outer | kaguya_cloth/outer_breast_big_open
出现：（无）
键变化：
- Body_b · outer_shrink（原名 AAO_Merged_outer_shrink_2）: 100→0
- Hair · Outer_on: 100→0
- Outfit_RePoppin/(A)Shirt · Parker_on: 100→0
- kaguya_cloth/sailor · outer_shlink: 100→0

## 基准态 MMN__all
可见服装件（17）：Pants | Outfit_MMN_黑/Bag（原 _Outfit$Outfit_MMN_黑$164/Bag） | …（16 个 MMN 部件）
非零形态键（已过滤表情/面捕类，2）：
- Body_b · Foot_heel_OFF_____足_ヒールオフ（原名 AAO_Merged_Foot_heel_OFF_____足_ヒールオフ_3） = 100
- Outfit_RePoppin/(A)Shirt · Parker_on = 100
身体上的收缩/脚型键：Body_b.Foot_heel_OFF_____足_ヒールオフ（原名 AAO_Merged_Foot_heel_OFF_____足_ヒールオフ_3）

#### [A2_Sho off] MMN__Sho_off（A2_Sho: 1→0）
隐藏：Outfit_MMN_黑/Shoes（原 _Outfit$Outfit_MMN_黑$164/Shoes）
出现：（无）
键变化：
- （无）

#### [A2_Sok off] MMN__Sok_off（A2_Sok: 1→0）
隐藏：Outfit_MMN_黑/Socks（原 _Outfit$Outfit_MMN_黑$164/Socks）
出现：（无）
键变化：
- Body_b · Foot_heel_OFF_____足_ヒールオフ（原名 AAO_Merged_Foot_heel_OFF_____足_ヒールオフ_3）: 100→0

## 自动候选
### a. residual：渲染器被隐藏，但名字与它相关的键仍非零（0 条）
- （无）
### b. mis_bound：脚型/收缩类键跟着不相干的开关走（2 条）
- 基准 MMN__all；状态 MMN__Sok_off；开关 A2_Sok：脚型/鞋跟键 Foot_heel_OFF_____足_ヒールオフ 跟着非鞋开关 A2_Sok 变化；且关鞋时这些键不变。
- 基准 ANEMONE__all；状态 ANEMONE__Sok_off；开关 A2_Sok：脚型/鞋跟键 Foot_heel_OFF_____足_ヒールオフ 跟着非鞋开关 A2_Sok 变化；且关鞋时这些键不变。
### c. no_body_keys：可见服装件多于阈值但身体没有收缩/脚型键（5 条）
- 基准 Kitty_a__all：可见服装件 6 件（>3）但身体渲染器上没有任何收缩/脚型键。
- 基准 Kitty_b__all：可见服装件 6 件（>3）但身体渲染器上没有任何收缩/脚型键。
- 基准 RePoppin_a__all：可见服装件 9 件（>3）但身体渲染器上没有任何收缩/脚型键。
- 基准 RePoppin_b__all：可见服装件 9 件（>3）但身体渲染器上没有任何收缩/脚型键。
- 基准 RePoppin_c__all：可见服装件 9 件（>3）但身体渲染器上没有任何收缩/脚型键。
### d. unexpected_change：关一件衣服时无关可见件的键变化（0 条）
- （无）
### e. out_of_range：形态键值 <0 或 >100（0 条）
- （无）
```

Additional note: besides the 8 outfit base states listed in the draft (kaguya / MMN / ANEMONE / Kitty_a / Kitty_b /
RePoppin_a / RePoppin_b / RePoppin_c), the tool also identifies `kaguya__hair0/1/2_coat1` as base states
(each has one `A2_Coat` single-off state), which corresponds exactly to the draft's "hairstyle × coat" section; `default` and the various `__naked`
have no single-off states and are not taken as bases.

---

## 9. Done / not done this round / known limitations

**Done (reproducible; outputs all kept under `_长程任务_20260918/派工/tmp/`)**:

1. `analyze` reproduced every fact in the §8 table (residual/d/unexpected/out_of_range are 0 on real data).
2. `slots`: `--step 1/64 --only '^A2_Outfit$'` → 65 values, first and last exactly 0.0/1.0;
   `--step 1/4 --only 'A2_Outfit|A2_Hair'` → a request with 10 states.
3. `slots-reduce`: with synthetic T1 output, `A2_Hair` was correctly compressed into 3 intervals (single-point interval flagged `narrow`),
   and `A2_Outfit` with a constant signature into 1 interval; rebuilding the plan from `--params` when `slots_plan.json` is missing also passed.
4. `sweep`: from the real `params.json`, inferred the full-set radial `A2_Outfit` and 6 clothing-part Bools, generating
   `setN__all / setN__<Bool>_off / setN__naked`; overriding with `--groups` also passed.
5. A synthetic dataset additionally triggered all five candidates — (a) residual, (b) foot/shrink, (d) unexpected_change, (e) out_of_range —
   confirming the decision paths run without throwing.

**Not done / needs real T1 to verify**:

1. This round did not open Unity or run T1; requests generated by `slots`/`sweep` **have not been executed on a real Play build**;
   whether state signatures are stable (especially whether jitter remains with `volatile_probe=false`) awaits a real run.
2. `slots-reduce` was verified only on synthetic data; whether the interval count of a real radial (e.g. the 7 outfits of `A2_Outfit`) equals
   the actual number of outfits, and whether the `narrow` threshold is appropriate, must be calibrated against real scan results.
3. `groups` inference depends on menu-path naming; an avatar with different naming habits may yield no inference at all — use `groups.json` then.

**Known limitations**:

1. Base/single-off identification only recognizes **one Bool going 1→0**. Toggles linking multiple parameters (one switch removing several pieces) do not enter the single-off list;
   have a colleague split such toggles into single-parameter states, or manually inspect `naked`/full diff in `matrix.json`.
2. "Related" relies entirely on name tokens; with cross-language naming (parameter called Coat, object called outer), the **hidden object** serves as the bridge;
   if the vendor's naming is completely unrelated, candidates (b2)(d) will false-positive or miss.
3. The expression filter is key-name keywords, not "is this key face tracking". Custom naming (e.g. Japanese expression keys) needs
   extra words via `--filter-file`.
4. The visible clothing list in `matrix.md` is heuristic and may treat accessories as clothing or vice versa; the raw `path` in `matrix.json`
   is authoritative.
5. The tool does not judge **design intent** such as "should the shrink value be 0 or 100" or "should the heel key follow the shoes or the socks" — it only lays out
   "the connections actually implemented"; right or wrong is for a human (or the SOP/client requirements) to decide.

---

## 10. File encoding

The tool and its outputs are all **UTF-8 without BOM, LF**. `t5_shapekey_matrix.py` depends only on the Python 3 standard library.

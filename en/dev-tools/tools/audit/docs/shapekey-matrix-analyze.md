> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/shapekey-matrix-analyze.md)

# T5 blend shape dependency matrix · analyze, classification and candidate criteria <!-- nav -->

> Formerly: T5 (original `审查/README_T5.md`) §5–§7. § numbers follow the original; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous: [T5 blend shape dependency matrix t5_shapekey_matrix.py · pipeline and subcommands](shapekey-matrix.md) · Next: [T5 blend shape dependency matrix · self-check, limitations, encoding](shapekey-matrix-selfcheck.md) <!-- nav -->

## 5. `analyze`: dependency matrix

```
analyze --t1 <T1 output dir> --sweep <sweep request> --out <dir>
        [--params <params.json>] [--n-clothing 3]
        [--filter-file F] [--clothing-roots-file F] [--clothing-keywords-file F]
        [--body-words-file F] [--foot-keywords-file F] [--shrink-keywords-file F]
        [--shoe-keywords-file F]
```

### 5.1 Identifying base states and single-off states (independent of id naming)

- **Bool detection**: if every value a parameter takes anywhere in the sweep request lies in `{0,1}` and there are ≤2 distinct values → it is treated as Bool.
  This keeps `A2_Outfit` (0, 0.1429…1.0) from being misclassified.
- **Single-off state**: state S has **exactly the same parameter key set** as state B, **differs in exactly one Bool**, and the direction is `1→0`
  → S is a single-off state of B.
- **Base state**: a state that has single-off states and is not itself a single-off state of any state (so intermediate states like "A off" are not taken as a base).
- **All-off state**: a state with the same key set as the base state, the same non-Bool parameters, and all Bools at 0 (usually just `__naked`).

Taking Project A's hand-written request as an example, 8 full-set/outfit base states + 3 "hairstyle × coat" base states are identified;
`default` and the various `__naked` are not treated as bases.

### 5.2 Output

`matrix.json` is the structured result; `matrix.md` is the human-readable version, with the same content. For each base state it gives:

- `visible_clothing`: visible clothing pieces (see §6 for the criterion), giving both `path` (the raw name after the Play build) and `restored` (the restored name).
- `nonzero_keys`: **all** non-zero blend shapes after filtering out expression/face-tracking/blink keys, giving both the raw key name and the restored name.
- `body_shrink_foot_keys`: shrink/foot-shape keys on the body renderer (criterion for candidate c).
- `single_off[]`: for each single-off state, the `hidden`/`shown` renderers and `key_changes` (key, before→after, whether expression-type).
- `naked`: the same information for the all-off state (if identified).

In `matrix.md`, keys and renderers are **given with the restored name first, followed by the raw post-Play-build name in parentheses** (not repeated if identical),
to make cross-checking against T1's raw `state_*.json` / Hierarchy easy. Example:

```
- Body_b · outer_shrink（原名 AAO_Merged_outer_shrink_2）: 100→0
隐藏：Outfit_MMN_黑/Shoes（原 _Outfit$Outfit_MMN_黑$164/Shoes）
```

### 5.3 Name restoration rules

| After Play build | Restored to |
|---|---|
| Blend shape `AAO_Merged_<original>_<n>` | `<original>` (strip the `AAO_Merged_` prefix + strip the trailing `_<digits>`) |
| Renderer path segment `name$original-object$index` | `original-object` (e.g. `_Outfit$Outfit_RePoppin$163` → `Outfit_RePoppin`) |
| Renderer path segment `$$AAO_AUTO_MERGE_SKINNED_MESH_n` | `<AAO合并网格#n>` (original name unknowable; only marks it as a merge product) |
| Segments/keys matching none of the above | Kept as is |

---

## 6. Classification and filtering rules (keywords, configurable)

All classification is **keyword heuristics**, not semantic understanding; every keyword file is a JSON list (`--*-file` overrides the defaults),
spelled out so people know where false positives come from.

- **Matching**: CJK keywords match as substrings; ASCII keywords match as a "whole token", and prefix matching is only allowed for length ≥4
  (`sock`→`Socks`, `shoe`→`Shoes`). This way `top` does not hit `Stop` and `set` does not hit `Seated`.
- **Expression/face-tracking filter words**: `blink/eye/brow/mouth/jaw/viseme/tongue/face/…` and `まばたき/瞬き/目/口/眉/顔…`.
  Hits are excluded from `nonzero_keys`; hits among key changes are marked `（表情类，已过滤）` (expression-type, filtered).
- **Clothing pieces**: the restored path contains a clothing root word (`cloth/clothes/clothing/outfit/wear/apparel/garment`) **or** the leaf name contains
  an item word (`pants/skirt/sock/shoe/boot/loafer/coat/outer/sailor/…`). The root words exist so that parts like
  `kaguya_cloth/aburaage_open` and `Outfit_Kitty_黑大/$$AAO_AUTO_MERGE_SKINNED_MESH_0`,
  "whose names contain no item word", are also counted.
- **Body renderer**: restored path contains `body`.
- **Foot-shape/heel keys**: `foot/heel/toe/足/ヒール/つま先/爪先`.
- **Shrink keys**: `shrink/shlink/縮/収縮/シュリンク`.
- **Shoe toggle parameters**: parameter name or menu path contains `shoe/sho/boot/loafer/sneaker/heel/靴/鞋/ヒール`.
- **Grouping inference words**: full-set radial `整套/套装/全身/outfit/set`; clothing parts `部件/鞋/袜/外套/上衣/下着/内衣/裙/裤/手套/cloth/outfit/shoe/sock/coat/top/pants/skirt/bra/inner`.

> Known trade-off: Project A's `VF57_A2_Coat` / `VF57_A2_Top` are legacy Bools without menu paths; name matching will
> infer them as clothing parts. The tool writes all groups and evidence into `groups_used.json` for a human to confirm — precisely the escape hatch for this case;
> do not blindly trust the inference.

---

## 7. Automatic candidates and criteria (suspects only)

Candidates are **never verdicts**; the end of `matrix.md` also restates the criteria.

- **(a) `residual`**: a single-off state hides renderer R, but there exists a non-zero key **not on R** whose restored key name contains a
  token of R's restored name (Latin ≥3 characters / CJK any). Meaning: R was put away, yet its fitting key is still applied.
  *Trade-off*: a key living on R itself (e.g. `kaguya_cloth/outer.use_bag`) does not count — the object is hidden anyway, harmless.
  **Do not skip just because "the key lives on a clothing renderer"**: that would also swallow true positives such as "shrink keys on clothing"
  (e.g. Project A `kaguya_cloth/sailor.outer_shlink` stays non-zero after the coat is hidden). Verified shared-word
  false positives are deducted only one by one via the **explicit exemption table** `RESIDUAL_EXEMPTIONS` in the code (each entry cites its source); hits are listed separately as
  `a′. residual 豁免表命中`. Before adding a new entry, first verify "which piece the key belongs to and whether it is the same set"; generalizing it into
  prefix/regex patterns is forbidden.
  **There is also a generic token stopword table `RESIDUAL_STOPWORDS`** (hits listed separately as `a″`): it only holds tokens with no discriminating power —
  toggle-state suffixes (`off`/`on`), base avatar/character names (Project E's `rurune`), part words shared across pieces
  (`hood` from Project E's two different hoods). Items that hit a stopword and would otherwise count as residual are listed one by one under `a″`,
  not silently dropped; the true positive `kaguya_cloth/sailor.outer_shlink` (token `outer`) is unaffected.
  Source: `验收_20260919_BC至BH.md` F-14.
- **(b) `mis_bound`**:
  - `foot`: foot-shape/heel keys change when a "non-shoe" Bool is switched off; the detail also checks "whether these keys stay unchanged in the base state's own
    shoes-off state". Project A MMN/ANEMONE socks off → `Foot_heel_OFF` 100→0 while shoes off leaves it unchanged: exactly this class.
  - `shrink`: a shrink key changes, but corresponds neither to any hidden object nor to the toggle parameter name.
- **(c) `no_body_keys`**: the base state has more visible clothing pieces than `--n-clothing` (default 3), yet the body renderer has no
  shrink/foot-shape keys at all. *Threshold trade-off*: 3 is the empirical line for "wearing three or more pieces without any body fitting"; accessory-heavy sets may false-positive,
  lower it for misses; change it with `--n-clothing`. Project A's RePoppin (9 pieces) / Kitty (6 pieces) are flagged,
  while kaguya (8 pieces, has shrink keys) and MMN (17 pieces, has foot-shape keys) are not, matching human judgment.
- **(d) `unexpected_change`**: when one clothing piece is switched off, a key on another **clothing piece visible in the base state** changes, and that key has no token link to
  the hidden object or the toggle parameter. Foot-shape/shrink keys are not double-counted (already under b).
- **(e) `out_of_range`**: any state with a blend shape value `<0` or `>100`. The VRChat client clamps, and an out-of-range value in an animation
  usually means a miswritten curve. The scan covers all states, not only base/single-off.

---

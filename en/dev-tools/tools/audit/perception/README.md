> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/perception/README.md)

# perception/ — Offline perception-mechanism tools (Python)

The offline part of T-01–T-32; read-only on the project, never launches Unity. Shared module `unity_yaml.py` (Unity multi-document YAML).

| File | Task | Purpose |
|---|---|---|
| `unity_yaml.py` | T-04 shared-module extraction | Unity YAML/`.controller` reading, GUID index, name resolution |
| `clip_writes.py` | T-11 helper | clip curve parsing (`m_FloatCurves`/blend tree/state machine) |
| `writers_static.py` | T-11 | Static writer graph `writers.json` (includes MA components in variant chains/nested prefabs; hosts resolved to scene-instance paths) |
| `static_rules.py` | T-11/E-T11-01 | Runs 6 classes of static rules on `writers.json` to produce candidates (K1 multiple writers on one key … K6 out of range); no rescan, no right/wrong judgement; `--selftest` verifies known samples with real data from Project A/Project B |
| `key_class_blender.py` | T-17 | Key-class calibration (Blender side) |
| `profile_keys.py` | AQ | Writes the `body_keys` inventoried by T-05 into the base-avatar profile `all_keys:` (SEM-07 uses the full key table) |
| `sync_audit.py` | T-09 | Audit-code sync (`--from-git <rev>` takes sources from the given revision, isolating half-done work in the working tree) |
| `strip_audit.py` | T-23 | Strip audit leftovers before delivery: `--check` lists, `--apply` actually deletes + zero-leftover self-check |
| `muscles.py` | T-26 | Fixed table of 95 muscles, finger-name mapping, body regions, Library B joint groups |
| `pose_frames.py` | T-26 | Pose-frame library `pose_library.json` |
| `pb_static.py` | T-30 | PhysBone static inventory `pb.json` |
| `pose_plan.py` | T-29 | Pose × state plan: per-part pose subset, two passes, batching by time budget in seconds → `request_pose_<n>.json` |
| `decl_draft.py` | T-04 | Declaration draft generator (drafts `声明.yaml` from generator tables/scene/vendor clips/T4/base-avatar profile/inventory) |
| `decl_validate.py` | T-02 | Declaration validator (YAML→schema→SEM-01…24→`decl.json`) |
| `verdict.py` | T-14 | Checker: declaration × T1/geo/writers → `verdicts.json` + summary |
| `rules_universal.py` | T-14 | Universal rules U1–U7 + U-KF, fallback resolution for post-build renames (shared module of `verdict.py`) |
| `thresholds.yaml` | T-14/T-18 | Thresholds/units/sources/what to do when unmet; geometry items are `advisory` |
| `key_follow_verdict.py` | AM | Same-name key mismatch judgement; `verdict.py`'s U-KF **calls it directly** (`load_states`+`build_result`) |

---

## Pose library (T-26; implemented in `muscles.py` + `pose_frames.py`)

```bash
python3 perception/pose_frames.py --selftest                 # self-verify on Project A data (about 50 s)
python3 perception/pose_frames.py --project <工程根>          # writes <工程>/_感知/out/pose_library.json
python3 perception/pose_frames.py --envelope extreme ...      # additionally generate HumanDescription ±1 levels (off by default)
python3 perception/muscles.py --selftest                     # 95-name table / finger mapping / Library B = 66 entries
```

### Three libraries (03 §8.1)

* **Library A, real static poses**: SDK `Packages/com.vrchat.avatars/**/ProxyAnim/*.anim`, **all 79**
  (of which `landing`/`hands_idle2`/`empty`/`rotate90_right` have non-zero length); GoGo Loco fixed 7 entries
  (collected only if installed); **project-private** = all humanoid clips referenced by the controllers attached to the avatar descriptor (descriptor's 5 layers + those merged in by `ModularAvatarMergeAnimator`, reusing `writers_static.ProjectScan`); SDK/GoGo packages go only through the two fixed lists above and are not counted twice. Clips on Additive layers (`AnimatorLayer.m_BlendingMode==1`) are tagged `additive: true`;
  their values are deltas (`moved_regions` computed against a baseline of 0), and T-27 layers them on top of `stand_still`.
* **Library B, joint sweeps (exactly 66 entries)**: 7 left/right-split joint groups × {25,50,75,100}% × left/right = 56; spine forward bend
  4 levels; 6 combos (sit/deep squat/seiza/arms crossed/arms raised/cross-legged). Dosing = all other muscles take the `stand_still` value; the swept muscle is interpolated linearly from its
  `stand_still` value toward the **Library A envelope extreme** in that direction (agy D5: HumanDescription ±1 is not used).
  If Library A has no displacement in that direction, fall back to the opposite direction and record it in `stats.envelope_fallbacks` (empty for Project A).
* **Library C, real motion clips**: GM's 16 bundled multi-frame expressions; GoGo `go_jump_in_place`/`go_knockback`/
  `go_manual_afk_idle`; declaration `poses.extra_clips` (empty if not given). Same rule throughout: “observed-muscle argmax/argmin +
  lowest `RootT.y` frame + `Foot Up-Down` extreme frame, dedup at L∞<0.05, ≤6 frames per clip”.

### How it reads, and key conventions

* Only reads `m_FloatCurves` (which carry the `attribute` name), not `m_EditorCurves`.
* Finger names `LeftHand.Index.1 Stretched` → `Left Index 1 Stretched` (explicit mapping, `muscles.clip_attr_to_muscle`).
* Missing finger curves take the value from `proxy_hands_idle`, **not 0**; missing body curves take `stand_still`; missing curves in additive clips take 0.
* Each entry is `{id, source, clip, frame, time, group, kind, muscles[95], root_t[3], root_q[4],
  builtin_params, moved_regions, tags, additive, …}`.
* Offline `moved_regions` = muscle groups with |Δ vs baseline| > 0.1 → body regions (I10); T-27 additionally computes bone-rotation differences in Unity and writes
  `moved_regions_bones`.

### One measured correction

04 T-26 says “each clip has 49 muscle + 7 Root curves, matching the number of `genericBindings`”; this does not hold in general:
`genericBindings` can contain **constant bindings** with no float curve (in this project's proxies, several each with `attribute==1/2`).
The criterion was changed to equality of the muscle **index sets** — all 79 proxy clips pass (`attribute == muscle index + 42`).
Count mismatches occur only for `proxy_land_quick 96/100`, `proxy_landing 96/100`, `proxy_sit_down 130/131`;
selftest reports them as `[note]` and does not fail.

### Where the 95-name order comes from

In Unity 2022.3.22f1, `HumanTrait.MuscleName` lives in native code and is not reachable from C#; this table was set-proven against 79 proxy clips using
`genericBindings[].attribute == muscle index+42` (re-run on every selftest).
The table content matches Kafe_CVR_Mods `GrabbyBones/MuscleData.cs`; the order of finger 1,Spread,2,3 is determined by
`HumanBodyBones` (Proximal/Intermediate/Distal) × the DoF order of `MuscleFromBone`.

---

## Pose × state plan (T-29; implemented in `pose_plan.py`)

Reads `decl.json` + `pose_library.json` + `inventory.json` + `pb.json` + `pose_timing.json` (measured by T-27;
falls back to defaults 0.2/5.0/0.7 s when absent), and per 03 §8.4 decides “which (state, pose, PB mode) frames to run, which parts to measure, how many seconds to spend,
how many batches”. **Plans only, does not measure**; does not modify the project.

```bash
python3 perception/pose_plan.py --selftest                    # Project A + fake pose_timing
python3 perception/pose_plan.py --project <工程根>              # writes <工程>/_感知/out/
python3 perception/pose_plan.py --project <工程根> --out <目录> --total-budget-min 20
python3 perception/pose_plan.py --project <工程根> --pass1 <poke_patches.json>
```

* **Pairing**: pair only when `moved_regions(pose) ∩ covers(part) ≠ ∅`. `covers` (`LeftUpperLeg/Hips/…`) is mapped via
  `COVER_TO_REGIONS` to the `moved_regions` vocabulary (`thigh/knee/…`); **`Hips` counts as both `thigh` + `spine`**
  — otherwise `MMN.pants` (covers only Hips/Spine) would miss the sitting pose (`B_combo_sit`). Poses listed in the declaration's
  `parts[].pose_scope.include` are added unconditionally (`kaguya.sailor` forces `proxy_stand_still`/`proxy_sit`).
* **States**: enumerate each part's relevant dimensions from `menu` (outfit/slot/ctl) (its own visibility ∪ visibility of other parts in the same region ∪
  dimensions referenced by writer conditions), and partition into equivalence classes by “set of visible parts in the same region + set of active writers”; then run a **greedy set cover** over all
  (part, equivalence class) pairs to get as few global representative states as possible. Invisible parts and parts with no paired pose take no state.
* **Two passes**: pass 1 = Library A + Library B@100% (incl. 6 combos) + Library C extreme frames; pass 2 = Library B@{25,50,75}, **only for
  (part, joint) hit by `--pass1`** (also accepts a `poke_patches.json`-style list, mapping `region` back to joints).
* **PB**: `both` only for parts with PB (`pb.json.parts[part].has_pb` or declaration `parts[].pb`), all others `rigid`.
  When `pb.json` has no parts mapping it **does not guess**; it logs a warning and uses `rigid` for everything (Project A's T-30 is empty because the avatar root was inactive).
* **Budget**: per-frame cost = stabilize + settle (for settle frames) + bake × number of visible parts in that frame; priority
  Library A(0) > B@100(1) > C(2) > pass-2 lower levels(3); when `--total-budget-min` >0, truncate from lowest priority up,
  each batch ≤ `--budget-min` (default 20 min, R6). Outputs `request_pose_<n>.json`, `pose_plan.json`
  (per-part table + state table), `pose_plan_skipped.json` (truncated items deduplicated by (part, pose)).

### selftest criteria and current output (2026-09-19)

① per-part table has 48 parts; ② `kaguya.sailor` has no B_hip/B_knee sweeps and `include` takes effect; ③ `MMN.skirt`/`MMN.pants`
are paired with `B_combo_sit` + hip forward flex; ④ pass 2 is driven only by the fake pass 1 (`MMN.pants×hip_fb`, `MMN.socks×knee`), 0 parts not hit;
⑤ the budget cuts C first, then B (when cutting only C, B/A=0; when also cutting B, A=0).

```
[2] kaguya.sailor：covers=['Chest','UpperChest','Spine'] regions=['chest','spine','upperchest']
    趟1=170，无 B_hip/B_knee=True，含 proxy_sit=True
[3] MMN.skirt/MMN.pants 配坐姿：True / True（B_combo_sit=True）
[4] 趟 2（假趟 1: MMN.pants×hip_fb, MMN.socks×knee）：
    MMN.pants 趟2 6 条：B_hip_fb_L_25, B_hip_fb_L_50, B_hip_fb_L_75, B_hip_fb_R_25, …
    MMN.socks 趟2 6 条：B_knee_L_25, …；MMN.skirt 趟2 0 条（应为 0）
[5] 预算压缩：A=32984.8s B100=1517.1s C=25980.8s，帧 18329
    预算 34502.4 s：砍 C=7761 B=0 A=0     预算 32984.9 s：砍 C=7761 B=939 A=0
    预算 10 min：帧 112，批 1，砍 18217 帧（C=7761, B100=939, A=9517）
[汇总] 状态 73（覆盖需求 132）、趟1 姿势 285、帧 18329、估算 60482.7 s、批 51
ALL PASS
```

### Two measured deviations from 03/04 (reported by T-29, for T-31/T-19 scheduling)

1. **Library A has 155 entries, not “≈33”**: T-26 put all 79 SDK proxies into A (85 tagged `library_a_pose`
   + 70 untagged), plus CERP expanded frames. The full pass 1 on Project A is **18329 frames / ≈16.8 h**,
   ~90× the “200–250 frames” in §8.4; truncation with `--total-budget-min` is **mandatory**; 20 min covers only 233 frames (≈1 state).
2. **`pb.json` has no parts**: T-30 skipped the inactive avatar root for Project A, so `both` has nowhere to go; until T-27's
   `pose_timing.json` is produced, default timings are used — the numbers are for ordering only, not a commitment.

---

## Declaration draft generation (T-04; implemented in `decl_draft.py`)

Drafts `<工程>/_感知/声明.yaml` from **facts readable in the project**; a human only fills in the `human:` items.
Principle: **vendor writers are always `confidence.correct: unknown`; mechanisms we are unsure about are marked `human:`, never invented.**
Sources (03a §Q1-⑤ S1–S9):

* **S1 generator tables**: `OUTFITS/OUTFIT_HIDE/PARTS/ACCPARTS/HEADPARTS/HAIRS/
  EARTAILS/HALOS/HEADDRESSES/PART_SHAPES/CHEST_PARTS/VENDOR_CLIP/VENDOR_ALT/CONFLICTS` in `MenuGen*.cs`
  + `Suppress`/`ShowInRange` calls.
* **S2 scene/prefab**: MA ShapeChanger / BlendshapeSync / ObjectToggle (reusing `writers_static`).
* **S3 vendor clips**: curves of the `<件> ON/OFF.anim` pointed to by `VENDOR_CLIP`.
* **S7 T4 `params.json`**: parameter defaults (the `menu` section still follows the generator tables).
* **S9 base-avatar profile/fragments**: `Kaguya.yaml` (baseline/key classes/vendor conventions/alt_pieces), `*.decl.yaml`.
* **T-05 inventory**: `inventory.json` (covers/closed/toggle method/renderer path).

```bash
python3 perception/decl_draft.py --project <工程目录> --out <草案.yaml> \
        [--profile <素体档案.yaml>] [--inventory <inventory.json>] [--params <params.json>] \
        [--scene <场景.unity>] [--menu-gen <MenuGenA2.cs>]
python3 perception/decl_draft.py --selftest        # draft for Project A and compare with the human-written declaration (read-only on project)
python3 perception/decl_draft.py --selftest-blind  # blind-draft rehearsal (old sources from git show ceb4070b^, read-only git)
```

Temporary files are written to `_长程任务_20260918/派工/tmp/ai/`; `--selftest` also calls `decl_validate.py` to validate the draft.

### selftest criteria and current output (2026-09-19; C-K added the strict metric; CK2 implemented the six B-T04b rulings)

`--selftest` drafts from the real Project A, then runs `decl_validate.py` and compares against the human-written declaration
(read-only on the project, writes only to `派工/tmp/`). **Acceptance metric** (04 §T-04, signed off in B-T04):
the draft passes `decl_validate.py` with **0 errors**; `parts` coverage ≥90%; D1/D3/D4a/D6 consistency
≥80% under both metrics — metric A (old) = kind + target overlap; metric B (strict) = kind + **identical target sets**
(by object path) + same when + same expect (including the normalizations in the table below and the exclusions from the CK2 rulings).

Basis for judgement (CK ruling 1, written into the acceptance metric): **the draft reads only project facts, never its own downstream products**.
After B-T07a moved generator tables/layers into `_感知/声明.yaml`, facts such as `PART_SHAPES`, `CHEST_PARTS`/
`SK_NIPPLE` and the three `SuppressBoolGated` no longer exist in `MenuGenA2.cs`/the scene/clips;
the only things still stating them are `Gen/Clip/Decl_*.anim` and `gen_writers.json` — which are **downstream** of this declaration,
so reading them would be copying the answer. Hence these 5 entries are recorded as `human_only`, are **not in the strict-metric denominator**, and are counted on a separate line:
`RePoppin.shirt_under_parker`, `工程A.default_hat_hides_added_ear`,
`工程A.head_acc_hides_ears`, `工程A.hood_hides_head_items`,
`kaguya.nipple_hidden_when_chest_covered` (the list is the data constant `decl_draft.HUMAN_ONLY_IDS`,
not written into the comparison logic). Identification uses the declaration entry's own `origin`/`human_only` fields, falling back to scanning
`source`/`note` for migration markers; entries on the list that cannot be identified in the declaration are named in selftest as “Claude needs to
add the marker” — no guessing. Counter-evidence: `--selftest-blind` (old sources at `ceb4070b^`) hits 3 of them — it is not that the draft
cannot write them, but that B-T07a deleted these facts from the current sources.

```text
[selftest] draft -> .../派工/tmp/ai/draft_工程A.yaml（parts=58 deps=16 includes=2）
[selftest] decl_validate(draft): OK（0 error）
  件覆盖 40/42 = 95.2%（阈值 90%）
  kind  A 人写          A 草案          B 人写          B 草案
  D1    3/3           4/4           3/3           3/3
  D3    3/4           3/3           2/3           3/3
  D4a   2/3           2/2           2/2           2/2
  D6    4/7           4/4           1/3           2/4
  A 旧口径：人写命中 12/17 = 70.6%；草案命中 13/13 = 100.0%
  B 严格口径：人写命中 8/11 = 72.7%；草案命中 10/12 = 83.3%（均阈值 80%）
  human_only（迁移，不计分母）5 条：RePoppin.shirt_under_parker 工程A.default_hat_hides_added_ear 工程A.head_acc_hides_ears 工程A.hood_hides_head_items kaguya.nipple_hidden_when_chest_covered
  被取代（不计分母）1 条：MMN.socks_foot_flat
  pending_cleanup（不计精确率分母）1 条：d1.kaguya_outer_sailor_shrink
  草案佐证（计入命中）0 条：—
  未命中且未分类（非迁移/非取代，逐条交 Claude 裁决）：工程A.holeheel_foot_hiheel 工程A.holeheel_hides_shoes 工程A.holeheel_shown
[FAIL] 覆盖率或一致性未达标
```

> **The current working tree still has 3 uncommitted HoleHeel declaration entries from 2026-09-19**
> (`工程A.holeheel_{shown,hides_shoes,foot_hiheel}`, being done in A-工程A-15/CL);
> the draft has no corresponding rule yet, so they fall into “missed and unclassified”. Removing these 3 (back to CK's 14-entry human-written set),
> the strict metric is **human-written 8/8 = 100%, draft 10/12 = 83.3%**. Their source has no migration marker,
> so they are not a B-T07a migration and, per ruling 1, are not added to `human_only` — the list goes to Claude for a ruling, no guessing.
> The per-entry differences and evidence for CK's 9 entries are in `_长程任务_20260918/派工/tmp/ck/diff_9.md`.

#### Comparison rules of the strict metric (merge only when semantically equivalent but textually different; target sets must still be identical)

1. **cases expansion**: for a dep with `cases:`, each non-`dont_care` case's `(when, expect)` is a comparison
   unit; `else`/`dont_care` do not participate. Human-written entries often put guards in `cases` with top-level `when: true / expect: null`.
2. **when boolean normalization**: top-level `|` splits into a disjunction set, `&` within a clause splits into a sorted atom set, redundant parentheses removed,
   `and`→`&`, contents of `{...}` sorted. `vis(a) and vis(b)` ≡ `vis(b) & vis(a)`,
   `outfit in {B,A}` ≡ `outfit in {A,B}`.
3. **when disjunction coverage**: human-written `A|B` can be jointly covered by two draft entries `A` and `B`; conversely, a draft entry counts as a hit if it is contained in some human-written entry's
   disjunction set. **Each covering entry must still have identical kind / target set / expect**.
4. **expect normalization**: `100` ≡ `100.0`; omitted `tol` ≡ `tol: 0.5` (schema default); other keys
   (`class`/`deleted`/`hidden`/`shown`…) are compared as-is, never dropped.
5. **Part-class alias (CK ruling 2)**: the vendor base avatar's bundled outerwear toggle clip **contains both keys
   `outer_shlink` and `outer_shrink` in the same clip**, while the profile's `key_classes.shrink` only lists
   the latter. `shlink` is the vendor's spelling and is treated as an alias, synonymous with `shrink` when filling `expect.class` (consistent on both the draft-generation
   and comparison sides); evidence: that clip (both keys have curves at each level).
6. **Part identity by object path (CK ruling 3)**: target `part: <id>` and `vis(<id>)` in `when` are first resolved via
   each declaration's own `parts[].objects[].path` (normalized root-relative paths) into path sets before comparison;
   different id text with the same paths means the same part (human-written `Kitty.shirt_a` ≡ draft `Kitty.kaguya_shirt_big`).
   Fall back to the id text only when the id cannot be found in the declaration.
7. **Visible-part filter (CK ruling 5)**: before comparing targets, use the `outfit` show/hide relations in the declaration to remove from both sides the parts that are
   **necessarily invisible** under the when condition (hood-type “invisible parts are not listed”). Conservative: remove a part only if it has an explicit
   outfit level and every disjunctive clause of when restricts outfit to levels disjoint from it (and there is no `vis(<that part>)`);
   keep it when unsure. **Known limitation**: only outfit levels are used; the `ctl(...)` toggle layers are not modeled, so it is slightly coarser than the human-written
   semantics (e.g., `Kitty.cat_ear`, kept by the human in the hood entry, gets removed because of the outfit=Kitty level);
   that entry is `human_only`, so the current numbers are unaffected.
8. **Superseded entries are not in the denominator (CK ruling 4)**: when a later human-written entry has `supersedes: [earlier entry]`, the earlier entry
   (`MMN.socks_foot_flat`) is not in the strict-metric denominator.
9. **Migrated entries are not in the denominator (CK ruling 1)**: see “Basis for judgement” above; the 5 `human_only` entries are counted separately.

**Two draft-side items (CK ruling 6)**: the old redundant SC in the scene awaiting cleanup (`d1.kaguya_outer_sailor_shrink`,
being cleaned by A-工程A-12) is marked `pending_cleanup` and is not in the precision denominator (`PENDING_CLEANUP_IDS`, marked on
`note`; the schema has no such field); an extra draft entry whose when is equivalent to some `human_only` migrated entry and whose
targets overlap ≥80% (Jaccard) is recorded as “draft corroboration” and counted as a hit; otherwise it is listed separately. Project A currently has no corroborating
entries — the whens of `d6.layer_1/2` (`ctl(hair)`/`ctl(head)`) are not equivalent to any of the 5 migrated entries, so they are listed separately.

* `--selftest-blind`: drafts from the old `MenuGenA2.cs` + scene at `git show ceb4070b^`;
  `MMN.socks_foot_flat` still appears with `when='vis(MMN.socks)'`, alternative jackets carry a `human:` note,
  and the draft passes validation with 0 errors — this corresponds to **E11 blind drafting** (full version done in T-16). The old sources can also produce
  `d4a.RePoppin_shirt_Parker_on` / `d6.layer_4/5`, which is counter-evidence for “migrated entries cannot be automated”.
* **Known trade-offs**: the T-05 inventory exports only SMRs, not MeshRenderers; PixelBoot's `windowA–E` are inside a prefab
  instance and their full paths are unavailable, so such selectors are recorded in the draft header as “unresolved selectors”. Vendor writers'
  `correct` is always `unknown` and needs a human judgement. Fragment parts `frag_parts` now keep `slot/fit/covers/toggle`
  (from `开发工具/素材包说明/*.decl.yaml`), so rules that aggregate by slot no longer miss fragment parts.

---

## Declaration validation (T-02; implemented in `decl_validate.py`)

```bash
python3 perception/decl_validate.py --selftest                 # positives 8/8, negatives 250/250 (about 2 s)
python3 perception/decl_validate.py --selftest --mini-yaml     # same batch, forced through the bundled YAML parser
python3 perception/decl_validate.py --in <声明.yaml> [--report json]
python3 perception/decl_validate.py --in <声明.yaml> --out <工程>/_感知/decl.json
python3 perception/decl_validate.py --in <声明.yaml> \
        --profile 开发工具/素体档案/Kaguya.yaml \
        --inventory <工程>/_感知/out/inventory.json \
        --pose-library <工程>/_感知/out/pose_library.json
```

Validation order is aligned with `schema/CONDITION_GRAMMAR.md`: **YAML load → schema (if it fails, the semantic layer is not run, §8) →
includes merge → SEM-01…SEM-24 → expand decl.json**.

### Full base-avatar key table (task AQ; implemented in `profile_keys.py`)

The “body key exists” check that SEM-07 needs should not look only at `key_classes` (that is the subset T-17 has classified); it should come from the body mesh itself.
The T-05 inventory now outputs `body_keys` for each avatar, and this script writes it into a new profile section `all_keys:`:

```bash
python3 perception/profile_keys.py --inventory <工程>/_感知/out/inventory.json \
        --profile 开发工具/素体档案/Kaguya.yaml
python3 perception/profile_keys.py ... --force     # force overwrite when all_keys already exists and differs
python3 perception/profile_keys.py --selftest      # temp files, does not touch the repository
```

* Touches only the `all_keys:` section: the first time it is appended to the end of the file; if it already exists it is replaced exactly as “top-level line + the indented lines following it”;
  all other bytes and YAML comments are left untouched; key order = mesh order; repeated runs are byte-identical.
* If it exists and differs from the inventory: by default it **only reports the difference and does not overwrite** (exit code 2); only `--force` writes — profiles are edited by several people,
  and a silent overwrite would wipe keys added by hand.
* Avatar selection: `--avatar` first; otherwise match the profile's `mesh` against the inventory's `body_path` (or the path basename); otherwise take the first
  avatar that has `body_keys`.
* Does not depend on PyYAML (reads `mesh:` and `all_keys:` line by line); SEM-07 recognizes `all_keys` only if it is a list; an empty list means
  “the body really has no keys”.

### Loading and fallbacks (trade-offs)

* **Use PyYAML when available**: `SafeLoader` keeps YAML 1.1 `on/off/yes/no` booleans and bare `1.06` floats,
  and only **removes implicit timestamp resolution** — `2026-09-18` is always loaded as a string (otherwise every schema `date` breaks).
  So bare dates/bare `1.06` remain a trap for readers: always quote strings in declarations.
* **Without PyYAML, fall back to the bundled `_MiniYaml`**: covers only the subset used by declarations/fragments (comments, block mappings/sequences, inline and
  multi-line flow, quotes and `\"` escapes, YAML 1.1 scalars); no anchors/tags/multi-document/multi-line scalars `|`/`>`.
  This path is self-verified every time by `--mini-yaml --selftest`, currently 8+250 all pass; no guarantee for YAML beyond declarations.
* **Use jsonschema when available** (Draft 2020-12); when absent the schema layer reports `SKIPPED`, `--out` does not write decl.json,
  and only the semantic layer runs. Error paths are normalized per §8: `context` is expanded recursively to the leaves, `required` adds the missing name,
  `additionalProperties` adds the extra key, `propertyNames` adds the offending key name.
* **Pose library**: automatically looks for `<工程>/_感知/out/pose_library.json` based on `avatar.project` (also accepts
  `*<project>*/_感知/out/`); if not found, checks ids and tags against the built-in list in GRAMMAR §3 (SDK 79 + GoGo 7+3 + Library B 66+30
  + GM 16). Project-private clips cannot be checked offline and only produce warnings.

### Semantic rules (GRAMMAR §5) and “skipped is not pass”

SEM-01…SEM-24 are all implemented, with error paths per the §5 table; standalone fragment validation only runs the rules decidable within the fragment
(SEM-01/02/03/04/05 (except mesh)/06/09/10/11/13/19), with error paths in the fragment itself; when included by a declaration,
fragment errors are reported as `/includes/<i>/fragment#<片段内路径>`, and invalid fragments are not merged.

* **SEM-07 (base-avatar profile) / SEM-12 (T-05 inventory) depend on external data**: without `--profile` / `--inventory`
  their status is **skipped** (not pass), listed separately in the report.
  **SEM-07 two-level metric** (task AQ): when the profile has `all_keys:` (the full body-mesh key table written from T-05 `body_keys`),
  a key **missing** on a body-mesh target in the declaration → **error**, and `key_classes` is only used for classification; without `all_keys`
  the old metric holds — a missing key is only a **warning** (base-avatar profiles have no schema yet, see CHANGELOG “Open issue 2”), with existence
  taken from `key_classes` + `baseline` + `keys`. SEM-12 only checks whether `objects[].path` is in the inventory, whether `type`
  matches `renderer` (smr/mesh), and whether `submesh` is less than the number of material slots; it does not skip because of `part_like`.
* **SEM-21 only warns** (fit is closed/tight but covers is empty); ok examples may have warnings but not errors.
* **SEM-22 expectation conflict** is the only rule that enumerates states: group by (mesh, key), **enumerate all dimensions per §6.1**
  (Cartesian product of `outfit/slot/ctl/axis/param/pose`; measured state counts: 工程A_min 8064, 03a_工程A
  6720, 03a_milfy 1040, 03a_project-c 256, 03a_h3 3); visibility uses E from §2.2 (including the single-pass hidden/shown
  correction); each dep is evaluated one by one, no pruning. Only when the state count is >500k does it fall back to “enumerate only the dimensions used by this group of deps”
  and note so in the report (none of the current examples trigger it). It compares interval types (`value±tol`, `range`, that key in `values`, `baseline±0.5` when a profile
  is present) and explicit `class`; on a hit it reports at the `/deps/<j>/id` that comes later in expansion order. Sampling of continuous dimensions
  per §6.1 (critical points + midpoints between neighbours + bounds; default `{0, 0.5, 1}` when there are no constants; body axes additionally union in `samples`).
* Deps superseded via `supersedes` do not enter the expectation matrix; they are kept in `decl.json` with `superseded_by` added.

### decl.json (deterministic)

`json.dumps(..., ensure_ascii=False, sort_keys=True, indent=2)`; arrays sorted by id. Expansion per §6:
includes merge (local ids get the `<as>.` prefix; conditions/target/alt_of/expect_by_leader keys are rewritten accordingly;
`objects.path` is prefixed with `mount/`; fragment parts are written into the include's outfit; fragment deps missing else get `dont_care`),
geo_defaults generates `geo.<件>` / `.opening` / `.poke` (regions computed per leaf; hand-written entries with the same id override generated ones),
supersedes annotation, defaults made explicit (`when`, `else`, `tol`, `poses`/`render`/`geo_defaults`/`roundtrip_default`),
each entry carries `origin` (generated items carry `generated_from`). The same input yields byte-identical output twice (selftest compares every positive example).

### selftest criteria

The first three lines `# rule:` / `# layer:` / `# expect_error_path:` are the criteria: `layer: schema` requires rejection by the schema
with the expected path ∈ the normalized path set; `layer: semantic` requires the schema to pass first, the semantic layer to **hit only the one
SEM rule named in the header comment**, and the expected path to be reported. Current output:

```
ok files: 8  ok failures: 0   bad files: 250  bad mismatches: 0
ALL PASS
```

---

## Checker (T-14; implemented in `verdict.py` + `rules_universal.py` + `thresholds.yaml`)

The declaration says “how it should be”, T1/geo/writers say “how it actually is”; this tool reconciles them and attributes causes — it is the core of judging “without looking at images”.
It **expands the expectation matrix independently** (does not read `gen_writers.json`, only uses it for attribution); when an input is absent, the corresponding judgement degrades to `no_data`
and is listed separately, **never reported as pass**.

```bash
python3 perception/verdict.py --selftest                 # self-verify on in-repo Project A data (83 states)
python3 perception/verdict.py --selftest --out <工程>/_感知/out/verdicts.json
python3 perception/verdict.py --decl <工程>/_感知/decl.json --t1 <T1 目录> \
        [--profile 开发工具/素体档案/Kaguya.yaml] [--geo <geo_*.json|目录>] \
        [--writers writers.json] [--ma-analysis ma_analysis.json] \
        [--fx-final fx_final.json] [--mapping mapping.json] \
        [--inventory inventory.json] [--pb pb.json] [--key-follow key_follow.json] \
        [--thresholds perception/thresholds.yaml] [--out verdicts.json]
python3 perception/verdict.py --diff a.json b.json       # diff two runs
```

### Expectation and judgement forms (aligned with schema `outcome`)

`baseline`｜`dont_care`｜`{value, tol}`｜`{range}`｜`{values}`｜`{class}`｜`{sync}`｜`{hidden|shown}`｜
`{deleted}`｜`{variant}`｜`{geo}`｜`{grab}`｜`{not_written}`｜`{no_writer_other_than}`｜`{pending}`.
Judgements can be `pass / violation / no_data / undecidable / unmatched / dont_care`; judgement coverage =
judged / (judged + undecidable), `dont_care` not counted.

### Degradation when dependent inputs are absent (hard requirement)

| Judgement | Needs | When absent |
|---|---|---|
| Key value/baseline/sync/visibility/variant/grab | T1 `state_*.json` | No T1 → no states to judge, report is empty |
| `not_written` / `no_writer_other_than` / U3 attribution | `writers.json` (T-11) | `no_data` (host not guessed) |
| `deleted` (Delete ratio) | T1 v4 V4 bucket/key-existence table (T-13) | `no_data` |
| `geo.*` / U1 static patches | `geo_*.json` (T-10/T-28a) | `no_data` (during the advisory period it does not enter the gate anyway) |
| U6 vertex count | T1 v4 | `no_data` |
| U7 | `pb.json` (T-30) | `no_data`; the rule itself only reports `info` |
| Frozen four-way split (frozen/frozen_meaningless) | `mapping.json` (T-12) | Degrades to exists/writes 0/does not exist; listed separately in the report |
| Winner attribution (MA section) | `ma_analysis.json` + `fx_final.json` (T-12) | Only reports the writer set and the static winner, marked low |

### Universal rules (independent of the declaration)

U1 static poke-through patches (T-28a, advisory) ｜ U2 two parts overlap <50% ｜ U3 no writer → back to baseline ｜ U4 grab points (hit count =
number of `hidden_materials` entries; `grab_point_lt_3000` only logged as info) ｜ U5 weight 0–100 ｜ U6 vertex count unchanged ｜
U7 PB colliders (`info`, attribution clue) ｜ **U-KF same-name key mismatch** (see below).

### U-KF same-name key mismatch (task AO spec)

Input `--key-follow` (T-05/AK inventory or key_follow JSON): a part carries a key with the same name as a body key, and **while the part is visible**
`|part value − body value| > threshold (thresholds `U_KF.mismatch_tol`, default 5)` → violation; iterates over all T1 states;
no overlap is recorded as `benign`, a part invisible in all states as `no_data`, and unresolvable part/key names as `unmatched` (no guessing).

**Direct call to AM (delivered)**: when `verdict.py` detects `perception/key_follow_verdict.py` it preferentially calls its
`load_states(t1_dirs)` + `build_result(inventory_path, t1_dirs, states)` (also accepts a custom
`analyze(key_follow, t1_dirs)`); only if the call fails or the module is absent does it fall back to this module's inline implementation (same criteria, see
`rules_universal.key_follow_verdict`). Findings carry a `source` field stating which path was taken
(`key_follow_verdict.py` / `verdict.py:inline`). The current selftest goes through AM: FootNail 21 states,
stocking 33 states, both `benign`.

**B-补-07 geometric weighting (BF rework)**: `key_follow_verdict.py` takes AY's `candidates[].geom`
(`AuditPartInventory.AttachFollowGeometry`). On a numeric mismatch it then looks at geometry:
if both `geom.body_piece_dist_mm.p50_delta_mm` (p50 of the part's nearest distance to the body surface, difference between body key 0→100) and
`geom.piece_key_disp_mm.max` (max vertex displacement of the part's own key 0→100) are < `GEOM_BENIGN_MM=1 mm`
→ downgrade to `benign_geometry`; either ≥ threshold → keep `mismatch`; `geom` absent/`available=false`/no comparable
values → **keep the numeric verdict** and mark `no_geometry=true`. The original numeric verdict is stored separately in `numeric_verdict`, geometry details
in `geometry` (including `geometry_source`). Thresholds come from measurement: Project D harness p50 constant 5.8 mm (delta 0)
→ benign_geometry; nipple pasties before the fix 5.74→14.95 mm (delta 9.21) → mismatch. The summary adds
`benign_geometry` / `no_geometry` counts; the table adds geometry columns and a `benign_geometry` section.

### Post-build rename fallback (when there is no `mapping.json`)

Source names in the declaration are matched to measured names by fallback; failures are recorded as `unmatched`: paths are normalized by stripping `$<n>` suffixes and mapping `$`→`/`, then
matched as “declared segments are a subsequence of measured segments” (covers `_Outfit$Outfit_MMN_黑$164/Shoes`, `$$AAO_AUTO_MERGE_SKINNED_MESH_n`);
key names are matched level by level via `AAO_Merged_<键>_<n>`, `<n>_<身体名>__<键>`, `__<键>`, `_<键>`. Ambiguity means `unmatched`.

### Visibility attribution: cannot attribute → `undecidable` (B-补-12, BF rework)

The `when` of `dep.when` and of `variant` options are both evaluated with **T1 measured visibility** `sv.eval_vis()`, not inferred from toggle values
(AO lesson 3). Measured visibility is computed under three “attributable” rules (`StateView._resolve_parts`):

1. **Standalone renderers**: part visible = any of its own renderers is `visible`;
2. **Hits only AAO-merged meshes**: AAO only merges meshes with identical activeness animation; decidable only if the hit chunks have consistent visibility;
   some chunks visible and some not (e.g., in the fully-undressed state `Kitty.shirt_a/b` hits `..._0` visible, `..._1` invisible) → cannot attribute;
3. **One part, multiple objects**: inconsistent conclusions across objects also count as cannot attribute (e.g., `RePoppin.parker`'s `(A)Parker` invisible,
   the tie `(A)Necltie` visible — “any object visible” would treat the tie as the jacket covering the chest).

**Cannot attribute lands only in `undecidable`; it is forbidden to judge pass/fail as if invisible** (BF rework, replacing AX's “`vis()` returns
False and goes to `else`”): `vis()` still returns False, but `verdict.py` passes `sv.vis_unknown()` to
`rules_universal.eval_decl_dep(..., unknown=...)`, and conditions are evaluated in three-valued logic (`eval_cond_3`) —
any `vis`/`chain` True→True, otherwise any unknown→`None`, `not/and/or` short-circuit per Kleene.
When `when`/`cases.when` evaluates to `None` it returns `UNDECIDABLE` and `judge` lands on `undecidable`; baseline/show-hide/variant judgements that compare
`visible(pid)` directly also check `vis_unknown()` first. The report adds an
“undecidable list” (`summary.undecidable` + `summary.visibility_unknown`); parts that cannot be attributed
appear only there — no vanishing without a trace. Effect (Project A 83-state selftest): `kaguya.nipple_hidden_when_chest_covered`
in the 4 fully-undressed states (KittyA/B, RePoppin, RePoppinHood), 3 rows per key for all three keys, lands in `undecidable`; `Kitty.shirt_a/b`,
`kaguya.outer_big`, `RePoppin.parker` appear in the undecidable list; `kaguya.outer_variant_by_bust`
is `undecidable` in all 83 states because `kaguya.outer_big` in its group cannot be attributed (a data gap, no longer judged by assumption). The real defect
`Kitty.base_panties_hidden` (12 rows) is unaffected.

### selftest criteria and current output (2026-09-19, after BF rework)

`--selftest` runs on Project A's `t1_full_probes` (83 states) + the T-03 declaration and asserts:
jacket off, 14 states, three keys pass; MMN post-fix four combos pass; grab points/overlap U2/U4 0 hits; **B-补-12 cannot attribute
lands in `undecidable` (KittyA/B, RePoppin, RePoppinHood: 3 `undecidable` rows for each of the three nipple keys; the related parts are in the
undecidable list)**; each item on the 03 §4.5 negative-sample list is 0 (with all shoes/socks off the foot-shape keys are not written; **Parker invisible writing 100
is harmless — B-补-13 iterated over 57 measured samples + synthetic samples to prove the criterion is not vacuous**; Kitty/RePoppin have no body keys; 83 states
grab/overlap 0); and prints judgement coverage, the `no_data` list and the `undecidable` list. Current: 8705 judgement rows,
pass 2514 / violation 12 / undecidable 4311 / dont_care 1878, coverage 37.0%. All 12 are
`Kitty.base_panties_hidden` (should be reported while T-06/T-07 are not landed); the 14 nipple-key/tie rows are, after B-补-12,
no longer violations but land in `undecidable` as cannot-attribute.

### Re-running the replay positive samples (after T-16)

When T-14 was delivered, the T-15 replay library and that T-16 Play run had not been done, so “all 4 positive samples are violations with correct
`writer_blamed`” is still missing. How to re-run (executed by Claude at T-16):

1. `replay.py apply --all` → re-run the generator → enter Play and capture T1 v4/geo/intercepts → exit Play;
2. `python3 perception/verdict.py --decl <工程>/_感知/decl.json \
      --t1 <修前 T1 目录> --geo <修前 geo 目录> --writers <writers.json> \
      --ma-analysis <ma_analysis.json> --fx-final <fx_final.json> --mapping <mapping.json> \
      --key-follow <key_follow.json> --out <工程>/_感知/out/verdicts_before.json`;
3. `replay.py revert --all` → run the same batch again, writing `verdicts_after.json`;
4. Criteria: in `verdicts_before` all 4 replayed defects are `violation` with the correct `writer_blamed.winner`;
   `--diff verdicts_before.json verdicts_after.json` shows the 4 disappearing and 0 violations after the fix.

### To do (T-32 pose additions)

Add pose/pb dimensions to the expectation matrix, read `pose_*.json`/`poke_patches.json`, PB interpretation table (✗/✓ info, ✗/✗ violation,
✓/✗ `pb_induced`), classify `static_grown`/`opening_deep`/`pose_changes_state` as advisory, add pose ids to `waivers`
— wired incrementally per T-32; currently the U7 and `waivers.pose/pb_mode` fields can be read in but do not take part in judgement.

---

## key_follow blind-spot check (B-补-06; implemented in `key_gaps.py`)

`key_follow` only checks “the part **carries** a key with the same name as a body key, but nobody drives it”. It is inherently blind to two other kinds of blend-shape defects:

* **Key missing on the part**: Project D Rurune-Black shoes missing the flat-foot key (B1), pasties missing `Breast_small` / `Breast_big(limit)`
  (B2/B3);
* **Writer attached to the wrong part**: Project A MMN flat-foot key attached to the socks (A3), Project B lop-eared bunny's 11 shrink keys attached to the whole-outfit root (R1).

`key_gaps.py` adds these two checks using the offline inventory (`审查产出/key_follow/<工程>.json`); read-only, does not launch Unity:

```bash
python3 perception/key_gaps.py --inventory <...>/COMM-xxx.json [--out gaps.json] [--md gaps.md]
python3 perception/key_gaps.py --all <key_follow 目录> --out gaps_7.json --md gaps_7.md
python3 perception/key_gaps.py --selftest
python3 perception/key_gaps.py --requests     # print the list of requirements for AuditPartInventory
```

Criteria (all `advisory`, need human judgement; after the BF rework **covered regions follow the inventory's `covers`**):

* **Covered regions**: `foot` → `LeftFoot/RightFoot/LeftToes/RightToes`; `bust` →
  `Chest/UpperChest/Spine`. Parts with `covers=Other/unknown/empty` **do not take part in judgement** and go separately into
  `unknown_cover` (they get concrete regions only after the MA MergeArmature covers mapping of B-补-18 is re-exported).
  The part slot (path/name token) is used only for `unknown_cover` grouping, no longer as a basis for judgement.
* `missing_key`: for each written body key K that “has a part-level host, and that part really covers the key's region”, any part covering the same region that is
  neither a host of K nor in `synced`/`candidates` is reported as missing the key (a key present on the part but written by nobody belongs to key_follow).
  If there is no “part-level host covering that region”, nothing is reported, to avoid flagging every part that never needed the key. The body renderer
  (`body_path`) does not count as a “clothing part that should carry the key”.
* `misplaced_writer`: **reports only cases where no host is on a part covering the key's region** — ① the host is an **ancestor/root or
  MA control object** (path is not a renderer) → misplaced (R1, confidence=high); ② none of the host parts cover the
  key's region while some host part covers another known region → that host is misplaced (A3, confidence=mid); as long as one
  host is on a covering part, the key is considered to be in the right place and no misplacement is reported for other hosts of the same key (avoiding the “the socks need this key too”
  false positive). Hosts with unknown coverage are not reported and are listed separately. All three output tables are **sorted by confidence high→mid→low**.

`--selftest` gathers evidence two ways: ① a hand-written minimal fixture (with covers) exactly reproduces B1/B2/B3/A3/R1, the negative sample
(key on both shoes and socks) gives 0 false positives, `unknown_cover` is listed separately, confidence ordering holds; ② real data with “fixes undone” — the existing
inventory is the **post-fix version and covers is still Other**; offline there is neither a pre-fix inventory nor the ability to re-run Unity, so on
real Project D/Project A/Project B data: first fill in covers in the shape expected after the B-补-18 re-export, then delete the known fixes
(`ugly_shoes`'s SC, the pasties' `Breast_small` host, MMN `Shoes`'s SC, the 11 shrink keys moved back to the whole-outfit root host)
as the pre-fix equivalent; B3 is pre-fix already. All 5 cases hit, and Project A post-fix `MMN/Socks` is no longer reported as misplaced.

### Why it is currently 0/0 (covers unknown) and re-verification after B-补-18 takes effect

Running `key_gaps.py --all` on the current 7 orders (old inventories, covers still all `Other`) gives
`missing_key 0 / misplaced_writer 0 / unknown_cover 354`. **This is not “no defects”**: part-level covered regions are
all unknown (`covers=['Other']`), so neither the `missing_key` threshold “there must first be a part-level host covering the region” nor
the `misplaced_writer` criterion “the host part's coverage is disjoint from the key's region” can hold; every part is listed separately in
`unknown_cover` and not counted in judgement. 0/0 = “the tool by design refuses to conclude while coverage is unknown”, not clean data.

The MA MergeArmature covers mapping of B-补-18 **takes effect only after re-exporting the inventory with the new tools**. Re-verification steps and expectations:

1. Revert to pre-fix: `replay.py apply b1_rurune_flatfoot b23_esmera_nipple r1_lopear_shrink mmn_foot`
   (before apply/revert, pass the “stop if replay list files are dirty” gate).
2. `sync_audit.py` syncs the new tools into Project D / Project B / Project A; Unity batch-exports to
   `_长程任务_20260918/审查产出/key_follow_replay/` (commands in the step-by-step document below).
3. `key_gaps.py --all <该目录> --out ... --md ...`, then check per project whether `covers` is no longer all `Other`.

| Defect | Project · part · key | Expected category | Criterion read from data |
|---|---|---|---|
| B1 | Project D Rurune-Black shoes missing `Foot_heel_OFF…` | `missing_key` | Shoe `covers` includes Foot/Toes yet it is not a host |
| B2/B3 | Project D Esmera pasties missing `Breast_small` / `Breast_big(limit)` | `missing_key` | Pasties' `covers` include Chest/UpperChest/Spine |
| A3 | Project A MMN flat-foot key on socks | `missing_key` (shoes) **or** `misplaced_writer` (socks) | Read the exported `covers`: socks include Foot → shoes reported missing key; socks cover only the lower leg → socks reported misplaced. **Category not presupposed** |
| R1 | Project B lop-eared bunny 11 shrink keys on whole-outfit root | `misplaced_writer` (high) | Host is an ancestor/root, not any part covering that region |

A3's expectation is a criterion read from the exported inventory's `covers` (step 6 of the step-by-step document prints the actual covering parts and accepts
either category), not the fixture's assumption that “socks only cover the lower leg”. For the complete per-step commands see
`_长程任务_20260918/派工/tmp/bo/BF_B补06_replay步骤_修正.md`; BF's original
`tmp/bf/BF_B补06_replay步骤.md` had three errors — heredoc variables not expanded, missing dirty-tree gate, A3 expectation dependent on the fixture —
which BO has fixed (dry-run output in `_长程任务_20260918/派工/tmp/bo/dryrun_*.log`).

### B-补-06 requirements list: data to add to `AuditPartInventory` (for Claude)

1. **Per-renderer list of blend-shape names** (blendshapes that actually exist on the mesh) — to separate “key really missing on the part” from “key present but nobody writes it”
   at the renderer level; currently only approximated by the presence of `synced`/`candidates`.
2. ~~Covered regions of clothing parts~~ **Done (B-补-18, BF rework)**: `AuditPartInventory.RegionMapper` maps outfit bones to the avatar's humanoid bones via MA
   MergeArmature's `mergeTarget` + bone names (directly calling its `GetBonesMapping()`);
   but **the inventory must be re-exported** to get concrete `covers`; old data is still `['Other']`.
3. **Exact attribution of writer hosts**: `body_written_keys[].writers[].component_path` has only a path, which may point to the root/
   an MA control object; add “which renderer the component belongs to”, or add the transform hierarchy so offline analysis can determine ancestors.
4. **Mapping from part toggles to body-key trigger conditions** (on top of the existing `switch.sources`, add “which level needs the key =100/0”),
   used to judge conditional defects such as “main part (shoes) missing a writer”.
5. **Part slot classification**: still guessed from path tokens (`SLOT_RULES`), now used only for `unknown_cover` grouped display.
6. **Full base-avatar key table** (`all_keys:` in `开发工具/素体档案/Kaguya.yaml`, B-补-02) — to determine whether the body has the key.

---

## 90 strip self-check (T-23; implemented in `strip_audit.py`)

Before delivery, remove audit leftovers from the project and run a zero-leftover self-check (spec 04 §T-23 / work list B-T23):

```bash
python3 perception/strip_audit.py --project <工程根> --check      # check only, no deletion (exit code 1 = leftovers found)
python3 perception/strip_audit.py --project <工程根> --apply      # actually delete; ProjectSettings restored to --baseline (default HEAD)
python3 perception/strip_audit.py --selftest                      # full-flow self-check on a temporary fixture, does not touch real projects
```

* **Strip items**: `Assets/AvatarAudit/` (+`.meta`), the old `Assets/Editor/AvatarAudit/`,
  `Assets/ZZZ_GeneratedAssets/`, `Packages/nadena.dev.ndmf/__Generated/`,
  `Library/AvatarAudit/`, `com.coplaydev.unity-mcp` in `Packages/manifest.json` and `packages-lock.json`,
  and drift of `ProjectSettings/` relative to the baseline.
* **Report only, no change**: `_感知/` is at the project root and not among the 5 delivery items of SOP 90 (**not delivered with the project zip**, kept in git);
  audit components such as `AuditMappingProbe` in scenes/prefabs (build-time components; when found, their paths are listed for a human to handle).
  Note that in Unity YAML a MonoBehaviour only records `m_Script: {fileID: 11500000, guid: <脚本 guid>}` and
  **does not record the class name**, so the criterion is “first collect the guids of `Assets/AvatarAudit/**/*.cs.meta`, then search scenes/prefabs by guid”;
  and the search **must finish before the script directory is deleted** (`--apply` keeps a guid snapshot for the second scan); otherwise, once the script directory
  is deleted the `.meta` files are gone and leftover components in the scene can no longer be found. When **“running a separate `--check` after deletion”**, the working tree's
  `.cs.meta` have been deleted along with the directory, so guids are read from the git baseline instead (`git ls-tree` lists paths +
  `git -c core.quotepath=false show HEAD:<路径>.meta` reads contents); if neither the working tree nor the baseline yields them, it reports
  `undecidable` with a non-zero exit code, **never ok**. `--selftest` uses real-project guids and real MonoBehaviour
  YAML blocks as positive samples, asserting “after deleting the script directory the pre-deletion snapshot still hits, while re-collecting guids on the spot hits 0”, and **in a separate process**
  runs two cases: “`--check` after deletion” (guids recovered from baseline, still reports RESIDUE) and “no guid source → undecidable”.
  `Captures/`, `Assets/Editor/AvatarGen/` (cleanup items of SOP 90 step 1; the script only prompts).
* **Zero-leftover criterion**: after `--apply`, `--check` shows 0 strip items; tracked changes **outside the whitelist** in `git status` are 0
  (whitelist = paths this script deleted/modified). Measured on a copy of Project A: `--check` hit 6 items →
  after `--apply`, 0 leftovers and 0 tracked changes outside the whitelist.
* Does not launch Unity or modify other projects; `--selftest`'s copy goes in `_长程任务_20260918/派工/_scratch/` (gitignored),
  deleted in `finally`; nothing left in the working tree (it would be swept into the repo by `git add -A`).


---

## T-11 static rule candidates (E-T11-01; implemented in `static_rules.py`)

Runs 6 classes of rules offline over the existing `writers.json` to produce candidates, **no project rescan, no right/wrong judgement** (right/wrong needs geometry/build-time intercepts/human judgement;
03 §4.5 “static rule results do not go into the user table”):

```bash
python3 perception/static_rules.py --batch <审查产出/_历史工程> --md 静态规则候选.md   # batch
python3 perception/static_rules.py --writers <writers.json> [--md one.md --json one.json]
python3 perception/static_rules.py --selftest        # known samples on real data (Project A / Project B)
```

* **K1** multiple writers on one key (configuration-type ShapeChanger/BlendshapeSync/ObjectToggle, flagging whether values differ);
  **K2** Set/Delete coexisting on one key (in markdown rows, Delete writers are listed first and not folded into “…(+N)”);
  **K3** level/whole-outfit writers (`Dial_整套` or multi-state selectors in the same layer)
  competing for keys with per-part/per-region writers; **K4** shrink key targeting the body mesh (attached to the outfit root); **K5** foot-shape-key ShapeChanger
  ownership (sock/shoe token + `where` read-back); **K6** blend-shape target value out of range (only class_id 137, excluding property paths).
* **K5 sock/shoe ownership (acceptance E-T11-01 rework)**: after `writers_static` folds hosts to the outfit instance root they are indistinguishable
  (Project A MMN's Socks/Shoes both become `_Outfit/Outfit_MMN_黑`), so the writer's `where` =
  `<文件>:<行>` is used to read back that prefab/scene and resolve the name of the GameObject holding the ShapeChanger (stripped objects follow
  `m_CorrespondingSourceObject` to the source prefab; if the source is an `.fbx`, only `<文件名#fid>` can be given). When neither level yields the
  **real name**, the conclusion fields `sock_owner`/`shoe_owner` are always **undecidable** (`owner_unknown=True`); the “vendor prefab writer = socks, scene-added writer = shoes”
  inferred from the `where` file type goes only into `sock_owner_guess`/`shoe_owner_guess`
  (验收_20260919_BC至BH.md BG2: fallback guesses must not enter conclusion fields), and `owner_kind_source` records the source.
* `--selftest` verifies three positive samples on **real projects**: Project B lop-eared bunny's 11 `Shrink_*` attached to
  `08_WhitePink_Milfy_MA` (K4); Project B's `Foot` layer, 4 levels, competing with per-part SCs for keys (K3);
  Project A MMN flat-foot key in the **real pre-fix scene** (a hardlink shadow project at git `ceb4070b^`, not writers deleted by hand)
  marked `vendor_only=True` + `sock_owner_guess=True` + `owner_unknown=True` (“attached only to socks, not shoes” can only be a guess),
  while live gives `sock_owner_guess=shoe_owner_guess=True` and the conclusion is likewise undecidable.
  The shadow project goes in `派工/_scratch/` (gitignored), deleted in `finally`, nothing left in the working tree.
* **Trade-offs/blind spots**: GameObject names from `.fbx` sources cannot be read offline from the binary (MMN's Socks/Shoes are such a case);
  then only `*_guess` is given, never passed off as a conclusion; of the 31 K5 entries across 14 historical projects, 19 fall into this category (the other 12 are judged by real name);
  if semantic-level ownership is truly needed, go back to Unity (`LoadAllAssetsAtPath` + `TryGetGUIDAndLocalFileIdentifier` to map
  fileID back to object names) or read the FBX.

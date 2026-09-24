> 🌐 English translation · [中文原文](../../../../../../开发工具/通用工具/审查/perception/schema/CONDITION_GRAMMAR.md)

# Condition expressions, pose ids, round-trip sequences and semantic rules (perception/0.2)

> Companion to `perception-0.2.schema.json` (T-01, including the schema part of T-32). The schema governs structure, types, vocabularies, required fields and mutual exclusion; **this page governs what the schema cannot express**: the grammar (EBNF) of conditions and round-trip sequences, evaluation semantics and the expected-visibility model, pose id naming, semantic rules such as referential integrity (SEM-xx), expansion rules, and the conventions for counterexample header comments and error paths. The implementer is `decl_validate.py` (T-02). The change log is `CHANGELOG.md` in the same directory.
> Design source 03a Q1-①; `03_研究与方案.md` §3 correction list and §8 (v3, 22:30) are authoritative.

## 1. Condition expression EBNF

Used in `deps[].when`, `cases[].when`, `expect.variant.options[].when`, `waivers[].states`. The object of evaluation is a "state" = menu parameter vector + other parameters (VRChat built-in, vendor) + body-shape axes + pose (history is expressed by round-trip sequences and does not enter conditions).

```ebnf
cond          = disj ;
disj          = conj , { "|" , conj } ;
conj          = unary , { "&" , unary } ;
unary         = "!" , unary | primary ;
primary       = "(" , cond , ")" | atom ;
atom          = "true" | "false" | vis_atom | chain_atom | slot_atom | outfit_atom
              | ctl_atom | param_atom | pose_atom | pose_tag_atom | body_atom ;
vis_atom      = "vis" , "(" , part_ref , ")" , [ "." , component ] ;
component     = "V1" | "V2" | "V3" | "V4" ;
part_ref      = "any." , ident | part_id ;
chain_atom    = "chain" , "(" , part_ref , "," , part_ref , { "," , part_ref } , ")" ;
slot_atom     = "slot" , "(" , ident , ")" , eq_op , bit ;
outfit_atom   = "outfit" , eq_op , label | "outfit" , "in" , "{" , label , { "," , label } , "}" ;
ctl_atom      = "ctl" , "(" , ident , ")" , eq_op , ctl_value
              | "ctl" , "(" , ident , ")" , "in" , "{" , ctl_value , { "," , ctl_value } , "}" ;
ctl_value     = label | slot_ref | bit ;
param_atom    = "param" , "(" , param_name , ")" , cmp_op , number ;
pose_atom     = "pose" , eq_op , pose_id | "pose" , "in" , "{" , pose_id , { "," , pose_id } , "}" ;
pose_tag_atom = "pose_tag" , eq_op , tag | "pose_tag" , "in" , "{" , tag , { "," , tag } , "}" ;
body_atom     = "body." , ident , "in" , interval ;
interval      = ( "[" | "(" ) , number , "," , number , ( "]" | ")" ) ;
eq_op         = "=" | "!=" ;
cmp_op        = "=" | "!=" | "<=" | ">=" | "<" | ">" ;
bit           = "0" | "1" ;
slot_ref      = "#" , digit , { digit } ;                 (* slot number i, starting from 0 *)
label         = quoted | bare_label ;
param_name    = quoted | bare_param ;
quoted        = '"' , qchar , { qchar } , '"' ;           (* qchar = any character except " and newline *)
bare_label    = lchar , { lchar } ;    (* lchar = any character except whitespace and ( ) { } [ ] , | & ! = < > " : ; the first character cannot be # *)
bare_param    = pchar , { pchar } ;    (* pchar = A–Z a–z 0–9 _ / . $ # + - and any non-ASCII character *)
pose_id       = kchar , { kchar } , [ "@" , digit , { digit } ] ;   (* kchar = A–Z a–z 0–9 _ and Chinese characters; cannot be entirely digits; @k = the k-th sampled frame of a multi-frame clip *)
tag           = tchar , { tchar } ;                     (* tchar = A–Z a–z 0–9 _ *)
ident         = lower , { lower | digit | "_" } ;
part_id       = seg , { "." , seg } ;                     (* at least two segments in a declaration; single segment allowed in fragments *)
seg           = idchar , { idchar } ;                     (* idchar = A–Z a–z 0–9 _ *)
number        = [ "-" ] , digit , { digit } , [ "." , digit , { digit } ] ;
```

- Lexing: whitespace between tokens is ignored; operators use longest match (`!=` before `!`, `<=` before `<`); bare words take the longest match. **If a bare word entirely matches `number`, it is a number, not a label** — labels that look like numbers (e.g. `"1"`, `"2.5"`) must be quoted; `#` followed by digits is a slot number.
- The keywords `true false vis chain slot outfit ctl param pose pose_tag body in` are only meaningful at the start of an atom; part ids appear only inside `vis(…)`/`chain(…)`, so the only reserved word is **the first segment `any`** (`any.<kind>`). A part id like `body.ears` is legal.
- Precedence: `!` > `&` > `|`, binary operators are left-associative; add parentheses if you need a different order.
- Quoting: labels containing spaces or symbols (`Petal Drape`, `NOEM 卫衣`) are written `outfit = "Petal Drape"`; parameter names containing spaces or symbols (`CERP Pose`, `Breast size`) are written `param("CERP Pose") = 1`.
- YAML: always quote condition strings. A bare `when: true` is parsed by YAML as a boolean, and the schema rejects it by type (`/deps/<i>/when`).

## 2. Semantics

### 2.1 Atoms

| Atom | Meaning |
|---|---|
| `vis(p)` | Part is compositely visible: ∃ object o∈p.objects such that V1(o) activeInHierarchy ∧ V2(o) renderer.enabled ∧ V3(o) not entirely masked by material ∧ V4(o) vertex retention ratio ≥0.5 all pass |
| `vis(p).Vk` | Looks only at whether the k-th component "passes": ∃ o such that Vk(o) passes. Used to check component mismatches, e.g. `vis(p).V1 & !vis(p)` (active but not visible) |
| `any.<kind>` | The union of all parts (including alternates) whose kind is that value: `vis(any.shoes)` ≡ ∨ vis(p). Parts outside the current level are not visible anyway, so no need to filter by level again |
| `chain(a,b,…)` | Boolean value ≡ vis(a) ∨ vis(b) ∨ …; also defines the **leader** = the first visible member in written order (shoes > socks > bare feet). Used with `expect_by_leader`; with no leader it goes to `else`. Constraints see SEM-04 |
| `slot(x)=v` | The raw value (bool) of the body-part toggle parameter. A toggle of 1 does not mean an item is visible (the current outfit set may have no item for that body part) |
| `outfit = L` / `outfit in {…}` | The label for the outfit selector's current slot number; float_slots takes the slot number by [i/n,(i+1)/n), int takes the integer value |
| `ctl(c) = v` / `ctl(c) in {…}` | The current level of `menu.controls.c`: int/float_slots compare labels (or `#i` slot number, slot number conversion same as outfit); bool compares 0/1; float controls cannot use ctl (use param) |
| `param(P) op x` | The raw value of any parameter (Bool as 0/1); P must be the param of some control in menu, `body_axes.*.param`, or a VRChat built-in parameter (IsLocal, PreviewMode, VRMode, TrackingType, Grounded, Seated, AFK, InStation, Upright, GestureLeft/Right(Weight), Viseme, Voice, MuteSelf, Earmuffs, IsOnFriendsList, IsAnimatorEnabled, AvatarVersion, ScaleModified, ScaleFactor, ScaleFactorInverse, EyeHeightAsMeters, EyeHeightAsPercent, VelocityX/Y/Z, VelocityMagnitude, AngularY) or an SDK default parameter (VRCEmote, VRCFaceBlendH/V) |
| `pose = x` / `pose in {…}` | The currently applied pose id (§3; the pose field of the T1 request) |
| `pose_tag = t` / `pose_tag in {…}` | The current pose's tags contain t (any) |
| `body.<axis> in I` | The value of `body_axes.<axis>` normalized to [0,1] falls within interval I (`[`/`]` closed, `(`/`)` open) |

### 2.2 Expected visibility model E(p, s)

Static expansion (SEM-22, DepCompiler, verdict's "expected visible part set" readback assertion, 03 §4.4 ②) doesn't run Play; it uses the menu to infer whether each item **should** be visible:

1. `alt_of` alternate items: E = false (not active by default; when to swap items is constrained by `expect.variant` and doesn't enter the model).
2. Otherwise E = [outfit is null, or the current outfit set label ∈ p.outfit] ∧ [slot is null, or `slot(p.slot)=1`] ∧ [no toggle, or `ctl(toggle.control)` hits `toggle.shown_at`]. Items introduced by fragments use the include's outfit.
3. Single-pass correction: in declaration order, for dependencies whose target is `{part}` and whose result in this state is `hidden`/`shown` (evaluating its when/cases with step 2's E), change that item's E to false/true; no iteration.
4. During static evaluation `vis(p).Vk` always equals E(p, s). During measurement (verdict) vis uses T1's four components, and E is used only for readback assertions.

### 2.3 Evaluation order of expectations

For each dep and each state: `when` is false → `else`; when true, by `expect` | `cases` (ordered, take the first that holds; if none holds → `else`) | `expect_by_leader` (no leader → `else`). `when` defaults to `true`; `else` defaults to: `baseline` in a declaration, `dont_care` in a fragment. `baseline` for keys = the base avatar profile baseline; for `{part}` targets = visibility equals §2.2's E(p, s) (if the menu says show, show it). `dont_care` produces no verdict; `pending` always produces undecidable with `human` attached. `variant.options`: the first option o that holds requires "visible items in the group ⊆ {o.use}" (use itself not being visible is not a violation); `exclusive: true` additionally requires at most one visible item in the group.

**Writing convention**: when the same key is written by multiple items and multiple outfit sets (e.g. foot-shape keys), each dep only handles the case where its own item is visible, with `else` written as `dont_care`; "return to baseline when all writer hosts are invisible" is left to universal rule U3. Otherwise SEM-22 will report conflicts in other outfit sets' states.

## 3. Pose ids and tags (T-26 `pose_library.json` is authoritative)

Pose names in conditions, `pose_scope`, and `waivers[].pose` all resolve to the `id` and `tags` of `<工程>/_感知/out/pose_library.json` produced by T-26 `pose_frames.py`. The table below is compiled from how `pose_frames.py` (2026-09-18 22:58 version, sha256 prefix 1c37aef22aa92673; `muscles.py` e94f2dd29d75e15e) actually generates names; if the T-26 delivery changes the naming, its selftest output is authoritative and this table and the examples must be synced.

| Source | id | Example | tags |
|---|---|---|---|
| SDK proxy (`ProxyAnim/*.anim`, 79, all included) | File name as-is (with `proxy_`) | `proxy_stand_still`, `proxy_sit`, `proxy_crouch_still`, `proxy_walk_forward`, `proxy_hands_fist` | `proxy`; the 15 named in 03 §8.1 additionally have `library_a_pose` |
| GoGo Loco library A (7) | File name as-is | `go_sit_crossed_leg`, `go_laydown_side` | `gogoloco`, `library_a_pose` |
| Project-private (humanoid clips referenced by the descriptor's 5 layer controllers, P14) | File name normalized, **no prefix** | `cerp_pose_10`, `a2_抱熊姿势` (seen in an actual Project A run) | `private`; CERP additionally gets `cerp`, `gesture_pose`; bear hug gets `bearhug`; Additive layers get `additive`, otherwise `library_a_pose` |
| Library B sweeps | `B_<joint>_<L\|R\|C>_<25\|50\|75\|100>` (spine is C) | `B_knee_L_75`, `B_spine_fb_C_100` | `sweep`, joint name, body-part name, `dose_<dose>` |
| Library B combos (6) | `B_combo_sit`, `B_combo_deep_squat`, `B_combo_kneel_sit`, `B_combo_arms_crossed`, `B_combo_arms_up`, `B_combo_cross_legged` | — | `combo`, combo name, `dose_<dose>` of each joint |
| Library B extreme (generated only with `dose_envelope: extreme`) | `B_<joint>_<side>_extreme_<m1\|p1>` | `B_elbow_R_extreme_p1` | `sweep`, `extreme`, joint name, body-part name |
| GM emotes (`Resources/Gm/Animations/Emote/`, 16) | `C_emote_<normalized file name>` | `C_emote_emote_1_wave` | `emote`, `gesturemanager` |
| GoGo motions (library C) | `C_<file name>`: `C_go_jump_in_place`, `C_go_knockback`, `C_go_manual_afk_idle` | — | `gogoloco`, `motion` |
| `poses.extra_clips` | `C_extra_<normalized file name>` | `C_extra_walk_loop` | `user`, `extra` |
| Sampled frames of multi-frame clips | `<id>@<k>` (sample index, from 0, ≤5); if only one frame remains after dedup, the id without `@` is still used | `proxy_hands_idle2@3`, `C_emote_emote_1_wave@0`, `cerp_pose_10@2` | Same as that clip |

- Normalization (`_sanitize`): runs of characters other than letters, digits and Chinese characters are replaced with a single `_`, leading/trailing `_` removed, lowercased; on collision `_1`, `_2` are appended.
- Joint names (8): `hip_fb` hip flexion, `hip_io` hip abduction, `knee` knee, `shoulder_up` shoulder elevation, `shoulder_fb` shoulder forward raise, `elbow` elbow, `ankle` ankle, `spine_fb` spine flexion; body-part names: `thigh knee shoulder elbow ankle spine`.
- **Tag vocabulary**: `proxy library_a_pose gogoloco private cerp gesture_pose bearhug additive sweep extreme combo emote gesturemanager motion user extra dose_25 dose_50 dose_75 dose_100`, plus the 8 joint names, 6 body-part names, and 6 combo names. Pose categories (sitting, squatting, lying prone) are not tags: to select by category, list the ids.
- **Resolution** (SEM-03, SEM-23): when `pose_library.json` exists it is authoritative, and both ids and tags must be in the library. Without the library, check against the built-in list: ids starting with `proxy_`, `go_`, `B_`, `C_emote_`, `C_go_` must be in the fixed list of the table above (SDK 79, GoGo 7+3, library B 66+30, GM 16; within these families `@k` is only accepted after the 4 multi-frame SDK proxies — `landing`, `hands_idle2`, `empty`, `rotate90_right` — and after GM and GoGo motion ids, with k ≤5; for multi-frame clips the id without `@` is also accepted — offline you can't know how many frames remain after dedup), otherwise an error is reported; ids starting with `C_extra_` and other ids (project-private, including those with `@k`) can't be checked offline and only produce warnings. Tags must be in the vocabulary above.

## 4. Round-trip sequence EBNF (`deps[].roundtrip`)

```ebnf
sequence   = segment , { "," , segment } ;
segment    = rt_param , ":" , rt_value , arrow , rt_value , { arrow , rt_value } ;
rt_param   = quoted | rt_bare ;
rt_value   = slot_ref | quoted | rt_bare_v ;
rt_bare    = rchar , { rchar } ;             (* rchar = any character except whitespace and : , " → ; and "->" must not appear *)
rt_bare_v  = rchar - "#" , { rchar } ;       (* bare values don't start with #; # followed by digits is a slot number *)
arrow      = "→" | "->" ;                     (* "->" is a single token *)
```

- The value's type follows the control that the parameter belongs to: bool allows only `0`, `1`; int / float_slots allow only **labels** (bare or quoted) or **`#i` slot numbers**, **bare numbers not allowed** (raw values can't be written as exact decimals, 0.2857≠2/7, 00 #5); float allows only numbers within [0,1]. A bare value that entirely matches `number` is a number, so labels that look like numbers must be quoted.
- Each value is one step "set that parameter to this value" (an empty step if it equals the current value), sampling after each step; segments continue in written order. Examples: `A2_Coat:1→0, A2_Outfit:素体水手服→MMN→#0, A2_Coat:0->1`, `"CERP Pose":0→1`, `RJ_Outfit:"Petal Drape"→"NOEM 卫衣"`.
- The validator expands it into an explicit T1 `reset:none` sequence ([audit docs/state-driver-reset.md](../../docs/state-driver-reset.md), original README §3.0.3), with int/float_slots labels and slot numbers replaced by parameter values i or i/n. `roundtrip: []` means this entry runs no round trip; if omitted, `roundtrip_default` is used. The schema governs syntax with a regex (`$defs/dep/properties/roundtrip`), SEM-15 governs references and types.

## 5. Semantic rules (outside the schema, decl_validate must check)

| No. | Rule | Error path |
|---|---|---|
| SEM-01 | `parts[].id` and `deps[].id` are each unique (after includes are introduced, by global id; this file overriding a fragment's same id, and hand-written `geo.*` overriding generated items, are legitimate overrides); id collisions between generated items are reported on the later part; hand-written dep ids starting with `geo.` must be exactly some id that will be generated | `/id` of the later entry |
| SEM-02 | Conditions and `waivers[].states` conform to the §1 EBNF (including chain ≥2 members, lexical distinction between slot numbers/numbers/labels) | That string field |
| SEM-03 | Condition references exist: part id, the kind of `any.<kind>`, `slot(name)`∈menu.slots, outfit label∈menu.outfit.labels, `ctl(name)`∈menu.controls and not float, the ctl value is a label/legal slot number/(bool) 0 or 1 of that control, `param(name)` (§2.1), `body.<axis>`∈body_axes, pose id and pose_tag resolved per §3. Conditions **in fragments** allow only vis/chain/pose/pose_tag/true/false atoms (the menu belongs to each order) | That condition field |
| SEM-04 | chain members don't repeat; when `expect_by_leader` is used, `when` contains exactly one chain, and it is a **top-level conjunct** of `when` (not under `!` or `|`); the key set of `expect_by_leader` **exactly equals** that chain's member set (missing ones reported at `/expect_by_leader`, extra ones at `/expect_by_leader/<key>`) | `/when`, `/expect_by_leader` or `/expect_by_leader/<key>` |
| SEM-05 | `target.part` exists; `target.mesh` = avatar.body or the path of some part's `renderer: smr` object; the part of `{part, key|keys}` has at least one smr object; same for `body_axes.*.key.mesh`, `sync.from.mesh` | `/target/part`, `/target/mesh`, `…/sync/from/mesh` |
| SEM-06 | target shape matches the expectation (expect, cases, expect_by_leader, else all checked): hidden/shown/variant/geo require `{part}` without key and submesh; grab requires `{part}` or `{part, submesh}`; value/range/class/not_written/sync/deleted/no_writer_other_than require key or keys; values requires no key/keys; pending either way; submesh goes only with grab | That expectation field |
| SEM-07 | Keys on the body mesh must exist in the base avatar profile: when the profile has `all_keys:` (the full body-mesh key table landed by T-05 `body_keys`), not in the table → **error**, and `key_classes` is used only for classification; without `all_keys` the old convention is kept (`key_classes`+`baseline`+`keys`, missing downgraded to **warning**). Missing `--profile` → skipped | `/target/key` or `/target/keys/<i>` |
| SEM-08 | `parts[].outfit` label∈menu.outfit.labels; `parts[].slot`∈menu.slots; `toggle.control`∈menu.controls and not a float control; `toggle.shown_at` is a label of that control (int/float_slots) or 0/1 (bool). Fragment parts are checked against this declaration's menu when introduced | That field (`/parts/<i>/toggle/control`, `…/toggle/shown_at`) |
| SEM-09 | `alt_of` points to an existing part that is not itself an alternate; the alternate's outfit is the same as the main item's | `/parts/<i>/alt_of` |
| SEM-10 | `variant.options[].use` ∈ target part ∪ parts that have it as alt_of; the variant group has ≥2 items | `…/options/<i>/use` or `…/variant` |
| SEM-11 | The same (path, submesh) belongs to at most one part | The later `/objects/<i>/path` |
| SEM-12 | When inventory.json is available, `objects[].path` must be in the inventory with a matching renderer type; `target.submesh` is less than the material slot count | `/objects/<i>/renderer`, `/target/submesh` |
| SEM-13 | Ordered: `range` lo≤hi; condition interval lo≤hi; when `deleted` writes both min/max, min≤max; source values of `sync.map` strictly ascending | That field |
| SEM-14 | float_slots default = some i/n (tolerance 1e-6); int default is an integer 0…n−1 | `…/default` |
| SEM-15 | The round-trip sequence's parameter is the param of some control in menu; values fit that control's type (§4: bool 0/1, int/float_slots label or `#i` with i<n, float within [0,1]) | `/roundtrip/<i>` |
| SEM-16 | `waivers[].dep` is an existing dep id (declared, introduced by fragment, or to be generated by geo_defaults), and not superseded by `supersedes`; parts in `waivers[].parts` exist | `/waivers/<i>/dep`, `/waivers/<i>/parts/<j>` |
| SEM-17 | Parts in `geo_defaults.exclude` exist | `/geo_defaults/exclude/<i>` |
| SEM-18 | includes: the fragment file exists and passes the schema as perception-fragment/0.2; `package.body` matches the base avatar of avatar.profile; `as` values don't repeat; `target.mesh` and `sync.from.mesh` in fragment deps both equal avatar.body. **Non-conforming fragments are not merged**, and subsequent rules no longer look at them | `/includes/<i>/fragment` |
| SEM-19 | When `pending` is used anywhere in cases / else / expect_by_leader, the dep must have `human` (top-level expect is governed by the schema) | `/deps/<i>/human` |
| SEM-20 | The params of outfit / slots / controls in menu are pairwise distinct | The later `…/param` |
| SEM-21 | Parts with fit closed/tight and empty covers get a **warning** when geo_defaults is on (not rejected; such items generate no geometry items) | `/parts/<i>/covers` |
| SEM-22 | **Expectation conflict**: after expansion (fragments merged, supersedes in effect, geo generated), if for the same (mesh, key) in any reachable state (§6.1 enumeration) two non-dont_care/pending expectations are incompatible, report: interval types (value±tol, range, that key in values) with no pairwise intersection; class differs (state-independent). baseline participates in comparison at its value ±0.5 when there is a base avatar profile, not compared without a profile. Reported on whichever of the two comes later in expansion order, with the first conflicting state attached | The later one's `/deps/<j>/id` (when both come from fragments, `/includes/<i>/fragment#/deps/<j>/id`) |
| SEM-23 | Pose references: ids/`tag:` in `parts[].pose_scope` and `waivers[].pose` are resolved per §3 (library authoritative when present, built-in list otherwise); **warning** when `poses.extra_clips` is non-empty but `libraries` doesn't contain C (those clips won't be collected) | `/parts/<i>/pose_scope/<include|exclude>/<j>`, `/waivers/<i>/pose[/<j>]` |
| SEM-24 | `supersedes`: each id is an existing dep (introduced by fragment, generated, or another dep in this file), not itself; no cycles (A supersedes B and B supersedes A) | `/deps/<i>/supersedes/<j>` |

SEM-07 and SEM-12 depend on external data (base avatar profile, T-05 inventory), so examples/bad contains no counterexamples for them; positive/negative examples for SEM-07's `all_keys` are covered specifically by `--selftest` (features_misc + injected profile: empty table all error, all-zero column error, one key missing from the inventory error, no all_keys warning only). SEM-21 only warns. **When a fragment file is validated standalone**, the rules decidable within the fragment are run (SEM-01/02/03/04/05 (except mesh)/06/09/10/11/13/19), with error paths being the fragment's own paths; when introduced by a declaration, errors within the fragment are reported as `/includes/<i>/fragment#<path within fragment>`, that fragment is not merged, and SEM-18 is not reported separately.

## 6. Expansion (decl.json) and state enumeration

The decl.json output by decl_validate is the expanded form, in the following order:

1. **Merge includes**: local ids get the `<as>.` prefix (keys in conditions, target, alt_of, expect_by_leader rewritten accordingly); `objects.path` is prefixed with `mount/`; parts are written with the include's outfit; fragment deps' `target.mesh`/`sync.from.mesh` are the body mesh and don't get mount prefixed (clothing meshes in fragments are always referenced with `{part, key}`); fragment deps without else get `dont_care`. Parts/deps with the same id in this file entirely override the fragment's.
2. **geo_defaults generation** (rules see schema `$defs/geoDefaults`): region operations are by leaf — `LeftFoot` = `LeftFoot.{forefoot,arch,heel,ankle}`, `LeftFingers` = the 15 left finger bones, other bone names are leaves; R = covers leaf set − openings leaf set, results listed by leaf (when all four sub-parts of a whole foot are present, written back as `LeftFoot`). Generates `geo.<p>` (static main item), `geo.<p>.opening` (opening item), `geo.<p>.poke` (pose item); hand-written same ids override generated items.
3. **supersedes**: superseded deps don't enter the expectation matrix; the entry is kept with `superseded_by: [<id>…]` added.
4. **Materialize defaults**: `when: "true"`, `else` (declaration baseline / fragment dont_care), `tol: 0.5`, `roundtrip_default`, defaults of `poses` and `render`, default items of `geo_defaults`.
5. Sort by id, sort keys; each dep carries `origin: declared|fragment|geo_default`, generated items carry `generated_from: <part id>` (these two fields exist only in decl.json and must not be written in YAML).

### 6.1 State enumeration (shared by SEM-22 and verdict's expectation matrix)

- Menu dimensions: outfit and int/float_slots controls take each slot (float_slots takes i/n itself), bool takes 0/1, mutually independent (menu toggles are independent).
- Continuous dimensions (float controls, body axes, parameters outside the menu): **critical-point sampling** — take all constants c that appear on that dimension in conditions; samples = {c} ∪ midpoints of adjacent constants ∪ {smallest constant−1, largest constant+1} (clipped to the value range); body axes additionally union `samples` (default [0, 0.5, 1]). This way every true/false combination of every comparison is sampled at least once.
- Pose dimension: expanded only when some condition uses pose/pose_tag; per §3's library (or built-in list), all poses are divided into equivalence classes by "the truth-value vector of each pose/pose_tag atom", taking one representative per class.
- Visibility uses §2.2's E; size = product of sample counts over dimensions (Project A about 7×2⁶×3×3×2 = 8 064); evaluating each dep one by one is fine, no pruning needed.

## 7. Handling of fields undefined in 03a

| 03a notation | v0.2 handling |
|---|---|
| `rules` | Rewritten as `cases` (ordered, the first branch that holds wins) |
| `extra` | Deleted: split into independent deps (each with its own id/target/expect/writer) |
| `also` | Deleted: split into independent deps |
| `exceptions` | Rewritten as `cases`, with exception branches placed first |
| `shown_if` | Deleted: per P1 default changed to `else: dont_care`; to expose a control, use `cases` to write `slot(under)=1 → shown` |
| `flag` | Rewritten as `expect: {pending: true}` + required `human` |
| `as_listed` | Deleted: changed to `expect.values` (per-key value mapping) |
| `dont_care` | Defined as an outcome shorthand (usable in expect / else / cases / expect_by_leader) |
| `variant.options` | Defined: `variant: {exclusive, options: [{when, use}]}`, semantics "visible items in the group ⊆ {use}"; `by`/`of` deleted (group = target part + alt_of alternates); `exclusive: false` must come with options |
| `targets` | Defined: a list of targets, mutually exclusive with target |
| `keys` mapping | Mapping form deleted; `keys` accepts only a list; for different values per key use `expect.values` |
| dep-level `chain` | Deleted: the priority chain is written into `when: chain(...)` (top-level conjunct), paired with `expect_by_leader` (keys = full member set) |

Other structural changes: `alt_objects` → alternates become independent parts with `alt_of`; `closed: bool` → `fit: closed|tight|loose|none`; `vendor_clip {on, off}` → `{on_clip, off_clip}` (YAML 1.1 parses on/off as booleans); `objects` strings → `{path, renderer, submesh}` (`路径#槽号` → `submesh`); single-column `confidence` → `{writer, correct, correct_basis}`; `writer` free text → vocabulary value or list (explanations moved to `note`/`source`); `menu.part_toggles/other` → `menu.slots/controls` (controls carry encoding and labels), correspondence between hairstyles/headwear/accessories and parts written as `parts[].toggle`; `menu.outfit_radial` → `menu.outfit`; `pose in {walk, sit, crouch}` → pose library ids (`proxy_walk_forward`, `proxy_sit`, `proxy_crouch_still`, §3).

## 8. Counterexample header comments and error path conventions

Each `examples/bad/*.yaml` file is derived from the same legal base draft by changing one place, and violates exactly one rule. The first three lines of the file header are fixed, optionally followed by a `# note:` line:

```yaml
# rule: <schema keyword or SEM-xx> — <one sentence>
# layer: schema | semantic
# expect_error_path: <JSON Pointer, e.g. /deps/0/confidence/correct>
```

**selftest criteria**: `layer: schema` — the schema must reject it, and the expected path ∈ the normalized path set; **documents that fail the schema don't run the semantic layer** (T-02 must do this: some counterexamples lack required fields and the semantic layer would crash). `layer: semantic` — the schema must **pass**, the semantic layer must reject and report the expected path, hitting only this one SEM rule. The `# note:` of schema counterexamples is written automatically by the generation script from the result of "skipping the schema and running the semantic layer directly" ("would also hit SEM-xx" or "semantic layer cannot run"); it's only a reading hint and doesn't participate in the criteria. Counterexamples of fragment files (`schema: perception-fragment/0.2`) are validated standalone per the last paragraph of §5.

**Error path normalization** (the T-02 implementation must match): for each error from jsonschema `iter_errors`, if it has `context` (oneOf/anyOf failure), recursively expand its sub-errors; leaf errors take `absolute_path` converted to a JSON Pointer (within segments `~`→`~0`, `/`→`~1`, RFC 6901), and: `required` appends the missing property name; `additionalProperties` appends the extra property name; errors whose `schema_path` contains `propertyNames` append `instance` (the offending key name). A counterexample reporting multiple paths is normal (oneOf/anyOf expansion brings along companion paths); the criterion only requires the expected path to be in the set.

**Mutual exclusion rules** are written in the schema **one-directionally** as `{"not": {}}` in canonical order (not boolean `false`: jsonschema 4.19 drops the property name for `false` subschemas), so writing two mutually exclusive fields together is reported only on the field later in canonical order: target `part→mesh`, `key→keys`, `submesh→key/keys`; dep `target→targets`, `expect→cases→expect_by_leader`; primary expectation forms in the order described in schema `$defs/expectation`; geo `inside→no_pierce→no_poke→opening_intact`; sync `scale/offset→map`; waiver `dep→rule/parts`, limit `max→min`; part `slot→toggle`.

**Error paths from fragment sources**: `/includes/<i>/fragment#<JSON Pointer within the fragment>`, e.g. `/includes/0/fragment#/deps/1/when`. Semantic layer errors directly give the path in the "Error path" column of §5. When loading YAML, timestamps are treated as strings (implicit timestamp parsing removed), and `on/off/yes/no` remain YAML 1.1 booleans (counterexamples depend on this).

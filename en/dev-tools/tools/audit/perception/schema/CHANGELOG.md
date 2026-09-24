> 🌐 English translation · [中文原文](../../../../../../开发工具/通用工具/审查/perception/schema/CHANGELOG.md)

# perception schema v0.2 · Change log

> Companion to `perception-0.2.schema.json` and `CONDITION_GRAMMAR.md`. New entries are added at the top.

## 2026-09-19 Task AQ (base avatar profile full key table)

**Change**: SEM-07 supports the new base avatar profile section `all_keys:` (the full body-mesh key table landed from the T-05 inventory `body_keys`,
written by `perception/profile_keys.py`). When the profile has `all_keys`, a key in the declaration targeting the body mesh that is not in the table
→ **error** (`key_classes` is used only for classification); without `all_keys` the old convention is kept (`key_classes` + `baseline`
+ `keys`, missing downgraded to **warning**). The schema itself is unchanged (base avatar profiles still have no schema); only the SEM-07 row of `CONDITION_GRAMMAR.md`
§5 and the final paragraph note were changed.

**Companion changes**: T-05 `AuditPartInventory.cs` adds `body_keys`/`body_key_count` per avatar; new
`perception/profile_keys.py` (replaces only the `all_keys:` section, preserving other comments; when it already exists and differs, by default it only reports the difference,
and only `--force` overwrites). `--selftest` adds a SEM-07 special case: features_misc + positive/negative examples with an injected profile.

**Not affected**: the other SEM rules, the schema counterexample set, and `--selftest`'s 8+250 count are unchanged.

## 2026-09-18 rev 2 (review incorporated)

**Basis**: independent review comments P1–P15 and the two "§6 text mismatch" items; after the review 03 was upgraded to v3 (22:30), and §8 and 04 T-32 also changed; this version aligns with all of them (wherever they conflict with the review's suggestions, 04 v3 is authoritative, itemized in the table below).

### Item-by-item handling

| # | Handling | Where it landed |
|---|---|---|
| P1 pose section | **Adopted, with one change**: top-level `poses {libraries, extra_clips, pb_default, dose_envelope, private_clips}`; `parts[].pb`, `parts[].pose_scope {include, exclude}` (pose id or `tag:`); `geo.no_poke {region, max_depth_mm, min_area_cm2}`; waiver gets optional `pose` (selector or list) and `pb_mode` (rigid/settle); D8 of `03a_project-c` changed to use no_poke and library ids. The review's suggested `sweep_max: 75\|100` was not added: 04 v3 T-32 changed P13 to `dose_envelope: libraryA\|extreme`, following 04. Also added `private_clips` (P14 switch, default true) | schema `$defs/poses`, `geoNoPoke`, `poseScope`, `waiver`; CONDITION_GRAMMAR §1 (pose/pose_tag atoms), §3 (pose ids and tags, per T-26's actual naming) |
| P2 no_poke default generation | Adopted: `geo_defaults.cover: no_poke\|none` (default no_poke), generated item id is `geo.<item>.poke` | schema `$defs/geoDefaults`; §6 step 2 |
| P3 fragment vs declaration contradiction | Adopted three items: ① the default else for fragment deps changed to dont_care; ② added SEM-22 (non-dont_care expectations for the same (mesh, key) must be compatible in any reachable state; states enumerated by §6.1 critical-point sampling, visibility via §2.2's expected visibility model E); ③ added `supersedes` (superseded ones don't enter the expectation matrix and can no longer be waived; reference check is SEM-24). Also added a writing convention: for keys shared by multiple outfit sets, each dep's else is dont_care, and returning to baseline is left to U3 | schema `dep.supersedes`, `else` description; §2.2, §2.3, §5 SEM-22/24, §6 |
| P4 round-trip grammar ambiguity | Adopted: `->` is a single token; parameter names and labels must not contain `: , " →` or `->`, and those containing these characters must be quoted; int/float_slots may only be written as labels or `#i` slot numbers, not bare numbers; labels that look like numbers must be quoted. The round-trip regex in the schema was rewritten per this EBNF. **Also fixed a problem along the way**: parameter names previously disallowed spaces and parentheses, but real projects have `CERP Pose`, `kaguya ear`, `…/Middle(Big0)…##7` (checked in the t4_menu/params.json of Project A and Project D); now allowed, written with quotes in conditions and round trips | schema `$defs/param`, `dep.roundtrip`; §1 lexing, §4 |
| P5 condition grammar details | Adopted: pose and kind changed to ordinary identifiers, checked by SEM-03 against the vocabulary or pose library (without `pose_library.json`, per §3's built-in list: the fixed families `proxy_`/`go_`/`B_`/`C_emote_`/`C_go_` must be in the list; project-private and extra can't be checked offline and only produce warnings); added `pose_tag`; the only reserved word left is the first segment `any` (`body.ears` is legal); added `ctl(<control>) = label \| #i \| 0/1` and `ctl(…) in {…}` | §1, §2.1, §3, §5 SEM-03 |
| P6 sem18 dragging in SEM-08 | Did both: added a bottom slot to the base draft's menu; SEM-18 states that non-conforming fragments are not merged and subsequent rules no longer look at them. Also added `sem08_fragment_part_slot`, specifically demonstrating SEM-08 on fragment parts and error paths containing `#` | `bad/sem18_*`, §5 SEM-18 |
| P7 variant.options false positives | Adopted: options semantics changed to "visible items in the group ⊆ {use}" (a coat being off isn't a violation); `exclusive: false` without options is rejected by the schema | schema `expectation.variant`; §2.3 |
| P8 headdress grab pass | Adopted: top-level `render.grab_point_min` (default 3050); expectation adds `grab {point_min, hidden_behind_max}`; target adds `submesh` (only with part, only with grab); dep kind adds `R` (render/grab pass, the kind extension of 03 Q10); waiver takes either dep or `rule: U1…U7` + `parts`; metrics add `grab.point_queue` (using the newly added `limit.min`), `grab.hidden_count`, `poke.area_cm2`, `poke.max_depth_mm`, `opening.max_shrink_mm`. `工程A_min` includes `工程A.grab.headdress_color_chain` (the replay library's dep_id) and PixelBoot's U4 rule waiver | schema `grab`, `render`, `target`, `waiver`; `ok/工程A_min.yaml` |
| P9 value loopholes | Adopted: `{class, tol}` is rejected (tol only goes with value/values); no segment of key or meshPath may start with `AAO_Merged_` or `$$AAO_`; fragment dep writers may only be vendor_*, confidence's correct is fixed as unknown, and correct_basis may not be written | schema `KEY`/`MESH_PATH`, `fragmentDep`, `fragmentConfidence` |
| P10 part-control binding | Adopted, but **the key name was changed**: `parts[].toggle {control, shown_at}`, mutually exclusive with slot, checked by SEM-08. The suggested `on` would be parsed by YAML 1.1 as boolean True (actually hit when first written: `/parts/3/toggle/True`), the same reason `vendor_clip` doesn't use on/off; for this the counterexample `schema_part_toggle_on_yaml_bool` was added | schema `$defs/toggle`; §2.2, SEM-08 |
| P11 expansion rules | Adopted: when covers is empty (or empty after subtracting openings) nothing is generated; items with openings additionally generate `geo.<item>.opening`, which can be turned off with `geo_defaults.opening`; regions of inside/no_pierce/no_poke are all covers minus openings. Region operations are computed by leaf: LeftFoot = four sub-parts, the newly added aggregate names LeftFingers/RightFingers = 15 finger bones each; if not computed by leaf, subtracting fingertips from gloves wouldn't work | schema `geoDefaults`, `region`; §6 step 2 |
| P12 chest | Adopted two items: `sync` adds `scale/offset` or piecewise `map` (mutually exclusive; ascending source values of map checked by SEM-13); body_axes adds `samples` | schema `$defs/sync`, `bodyAxis` |
| P13 fragment expansion | Adopted: clothing meshes in fragments are always referenced with `{part, key}`; `mesh` may only be the body mesh and must equal avatar.body (SEM-18), without mount prefixing; error paths from fragment sources are uniformly written `/includes/<i>/fragment#<path within fragment>`; which rules run when a fragment is validated standalone is also spelled out | end of §5, §6 step 1, §8 |
| P14 expect_by_leader | Adopted: chain must be a top-level conjunct of when (cannot be under `!` or `\|`); the key set must **exactly equal** the member set. Strict equality was chosen rather than "missing ones go to else": omitting a member is usually a typo and shouldn't be silently let through | §5 SEM-04 |
| P15 documentation | **Can't be done in this task**: the FootNail row in 03 §3 requires changing 03, which is not among the files writable in this task (the positive example already writes `FootNail_Default Variation` per `美甲清点.md:6`). A base avatar profile schema is also outside T-01's scope, see "Outstanding" | — |
| §6 note doesn't match reality | Adopted: the `# note:` of schema counterexamples is now computed by the generation script: which rules would additionally be hit when skipping the schema and running the semantic layer directly, or whether the semantic layer would crash, is written into the note. Of the 188 schema counterexamples, 44 have a note: 28 say "would also hit SEM-xx", 16 say "semantic layer would crash"; the other 144 report nothing extra when skipping the schema and running the semantic layer. §8 states: documents that fail the schema don't run the semantic layer | §8; `bad/schema_*` header comments |
| §6 "path lands on the later field" | Adopted: mutual exclusion rules are all rewritten **one-directionally** in canonical order (primary forms of expectation, geo metrics, sync's map, etc.); when two mutually exclusive fields are written together, only the one later in order is reported; §8 lists all canonical orders | schema `exclusive_chain`; §8 |

### Changes beyond the review

- **Aligned with 03 v3's geometry conventions (F26)**: U1's main criterion has been changed to static poke-through patches. The semantics of `geo.inside`/`no_pierce` were correspondingly changed to "patch count = 0", adding `min_area_cm2`; the containment ratio was demoted to a reference column. Waiver metrics dropped `geo.intersections`, `geo.max_depth_mm`, `geo.outside_ratio`: reference columns have no threshold, so waiving them is meaningless.
- **The meaning of `baseline` on `{part}` targets** was previously undefined; it is now defined as "visibility equals the expected visibility model E" (§2.3).
- **SEM-22 caught a real conflict in the first draft**: in the first draft of `03a_milfy`, the else of `snowflake.foot_by_leader` was written as "all 0", which under the LUNALICE outfit set conflicted with `milfy.lunalice.foot` (Foot_highheels = 100) (`/deps/3/id`, outfit = 9). It was split into two entries, "by leader" and "bare feet for this set", and the else of foot-shape keys shared by multiple sets was uniformly changed to dont_care. Project C's `violet.toe_highheels` was likewise changed to dont_care.
- Completed the built-in parameter table (PreviewMode, IsAnimatorEnabled, AvatarVersion, ScaleFactorInverse, EyeHeightAsMeters/Percent, VelocityMagnitude, VRCEmote, VRCFaceBlendH/V).
- **Pose ids aligned with T-26's implementation**: while writing this version it was found that DSH had already written `pose_frames.py` in the same directory (task AB, 22:46–22:58), whose naming is `proxy_*`, `go_*`, `B_<关节>_<L|R|C>_<剂量>`, `B_combo_*`, `C_emote_*`, `C_go_*`, `C_extra_*`; project-private clips get no prefix, and multi-frame clips use `@<取样序号>`. T-26's task brief didn't specify naming, and the §3 I drafted (`sw_*`/`cb_*`/`gm_*`/`prv_*`) would conflict with it, so it was changed to follow its implementation, without changing its file. The pose id regex was relaxed to upper/lower-case letters, digits, underscores and Chinese characters (a private clip name contains `抱熊`). Cross-checked against the Project A library (360 entries) produced by actually running it with `--envelope extreme`: 0 misjudgments by the built-in list, 65 project-private entries producing only warnings; all tags in the library are in the §3 vocabulary; all pose ids used in the examples are in the library (output below). The values `libraryA|extreme` of `poses.dose_envelope` match its `--envelope` parameter.
- New positive example `fragment_features.decl.yaml` (illustrative fragment), covering fragment-specific fields (alt_of, openings, owner_writers, pb, pose_scope, toggle, vendor_clip, targets, cases, expect_by_leader including `any.<kind>`, else, human), introduced by `features_misc` with `as: FX`.
- `工程A_min` was changed into the T-03 template: introduces the MMN fragment and entirely overrides MMN.shoes (writing back the human-judged answer), `MMN.foot_flat` supersedes the fragment dependency with `supersedes`; added headdress and hair accessory controls and toggles, `pose_scope`, an R grab-pass dependency, and the PixelBoot U4 waiver. The waiver's `by` says "pending user confirmation": the work log only says "recorded as acceptable residue on 09-03", not who decided it.

### Outstanding issues

1. **The 03 §3 FootNail row** contradicts `工程A/Assets/_Work/美甲清点.md:6`: the one with the renderer is `FootNail_Default Variation`, and the wrapper object without a renderer is `FootNailToggle_Default Variation`. What needs changing is that row in 03 §3; handed to the main session.
2. **Base avatar profiles have no schema**: SEM-07 (body key existence) and SEM-22's baseline comparison both depend on it, and 03 §3 "delete aliases with counts" also has nowhere to be enforced. Suggest adding a T-01b (Claude, S) before T-03 drafts `Kaguya.yaml`; until then, SEM-07 is downgraded to warning per this page, and SEM-22 doesn't compare baselines.
3. **`dep_kind: "U4"` in the replay library's `replay/grab_headdress/expect.json`** is a rule number; in the declaration this dependency's kind is `R`, and rule U4 is something else. Suggest the T-15 owner change it to `R`, or separate kind and rules in the replay format (it already has `rules: ["U4"]`). This task doesn't change the replay library.
4. **PixelBoot's renderer type** is written as MeshRenderer (a model instance, no skinning — an inference); the waiver's approver is pending user confirmation. Both are marked in `工程A_min`'s source/by, and will be checked by SEM-12 once T-05 produces the inventory.
5. **§3 was written against the 22:58 version of `pose_frames.py` (sha256 prefix 1c37aef22aa92673)**, and T-26 is still in progress. If it changes the naming on delivery, §3, the `POSE_SEL` regex (usually doesn't need to change after relaxing), the built-in list, and the pose ids in `project-c`, `features_misc`, `fragment_features`, `工程A_min` must all be synced. Also, offline validation can't recognize spelling errors in project-private clips: they have no prefix and can only produce warnings. To catch errors offline too, T-26 could add a prefix to private clips (e.g. `P_`); this needs the main session's decision, and this task doesn't change its file.
6. **The reviewer's `sem.py` is outdated**: it hard-codes the old 7 pose words and only recognizes dep waivers; on the new version it falsely reports SEM-03 for `project-c` and crashes on rule waivers (KeyError: 'dep'). Its `sv.py` (schema layer) is still usable; results below.
7. Midway through this task, the workspace's periodic commits (9ac10c63 etc., not made by this task) swept my half-finished version at the time into git; the final version is the current state of the workspace, and per the task requirements this task made no commits.
8. The semantic-layer prototype `check.py` and the generation scripts are all in the scratchpad (session temp dir `scratchpad/t01/`, not committed: `build_schema.py`, `gen_bad.py`, `check.py`, `coverage.py`), **not deliverables**; T-02 should rewrite per CONDITION_GRAMMAR. They only prove the rules are implementable, and that the examples conform to the rules.

### Validation

This machine: `python3 3.14.4`, `jsonschema 4.19.2`, `PyYAML 6.0.3`. Implicit timestamp parsing is removed when loading YAML, and error paths are normalized per §8.

- Positive examples 8/8: schema passes, semantic layer (SEM-01…24; state counts enumerated by SEM-22: `工程A_min` 8 064, `03a_工程A` 6 720, features_misc 120 960, 03a_milfy 1 040, 03a_project-c 256, 03a_h3 3) 0 errors.
- Counterexamples 250: 188 at the schema layer, all rejected, with the expected paths all in the normalized path set; 62 at the semantic layer, all first pass the schema and are then rejected by the semantic layer, each hitting only the one rule written in its header comment, and reporting the expected path. The reviewer's independent script `sv.py` (unmodified) gives the same result: 188 GOOD, 62 SCHEMA_PASS.
- Field coverage: 232 of 233 (context, field) pairs appear in the positive examples; the only exception, `menu.slots.*.labels`, is intentional: bool toggles may not have labels, and it is covered by the counterexample `schema_menu_bool_labels`. Counted by field name, every field has at least one counterexample.
- Pose ids: the Project A library (360 entries) produced by actually running `pose_frames.py --envelope extreme` was run through the built-in list entry by entry: 0 misjudgments, 65 project-private entries producing only warnings; all tags in the library are in the vocabulary; all pose ids used in the examples are in the library.
- Closure: except for the root, all structural objects are `additionalProperties:false`. The two "open objects" reported are `if` condition subschemas, not field definitions. The 29 places without description are also all in if/then condition subschemas.

<details><summary>Full output (2026-09-18 23:09)</summary>

```
$ date; sha256sum schema/perception-0.2.schema.json
2026-09-18 23:09:15 +1200
be6cdaed34a83ca1d5eed1b8fd23dcc3ac829969894c50d1562ae1faca887074  schema/perception-0.2.schema.json
python 3.14.4 | jsonschema 4.19.2 | PyYAML 6.0.3 | check_schema(Draft 2020-12): ok

$ python3 check.py   # schema + normalized paths + SEM-01…24 prototype
ok  PASS 03a_工程A.yaml
ok  PASS 03a_h3.yaml
ok  PASS 03a_milfy.yaml
ok  PASS 03a_project-c.yaml
ok  PASS 工程A_min.yaml
ok  PASS features_misc.yaml
ok  PASS fragment_MMN.decl.yaml
ok  PASS fragment_features.decl.yaml
bad OK  schema_avatar_body_path.yaml exp=/avatar/body 
bad OK  schema_avatar_missing_root.yaml exp=/avatar/root 
bad OK  schema_avatar_profile_pattern.yaml exp=/avatar/profile 
bad OK  schema_avatar_project_empty.yaml exp=/avatar/project 
bad OK  schema_avatar_scene_pattern.yaml exp=/avatar/scene 
bad OK  schema_body_axis_both.yaml exp=/body_axes/bust/param 
bad OK  schema_body_axis_param_arrow.yaml exp=/body_axes/bust/param 
bad OK  schema_body_axis_samples_range.yaml exp=/body_axes/bust/samples/1 
bad OK  schema_control_label_empty.yaml exp=/menu/slots/socks/label 
bad OK  schema_dep_also_field.yaml exp=/deps/0/also 
bad OK  schema_dep_as_listed.yaml exp=/deps/0/expect/value 
bad OK  schema_dep_by_leader_key.yaml exp=/deps/0/expect_by_leader/MMN shoes 
bad OK  schema_dep_by_leader_no_chain.yaml exp=/deps/0/when 
bad OK  schema_dep_cases_empty.yaml exp=/deps/0/cases 
bad OK  schema_dep_cases_missing_when.yaml exp=/deps/0/cases/0/when 
bad OK  schema_dep_chain_field.yaml exp=/deps/0/chain 
bad OK  schema_dep_confidence_enum.yaml exp=/deps/0/confidence/correct 
bad OK  schema_dep_confidence_single.yaml exp=/deps/0/confidence 
bad OK  schema_dep_correct_basis_pattern.yaml exp=/deps/0/confidence/correct_basis 
bad OK  schema_dep_else_enum.yaml exp=/deps/0/else 
bad OK  schema_dep_exceptions_field.yaml exp=/deps/0/exceptions 
bad OK  schema_dep_expect_and_cases.yaml exp=/deps/0/cases 
bad OK  schema_dep_extra_field.yaml exp=/deps/0/extra 
bad OK  schema_dep_flag_field.yaml exp=/deps/0/expect/flag 
bad OK  schema_dep_human_empty.yaml exp=/deps/0/human 
bad OK  schema_dep_key_and_keys.yaml exp=/deps/0/target/keys 
bad OK  schema_dep_keys_map.yaml exp=/deps/0/target/keys 
bad OK  schema_dep_kind_enum.yaml exp=/deps/0/kind 
bad OK  schema_dep_missing_confidence.yaml exp=/deps/0/confidence 
bad OK  schema_dep_missing_source.yaml exp=/deps/0/source 
bad OK  schema_dep_missing_writer.yaml exp=/deps/0/writer 
bad OK  schema_dep_no_expect.yaml exp=/deps/0/expect 
bad OK  schema_dep_no_target.yaml exp=/deps/0/target 
bad OK  schema_dep_part_and_mesh.yaml exp=/deps/0/target/mesh 
bad OK  schema_dep_roundtrip_bad_slotref.yaml exp=/deps/0/roundtrip/0 
bad OK  schema_dep_roundtrip_no_arrow.yaml exp=/deps/0/roundtrip/0 
bad OK  schema_dep_roundtrip_unquoted_space.yaml exp=/deps/0/roundtrip/0 
bad OK  schema_dep_rules_field.yaml exp=/deps/0/rules 
bad OK  schema_dep_shown_if_field.yaml exp=/deps/0/else/shown_if 
bad OK  schema_dep_supersedes_empty.yaml exp=/deps/0/supersedes 
bad OK  schema_dep_supersedes_pattern.yaml exp=/deps/0/supersedes/0 
bad OK  schema_dep_target_and_targets.yaml exp=/deps/0/targets 
bad OK  schema_dep_vendor_correct_no_basis.yaml exp=/deps/0/confidence/correct_basis 
bad OK  schema_dep_when_bool.yaml exp=/deps/0/when 
bad OK  schema_dep_when_empty.yaml exp=/deps/0/when 
bad OK  schema_dep_writer_any.yaml exp=/deps/0/writer 
bad OK  schema_exp_class_enum.yaml exp=/deps/0/expect/class 
bad OK  schema_exp_class_tol.yaml exp=/deps/0/expect/tol 
bad OK  schema_exp_class_with_hidden.yaml exp=/deps/0/expect/class 
bad OK  schema_exp_deleted_max_ratio.yaml exp=/deps/0/expect/deleted/max_ratio 
bad OK  schema_exp_deleted_no_ratio.yaml exp=/deps/0/expect/deleted/min_ratio 
bad OK  schema_exp_deleted_ratio_range.yaml exp=/deps/0/expect/deleted/min_ratio 
bad OK  schema_exp_geo_depth_zero.yaml exp=/deps/0/expect/geo/inside/max_depth_mm 
bad OK  schema_exp_geo_inside_area.yaml exp=/deps/0/expect/geo/inside/min_area_cm2 
bad OK  schema_exp_geo_missing_region.yaml exp=/deps/0/expect/geo/no_pierce/region 
bad OK  schema_exp_geo_no_pierce_depth.yaml exp=/deps/0/expect/geo/no_pierce/max_depth_mm 
bad OK  schema_exp_geo_no_poke_area.yaml exp=/deps/0/expect/geo/no_poke/min_area_cm2 
bad OK  schema_exp_geo_no_poke_region.yaml exp=/deps/0/expect/geo/no_poke/region 
bad OK  schema_exp_geo_two_metrics.yaml exp=/deps/0/expect/geo/no_pierce 
bad OK  schema_exp_grab_empty.yaml exp=/deps/0/expect/grab 
bad OK  schema_exp_grab_hidden_negative.yaml exp=/deps/0/expect/grab/hidden_behind_max 
bad OK  schema_exp_grab_point_type.yaml exp=/deps/0/expect/grab/point_min 
bad OK  schema_exp_no_writer_enum.yaml exp=/deps/0/expect/no_writer_other_than/1 
bad OK  schema_exp_not_written_false.yaml exp=/deps/0/expect/not_written 
bad OK  schema_exp_opening_region.yaml exp=/deps/0/expect/geo/opening_intact/region 
bad OK  schema_exp_opening_shrink_zero.yaml exp=/deps/0/expect/geo/opening_intact/max_shrink_mm 
bad OK  schema_exp_pending_false.yaml exp=/deps/0/expect/pending 
bad OK  schema_exp_pending_no_human.yaml exp=/deps/0/human 
bad OK  schema_exp_range_len.yaml exp=/deps/0/expect/range 
bad OK  schema_exp_shown_false.yaml exp=/deps/0/expect/shown 
bad OK  schema_exp_sync_map_and_scale.yaml exp=/deps/0/expect/sync/map 
bad OK  schema_exp_sync_map_point.yaml exp=/deps/0/expect/sync/map/0 
bad OK  schema_exp_sync_missing_from.yaml exp=/deps/0/expect/sync/from 
bad OK  schema_exp_sync_offset_type.yaml exp=/deps/0/expect/sync/offset 
bad OK  schema_exp_sync_scale_type.yaml exp=/deps/0/expect/sync/scale 
bad OK  schema_exp_tol_without_value.yaml exp=/deps/0/expect/tol 
bad OK  schema_exp_two_primaries.yaml exp=/deps/0/expect/hidden 
bad OK  schema_exp_value_range.yaml exp=/deps/0/expect/value 
bad OK  schema_exp_values_bad.yaml exp=/deps/0/expect/values/Foot_Hiheel_____足_ハイヒール 
bad OK  schema_exp_variant_by.yaml exp=/deps/0/expect/variant/by 
bad OK  schema_exp_variant_missing_exclusive.yaml exp=/deps/0/expect/variant/exclusive 
bad OK  schema_exp_variant_nonexclusive_empty.yaml exp=/deps/0/expect/variant/options 
bad OK  schema_exp_variant_options_one.yaml exp=/deps/0/expect/variant/options 
bad OK  schema_frag_dep_correct_basis.yaml exp=/deps/0/confidence/correct_basis 
bad OK  schema_frag_dep_correct_raised.yaml exp=/deps/0/confidence/correct 
bad OK  schema_frag_dep_roundtrip.yaml exp=/deps/0/roundtrip 
bad OK  schema_frag_dep_supersedes.yaml exp=/deps/0/supersedes 
bad OK  schema_frag_dep_writer_gen.yaml exp=/deps/0/writer 
bad OK  schema_frag_menu.yaml exp=/menu 
bad OK  schema_frag_missing_package.yaml exp=/package 
bad OK  schema_frag_package_body.yaml exp=/package/body 
bad OK  schema_frag_package_name.yaml exp=/package/name 
bad OK  schema_frag_part_outfit.yaml exp=/parts/0/outfit 
bad OK  schema_frag_poses.yaml exp=/poses 
bad OK  schema_frag_version_float.yaml exp=/package/version 
bad OK  schema_geo_defaults_cover_enum.yaml exp=/geo_defaults/cover 
bad OK  schema_geo_defaults_extra.yaml exp=/geo_defaults/shoes 
bad OK  schema_geo_defaults_loose_enum.yaml exp=/geo_defaults/loose 
bad OK  schema_geo_defaults_off.yaml exp=/geo_defaults/closed 
bad OK  schema_geo_defaults_opening_enum.yaml exp=/geo_defaults/opening 
bad OK  schema_geo_defaults_string.yaml exp=/geo_defaults 
bad OK  schema_geo_defaults_tight_enum.yaml exp=/geo_defaults/tight 
bad OK  schema_human_missing_q.yaml exp=/parts/1/human/q 
bad OK  schema_include_as_pattern.yaml exp=/includes/0/as 
bad OK  schema_include_ext.yaml exp=/includes/0/fragment 
bad OK  schema_include_missing_mount.yaml exp=/includes/0/mount 
bad OK  schema_key_aao_merged.yaml exp=/deps/0/target/key 
bad OK  schema_menu_bool_default.yaml exp=/menu/slots/socks/default 
bad OK  schema_menu_bool_labels.yaml exp=/menu/slots/socks/labels 
bad OK  schema_menu_control_extra.yaml exp=/menu/slots/socks/values 
bad OK  schema_menu_control_missing_default.yaml exp=/menu/slots/shoes/default 
bad OK  schema_menu_empty.yaml exp=/menu 
bad OK  schema_menu_float_default_range.yaml exp=/menu/controls/light/default 
bad OK  schema_menu_labels_missing.yaml exp=/menu/controls/hair/labels 
bad OK  schema_menu_outfit_type.yaml exp=/menu/outfit/type 
bad OK  schema_menu_param_pattern.yaml exp=/menu/slots/socks/param 
bad OK  schema_menu_slot_name.yaml exp=/menu/slots/Socks 
bad OK  schema_mesh_aao_auto_merge.yaml exp=/deps/0/target/mesh 
bad OK  schema_note_type.yaml exp=/parts/0/note 
bad OK  schema_part_alt_objects.yaml exp=/parts/1/alt_objects 
bad OK  schema_part_alt_with_slot.yaml exp=/parts/2/slot 
bad OK  schema_part_alt_with_toggle.yaml exp=/parts/2/toggle 
bad OK  schema_part_closed_field.yaml exp=/parts/1/closed 
bad OK  schema_part_covers_region.yaml exp=/parts/0/covers/1 
bad OK  schema_part_fit_missing.yaml exp=/parts/0/fit 
bad OK  schema_part_human_object.yaml exp=/parts/1/human/a 
bad OK  schema_part_id_any_prefix.yaml exp=/parts/0/id 
bad OK  schema_part_id_one_segment.yaml exp=/parts/0/id 
bad OK  schema_part_kind_enum.yaml exp=/parts/0/kind 
bad OK  schema_part_objects_empty.yaml exp=/parts/0/objects 
bad OK  schema_part_objects_no_renderer.yaml exp=/parts/0/objects/0/renderer 
bad OK  schema_part_objects_string.yaml exp=/parts/0/objects/0 
bad OK  schema_part_opening_kind.yaml exp=/parts/1/openings/0/kind 
bad OK  schema_part_opening_region.yaml exp=/parts/1/openings/0/region 
bad OK  schema_part_outfit_type.yaml exp=/parts/0/outfit 
bad OK  schema_part_owner_writers_enum.yaml exp=/parts/0/owner_writers/1 
bad OK  schema_part_path_hash.yaml exp=/parts/0/objects/0/path 
bad OK  schema_part_pb_enum.yaml exp=/parts/0/pb 
bad OK  schema_part_pose_scope_empty.yaml exp=/parts/0/pose_scope 
bad OK  schema_part_pose_scope_selector.yaml exp=/parts/0/pose_scope/include/0 
bad OK  schema_part_renderer_enum.yaml exp=/parts/0/objects/0/renderer 
bad OK  schema_part_slot_pattern.yaml exp=/parts/0/slot 
bad OK  schema_part_source_level.yaml exp=/parts/0/source/0 
bad OK  schema_part_submesh_negative.yaml exp=/parts/0/objects/0/submesh 
bad OK  schema_part_subregion.yaml exp=/parts/0/covers/0 
bad OK  schema_part_toggle_control_pattern.yaml exp=/parts/2/toggle/control 
bad OK  schema_part_toggle_on_yaml_bool.yaml exp=/parts/2/toggle/shown_at 
bad OK  schema_part_toggle_shown_at_type.yaml exp=/parts/2/toggle/shown_at 
bad OK  schema_part_toggle_with_slot.yaml exp=/parts/0/toggle 
bad OK  schema_part_vendor_clip_missing_off.yaml exp=/parts/0/vendor_clip/off_clip 
bad OK  schema_part_vendor_clip_onoff.yaml exp=/parts/0/vendor_clip/on_clip 
bad OK  schema_part_vendor_clip_path.yaml exp=/parts/0/vendor_clip/on_clip 
bad OK  schema_poses_dose_envelope_enum.yaml exp=/poses/dose_envelope 
bad OK  schema_poses_extra_clip_path.yaml exp=/poses/extra_clips/0 
bad OK  schema_poses_library_enum.yaml exp=/poses/libraries/1 
bad OK  schema_poses_pb_default_enum.yaml exp=/poses/pb_default 
bad OK  schema_poses_private_type.yaml exp=/poses/private_clips 
bad OK  schema_poses_sweep_max_field.yaml exp=/poses/sweep_max 
bad OK  schema_region_aggregate.yaml exp=/parts/0/covers/0 
bad OK  schema_render_extra.yaml exp=/render/grab_queue 
bad OK  schema_render_grab_type.yaml exp=/render/grab_point_min 
bad OK  schema_root_chain_field.yaml exp=/chain 
bad OK  schema_root_missing_avatar.yaml exp=/avatar 
bad OK  schema_root_version.yaml exp=/schema 
bad OK  schema_roundtrip_default_k.yaml exp=/roundtrip_default/history_k 
bad OK  schema_roundtrip_default_template.yaml exp=/roundtrip_default/templates/1 
bad OK  schema_target_submesh_negative.yaml exp=/deps/0/target/submesh 
bad OK  schema_target_submesh_with_key.yaml exp=/deps/0/target/key 
bad OK  schema_target_submesh_without_part.yaml exp=/deps/0/target/part 
bad OK  schema_waiver_cause.yaml exp=/waivers/0/cause 
bad OK  schema_waiver_date.yaml exp=/waivers/0/date 
bad OK  schema_waiver_dep_and_rule.yaml exp=/waivers/0/rule 
bad OK  schema_waiver_hash_pattern.yaml exp=/waivers/0/decl_hash 
bad OK  schema_waiver_limit_max.yaml exp=/waivers/0/limit/max 
bad OK  schema_waiver_limit_max_and_min.yaml exp=/waivers/0/limit/min 
bad OK  schema_waiver_metric.yaml exp=/waivers/0/limit/metric 
bad OK  schema_waiver_metric_reference_only.yaml exp=/waivers/0/limit/metric 
bad OK  schema_waiver_missing_by.yaml exp=/waivers/0/by 
bad OK  schema_waiver_missing_hash.yaml exp=/waivers/0/decl_hash 
bad OK  schema_waiver_missing_reason.yaml exp=/waivers/0/reason 
bad OK  schema_waiver_missing_states.yaml exp=/waivers/0/states 
bad OK  schema_waiver_no_target.yaml exp=/waivers/0/dep 
bad OK  schema_waiver_parts_with_dep.yaml exp=/waivers/0/parts 
bad OK  schema_waiver_pb_mode_enum.yaml exp=/waivers/0/pb_mode 
bad OK  schema_waiver_pose_pattern.yaml exp=/waivers/0/pose 
bad OK  schema_waiver_rule_enum.yaml exp=/waivers/0/rule 
bad OK  schema_waiver_rule_no_parts.yaml exp=/waivers/0/parts 
bad OK  schema_waiver_tool_version.yaml exp=/waivers/0/tool_version 
bad OK  sem01_dup_dep_id.yaml exp=/deps/1/id 
bad OK  sem01_dup_part_id.yaml exp=/parts/2/id 
bad OK  sem01_geo_prefix_unmatched.yaml exp=/deps/0/id 
bad OK  sem02_chain_one_member.yaml exp=/deps/0/when 
bad OK  sem02_cond_syntax.yaml exp=/deps/0/when 
bad OK  sem02_numeric_label_unquoted.yaml exp=/deps/0/when 
bad OK  sem03_ctl_label.yaml exp=/deps/0/when 
bad OK  sem03_fragment_menu_atom.yaml exp=/deps/0/when 
bad OK  sem03_unknown_axis.yaml exp=/deps/0/when 
bad OK  sem03_unknown_ctl.yaml exp=/deps/0/when 
bad OK  sem03_unknown_kind.yaml exp=/deps/0/when 
bad OK  sem03_unknown_outfit.yaml exp=/deps/0/when 
bad OK  sem03_unknown_param.yaml exp=/deps/0/when 
bad OK  sem03_unknown_part.yaml exp=/deps/0/when 
bad OK  sem03_unknown_pose.yaml exp=/deps/0/when 
bad OK  sem03_unknown_pose_tag.yaml exp=/deps/0/when 
bad OK  sem03_unknown_slot.yaml exp=/deps/0/when 
bad OK  sem04_chain_duplicate.yaml exp=/deps/0/when 
bad OK  sem04_chain_in_disjunction.yaml exp=/deps/0/when 
bad OK  sem04_chain_negated.yaml exp=/deps/0/when 
bad OK  sem04_leader_keys_incomplete.yaml exp=/deps/0/expect_by_leader 
bad OK  sem04_leader_not_member.yaml exp=/deps/0/expect_by_leader/MMN.pants 
bad OK  sem05_body_axis_mesh.yaml exp=/body_axes/bust/key/mesh 
bad OK  sem05_target_mesh.yaml exp=/deps/0/target/mesh 
bad OK  sem05_target_part.yaml exp=/deps/0/target/part 
bad OK  sem06_grab_on_key.yaml exp=/deps/0/expect 
bad OK  sem06_hidden_with_key.yaml exp=/deps/0/expect 
bad OK  sem06_submesh_not_grab.yaml exp=/deps/0/expect 
bad OK  sem06_value_on_part.yaml exp=/deps/0/expect 
bad OK  sem06_values_with_key.yaml exp=/deps/0/expect 
bad OK  sem08_fragment_part_slot.yaml exp=/includes/0/fragment#/parts/2/slot 
bad OK  sem08_part_outfit.yaml exp=/parts/0/outfit 
bad OK  sem08_part_slot.yaml exp=/parts/0/slot 
bad OK  sem08_toggle_control.yaml exp=/parts/2/toggle/control 
bad OK  sem08_toggle_label.yaml exp=/parts/2/toggle/shown_at 
bad OK  sem09_alt_of_unknown.yaml exp=/parts/2/alt_of 
bad OK  sem10_variant_use.yaml exp=/deps/1/expect/variant/options/1/use 
bad OK  sem11_object_twice.yaml exp=/parts/1/objects/0/path 
bad OK  sem13_interval_reversed.yaml exp=/deps/0/when 
bad OK  sem13_range_reversed.yaml exp=/deps/0/expect/range 
bad OK  sem13_sync_map_order.yaml exp=/deps/0/expect/sync/map 
bad OK  sem14_default_off_slot.yaml exp=/menu/outfit/default 
bad OK  sem15_roundtrip_bare_number.yaml exp=/deps/0/roundtrip/0 
bad OK  sem15_roundtrip_label.yaml exp=/deps/0/roundtrip/0 
bad OK  sem15_roundtrip_param.yaml exp=/deps/0/roundtrip/0 
bad OK  sem15_roundtrip_slot_range.yaml exp=/deps/0/roundtrip/0 
bad OK  sem16_waiver_dep.yaml exp=/waivers/0/dep 
bad OK  sem16_waiver_rule_part.yaml exp=/waivers/0/parts/0 
bad OK  sem16_waiver_superseded.yaml exp=/waivers/0/dep 
bad OK  sem17_exclude_unknown.yaml exp=/geo_defaults/exclude/0 
bad OK  sem18_include_body_mismatch.yaml exp=/includes/0/fragment 
bad OK  sem18_include_mesh_mismatch.yaml exp=/includes/0/fragment 
bad OK  sem18_include_missing.yaml exp=/includes/0/fragment 
bad OK  sem19_pending_in_cases.yaml exp=/deps/0/human 
bad OK  sem20_dup_param.yaml exp=/menu/slots/shoes/param 
bad OK  sem22_class_conflict.yaml exp=/deps/1/id 
bad OK  sem22_value_conflict.yaml exp=/deps/1/id 
bad OK  sem23_pose_scope_unknown.yaml exp=/parts/0/pose_scope/include/0 
bad OK  sem23_waiver_pose_unknown.yaml exp=/waivers/0/pose 
bad OK  sem24_supersedes_cycle.yaml exp=/deps/1/supersedes/0 
bad OK  sem24_supersedes_self.yaml exp=/deps/0/supersedes/0 
bad OK  sem24_supersedes_unknown.yaml exp=/deps/0/supersedes/0 

ok files: 8  ok failures: 0   bad files: 250  bad mismatches: 0

$ python3 sv.py ok; python3 sv.py bad | 计数   # reviewer's independent schema-layer script (unmodified)
OK  03a_工程A.yaml []
OK  03a_h3.yaml []
OK  03a_milfy.yaml []
OK  03a_project-c.yaml []
OK  工程A_min.yaml []
OK  features_misc.yaml []
OK  fragment_MMN.decl.yaml []
OK  fragment_features.decl.yaml []
    188 GOOD
     62 SCHEMA_PASS

$ python3 coverage.py
fields total 233 covered by ok 232
  NOT IN OK: ('menu.slots', 'labels')
field names total 138
fields without a negative (by name): 0
open object schemas (no additionalProperties:false, not a map): ['#/$defs/dep/allOf/3/if/properties/expect', '#/$defs/fragmentDep/allOf/3/if/properties/expect']
properties without description: 29 places, all in if/then condition subschemas (not field definitions)

$ pose id cross-check: library produced by actual pose_frames.py --envelope extreme run (Project A) vs built-in list
library entries 360 | built-in list misjudged [] | warnings only (project-private) 65
library tags not in vocabulary: [] | all pose ids used in examples are in library: True
```
</details>

## 2026-09-18 rev 1 (first draft)

Turned 03a Q1-① into a closed schema: handling of the 12 undefined fields see CONDITION_GRAMMAR §7; defined the writer vocabulary and the two confidence columns; objects must carry renderer; added the menu input section, geo_defaults, the waivers five-tuple; 7 positive examples (including rewrites of the 14 samples from 03a), 165 counterexamples.

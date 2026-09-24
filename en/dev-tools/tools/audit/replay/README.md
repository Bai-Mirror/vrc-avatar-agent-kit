> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/replay/README.md)

# Defect replay library `replay/` (kickoff checklist T-15; expanded by C-06)

Real defects that have been fixed are patched back into the workspace in reverse, file by file, plus one injected sample, for use by **the single T-16 Play run
(E2/E3/E4/E12)**, **E11 blind drafting**, **E6 geometric positive samples**, and **tool revision regression (03 §4.4 ⑦)**.
For criteria and ground-truth definitions see `_长程任务_20260918/感知机制研究/03_研究与方案.md` §4.5 / §4.6
and the T-15 section of 04; for the expanded entries see work checklist C-06.

## Nine cases

First batch of 4 (Project A, fix commit `ceb4070b`):

| case | Type | dep_id | Defect in one sentence | Key metric (before fix → after fix) |
|---|---|---|---|---|
| `grab_headdress` | git patch | `工程A.grab.headdress_color_chain` (U4) | Headdress recolor animation references the vendor original (queue 2450), grab point falls back | Grab point 2450 → 3050; grab-pass chain hits 24 → 0 |
| `coat_double` | git patch | `kaguya.outer_variant_by_bust` (D5/U2) | Alternate coat `outer_breast_big_open` active simultaneously with `outer` | Overlap ratio 70% → 0 (no big_open in the build output) |
| `mmn_foot` | git patch | `MMN.foot_flat` (D3/U1) | When shoes are on and socks off, nobody writes the flat-foot key; toes poke through the closed-toe shoe | Toe poke-through 63/170 → 0; `Foot_heel_OFF` 0 → 100 |
| `inject_parker` | Injection script | `RePoppin.shirt_under_parker` (D4a/U3) | Delete the RePoppin row of `PART_SHAPES`; `Parker_on` has no writer | `Parker_on` expected 100, baseline after injection 0 |

Second batch of 5 (defects fixed by hand this round, errors.md E1/B1/B2+B3/R1/Z1–Z3):

| case | Type | dep_id | Defect in one sentence | Key metric (before fix → after fix) |
|---|---|---|---|---|
| `e1_bust_sync` | git patch | `RePoppin.bust_shape_sync` (D5) | Project E: nobody syncs the bust-shape keys of five Re-Poppin items; with bust shape maxed, both breasts poke through | Key on item constantly 0 → identical value by value to the body; front skin-color pixels 6,822 → 837 |
| `b1_rurune_flatfoot` | git patch | `工程D.rurune_black_foot_flat` (D3) | Project D: Rurune-Black platform shoes don't have the flat-foot key attached | `Foot_heel_OFF` absent (=0) → 100 (shoes on) / 0 (shoes off) |
| `b23_esmera_nipple` | git patch | `工程D.esmera_nipple_bust_sync` (D5) | Project D: Esmera nipple patches lack `Breast_small` / `Breast_big(limit)` and nobody syncs them | Gap p50 5.74 / 14.95 mm → 1.28 / 1.66 mm |
| `r1_lopear_shrink` | git patch | `工程B.lopear_shrink_owner` (D4a) | Project B: 11 shrink keys of the lop-eared rabbit are attached to the whole set; after removing an item the body is missing | 11 keys constantly 100 → follow covering item visibility |
| `z_outfit_menu` | git patch | `工程F.outfit_menu_visibility` (menu/visibility) | Project F: broken Outfit submenu + three Shellmarin items on the same toggle + glasses semantics reversed | 9 toggles with zero effect → submenu deleted; three items independent; default hidden / 0 shown / 1 hidden |

Each case directory contains: `patch.diff` (git patch) or `inject.py` (injection script), `expect.json`
(dep_id / state set / responsible writer / metric ranges / positive-negative controls / evidence), and `README.md` (this case's notes).

`b23_esmera_nipple` merges B2 and B3 from errors.md (same asset and scene; split apart they would overwrite each other);
`z_outfit_menu` merges Z1–Z3 (same fix commit). `e1_bust_sync` is unrelated to Project A;
it is the first replay case of the Project E project.

## Usage

```bash
R=开发工具/通用工具/审查/replay
python3 $R/replay.py list                 # list the 9
python3 $R/replay.py status               # status of the 9 + manifest check (acceptance command)
python3 $R/replay.py verify               # on a clean tree, verify patches apply both forward and reverse (temporary change, restored at the end)
python3 $R/replay.py apply  --all         # patch all back (idempotent)
python3 $R/replay.py revert --all         # git checkout HEAD -- <the 19 manifest files>
python3 $R/replay.py apply  mmn_foot      # single case
python3 $R/replay.py selftest             # clean tree → apply --all → check/reproducible (rebased entries use semantic assertions) → revert
```

> **From task BR on: `apply` first runs `git status --porcelain`, and refuses if non-empty** (prints the first 50 entries).
> Motivation: apply/revert modify each project's working tree; when there are already a pile of uncommitted changes (other sessions, unsaved Unity),
> patching and then `revert` would check them out along with everything / the context wouldn't match. After confirming those changes are unrelated to this library's manifest,
> you can explicitly skip the check with `python3 $R/replay.py apply --allow-dirty mmn_foot` (the tool prints a WARNING).
> `selftest` uses an internal apply and is not affected by this global check (it only requires the manifest to be clean anyway).

`status` exit code: 0 when the working tree within the manifest matches "the union of files of applied cases", otherwise 1.
It also prints lock file status and tracked changes **outside the manifest** (not counted as failure, only a notice).

> `selftest` modifies each project's working tree. To not touch the real projects at all, create a sparse worktree and point
> `--root` at it: `git worktree add --no-checkout --detach /tmp/wt HEAD` + sparse-checkout
> the manifest files, then `replay.py --root /tmp/wt selftest` (this C-06 self-test was run exactly this way).

## Locks and safety conventions

`apply` / `revert` **temporarily modify the working trees of the projects in the manifest** (Project A, Project E, Project D,
Project B, Project F). Per the dispatch conventions:

1. Before `apply`, first create the lock file
   `_长程任务_20260918/派工/tmp/T15_REPLAY_ACTIVE` (write the time into it);
2. After `revert --all`, confirm `git diff -- <this library's manifest>` is empty, then delete the lock file;
3. **Under all circumstances you must revert cleanly before finishing**.

replay.py only **detects and prints** the lock, it doesn't enforce it (the lock holder may be a Unity session or another DSH task,
which the tool can't determine); when the lock is missing it prints a `WARNING`.

`revert` only does `git checkout HEAD -- <this library's manifest files>`, and **never reverts tool files**
(`Assets/Editor/AvatarAudit/*`, `开发工具/通用工具/审查/*.cs`, etc.) or changes outside the manifest.
Note: the fix commit of `b1_rurune_flatfoot` also changed `ProjectSettings.asset` (a Play side effect);
per the SOP it is not in the manifest, and revert won't touch it.

Stacking on shared files: `coat_double` and `inject_parker` share `MenuGenA2.cs`;
`b1_rurune_flatfoot` and `b23_esmera_nipple` share `工程D.unity`. They are in different regions
and can be stacked; but **a single-case revert also restores the other case in the shared file** (both go back to HEAD);
`revert --all` is the recommended usage.

## Manifest (19 files, relative to the repository root)

```
工程A/Assets/Editor/AvatarGen/MenuGenA2.cs                 (coat_double, inject_parker)
工程A/Assets/_Work/工程A.unity                     (mmn_foot)
工程A/Assets/_Work/Gen/Clip/Dial_头饰色.anim                (grab_headdress)
工程A/Assets/_Work/Gen/Clip/Dial_整套.anim                  (coat_double)
工程A/Assets/_Work/Gen/Clip/On_部位_外套.anim               (coat_double)
工程A/Assets/_Work/GrabQueue/glass_virgo_q3050.mat         (grab_headdress, deleted on apply)
工程A/Assets/_Work/GrabQueue/glass_virgo_q3050.mat.meta    (grab_headdress, deleted on apply)
工程E/Assets/工程E.unity                                          (e1_bust_sync)
工程D/Assets/工程D.unity                                          (b1_rurune_flatfoot, b23_esmera_nipple)
工程D/Assets/_Work.meta                                          (b23, deleted on apply)
工程D/Assets/_Work/Esmera_BreastSmall.meta                       (b23, deleted on apply)
工程D/Assets/_Work/Esmera_BreastSmall/Breast_Bandage_BreastSmall.asset      (b23, deleted on apply)
工程D/Assets/_Work/Esmera_BreastSmall/Breast_Bandage_BreastSmall.asset.meta (b23, deleted on apply)
工程B/Assets/_Work/工程B_Milfy.unity                          (r1_lopear_shrink)
工程F/Assets/Kipfel.unity                                        (z_outfit_menu)
工程F/Assets/_Work.meta                                          (z, deleted on apply)
工程F/Assets/_Work/Menu.meta                                     (z, deleted on apply)
工程F/Assets/_Work/Menu/Kipfel_ExMenu_FT_noOutfit.asset          (z, deleted on apply)
工程F/Assets/_Work/Menu/Kipfel_ExMenu_FT_noOutfit.asset.meta     (z, deleted on apply)
```

## How the patches were made (reproducible)

Each `git_patch` case's `expect.json` records `fix_commit` / `pre_fix_rev`; the patch is a **reverse**
diff (patching the fixed tree back to pre-fix), generated with `git diff <fix_commit> <pre_fix_rev> -- <case 的文件...>`;
`replay.py selftest` recomputes from these two commits and compares byte for byte with the patch on disk:

```bash
git diff <fix_commit> <fix_commit>^ -- <case 的文件...>
```

* First batch: `fix_commit = ceb4070b`.
  * `grab_headdress` / `coat_double`: whole-file reverse diff, saved verbatim.
  * `mmn_foot`: after the whole-file reverse diff, **only the two hunks containing `232539723` are kept**
    (the newly created component `&232539723` and its registration in the PrefabInstance's `m_AddedComponents`),
    removing two lighting/serialization noise hunks, `RenderSettings.m_IndirectSpecularColor` and PhysBone `cachedExecutionGroupIndex`.
    Both hunks reference the same fileID; neither can be omitted.
    The case marks this filter with `patch_filter: "mmn_fileid"`.
  * `inject_parker`: no commit; `inject.py` deletes the line
    `("A2_Coat", "in:Outfit_RePoppin/(A)Shirt", "Parker_on", 100f, 0f),` from `MenuGenA2.PART_SHAPES` (idempotent).
  * `git diff ceb4070b HEAD -- <第一批 7 文件>` is empty, so the reverse patch applies cleanly,
    and `revert` with `git checkout HEAD --` returns to the fixed state.
* Second batch: `fix_commit` is respectively `2acdb32a`(e1) / `6d5eb1e7`(b1) / `da79abfc`(b23) /
  `67233c44`(r1) / `862686ad`(z); whole-file reverse diff (including deletion hunks for newly created files/directory `.meta`).
  * `b23`'s pre side takes `b34a6010^` (the two commits B2 and B3 merged into one case).
  * The files of `b1` and `r1` were changed again by other commits after the fix commit (b1 by the two b23 commits,
    r1 by `97ceccae`); the patch is generated from the fix commit, but on the current HEAD
    `git apply --check` passes (changes in different regions), and apply only patches back that defect's hunks.
  * The reverse hunks of newly added files (`glass_virgo_q3050.*`, `Breast_Bandage_BreastSmall.*`,
    `Kipfel_ExMenu_FT_noOutfit.*` and directory `.meta`) are **deletions**;
    apply deletes them, and revert retrieves them from HEAD.

### Rebasing onto HEAD (task CF, 2026-09-19)

After the fix commits, the four scene files of `mmn_foot`, `b1_rurune_flatfoot`, `b23_esmera_nipple`, `z_outfit_menu`
were changed again by the generator/subsequent fixes (component fileIDs reordered, extra entries in `m_AddedComponents`,
resources added/removed); the context of a verbatim `git diff <fix> <pre>` no longer matches HEAD,
and `replay.py verify` reported `打补丁失败 …:<行号>` ("patch failed …:<line number>").

These four `expect.json` now carry `"regen": "head_rebase"`:

* `rebase` records the rebase's **reason / method / worktree HEAD at generation time**; `pre_fix_rev` still preserves
  the defect's provenance (the rev before the fix commit), but is **no longer used to recompute the patch verbatim**.
* `patch.diff` is obtained by rebuilding the defect state on a sparse HEAD worktree according to **defect semantics** and then `git diff HEAD`:
  deleting the components/registrations/newly created resources introduced by the defect, while also removing serialization noise hunks such as lighting, PhysBone, and float
  precision (they don't affect defect semantics).
* `defect_assert` lists "markers that must be absent/present after patching" (e.g. after patching mmn_foot there must be no
  `Foot_heel_OFF`, after patching b23 there must be no `Esmera_BreastSmall` resource); `verify` and
  `selftest` use it in place of the "verbatim reproducible" check, ensuring the patch really returns to the defect state.
* When a rebuild is needed: `git worktree add --no-checkout --detach <wt> HEAD` + sparse-checkout
  this library's manifest, edit the files per `rebase.how`, and overwrite `patch.diff` with `git diff HEAD`.
  Failed hunks can be landed on HEAD with `git apply --reject <旧补丁>`, then fill in the `.rej` by hand.


## Regression usage (03 §4.4 ⑦)

After a tool (geometry / grab-pass / validator / generator) revision:

```bash
python3 $R/replay.py verify                       # the patches themselves aren't broken
python3 $R/replay.py apply --all                  # patch the defects back
#   → rerun the generator + one Play capture (T-16 steps ①–③)
python3 $R/replay.py revert --all                 # restore
#   → capture the same batch again after the fix (T-16 step ⑤)
```

If any case no longer reports a violation under the new tool = tool regression; record it in the work log.

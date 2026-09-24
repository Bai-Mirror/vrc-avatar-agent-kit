> 🌐 English translation · [中文原文](../../../../开发工具/SOP/50_服装发型装配/部件理解与菜单编排.md)

> ← [50 · Outfit and hair assembly](../50-outfit-and-hair-assembly.md)

# 50 · Part understanding and menu layout (part atlas)　🤖 → 🎨

**Purpose**: when fitting a garment, first work out for each of its parts **what it is, when it's visible, and how conspicuous it is within the set**, then decide how it enters the menu, how conflicts are handled, and what easter egg material there is; written up as a “part atlas” filed per product and reused across projects.
**Output**: `开发工具/素材包说明/<商品名>/部件图鉴.md` (template `开发工具/素材包说明/_部件图鉴模板.md`, not public), in the same directory as the `部件清单.json` and `部件图/` written by the capture tool.
**Origin**: requested by the author on 2026-09-22 (key points relayed in `_长程任务_20260918/作业清单_全部未完成.md` §H, `:963-974`).
**Status**: H-01 **reviewed by Claude 09-22 13:5x** (workflow wmynetj49: 6 lanes mined 311 conventions, 99 evidence items spot-checked, 21 usability review items fixed). Entries marked “candidate” or “pending review” are handled per section 2 “Default actions when undecided” of [DSH execution points](part-understanding-and-menu-layout/dsh-execution-points.md); **all other rules DSH must follow**. Capture tool: H-02 on 09-22 shot 4 sets, 36 parts, 222 images, acceptance partially passed (`A/_施工记录.md:913,931-932`); H-02b rework (side-view leakage, per-part framing for full sets) reshot as 300 images, Claude acceptance passed at 06:35 (`:955,969`). Usage in `开发工具/通用工具/部件图鉴/README.md`.
⚠ Not the same thing as the [14 selection atlas](../14-selection-atlas.md) (the catalog for clients to pick assets from).

## Source abbreviations and source levels

Subpage sources are written as `path:line`, with path abbreviations (note for the public version: apart from `sop/`, these are all unpublished records from the original workspace, used only as source markers; see the header of [00 Overview](../00-overview.md)):

`sop/` = `开发工具/SOP/`　`pkg/` = `开发工具/素材包说明/`　`lt/` = `_长程任务_20260918/`　`hist/` = `_历史工程/`　`A/` = `匿名工程A/` (anonymous Project A)　`B/` = `工程B/` (Project B)　`C/` = `工程C/`　`D/` = `工程D/`　`E/` = `工程E/`　`F/` = `工程F/`　`G/` = `工程G/`

Source levels, ranked like this on conflict: **〔explicit〕 user stated explicitly > 〔corrected〕 user correction > 〔convention〕 Claude convention > 〔vendor〕 vendor convention**.
- 〔practice〕 = what the user actually did in their own old projects, not a verbal requirement; treat only as samples that include both good and bad examples (`CLAUDE.md` “division of labor” section).
- 〔explicit·relayed〕 = documents say the user said it, but the original words can't be found.
- In Project A the “client” is the user themself (memory personal-vs-client-projects), so “client decisions” there count as 〔explicit〕.
- 〔vendor〕 ranks last and only governs **menu preferences**; facts like “which items form a group, parameter polarity” follow the vendor clip ([03 Assembly and conflict rules](../03-assembly-and-conflict-rules.md)) — only clips in the vendor directory count, ours don't ([Conflict checklist](part-understanding-and-menu-layout/conflict-handling-checklist.md) C03).
- The full text of the user's 09-22 words is in the first paragraph of `lt/作业清单_全部未完成.md` §H (added at 13:5x).

(In the Chinese original the levels are written 〔明〕〔纠〕〔惯〕〔厂〕〔实〕〔明·转述〕; the English pages use 〔explicit〕〔corrected〕〔convention〕〔vendor〕〔practice〕〔explicit·relayed〕 respectively.)

## 1. Trigger moments and checkable questions

**When to check**: ① fitting an outfit, before step 1 of [50](../50-outfit-and-hair-assembly.md); ② building or changing the menu for an already-fitted outfit, before step 2 of [60](../60-menu-and-animation-layers.md); ③ a DSH task brief contains “fit / change some outfit”.

**What to look up**: the same product has many names (asset directory name, Booth product name, vendor prefab name, our scene root name are often all different), so **look up by Booth product ID**:

```
ls -d <素材库>/*-<商品号>                            # product ID: end of the asset path, item_id in .booth-meta.json
grep -rl '<商品号>' 开发工具/素材包说明/*/部件图鉴.md
ls 开发工具/素材包说明/<商品名>/                     # is there a 部件清单.json, 部件图/
```

For assets not from Booth with no product ID, grep by directory name, prefab name and scene root name one by one; when creating a new atlas, write all these aliases into the header.

| Lookup result | Next step |
|---|---|
| Atlas exists, includes this order's base avatar | First read the “menu recommendations”, “conflict handling” and “undecided” columns before acting; new wording decided by the user in this order is written back into the atlas with date and original words |
| Atlas exists, missing this order's base avatar | Only add “base avatar adaptation differences” and the affected parts; check the target directory before reshooting (section 2 step 2) |
| Only the list and images | Run from step 3 |
| Nothing | Build the file in the order below |

**Order when missing**: the capture tool clones the avatar in the scene to shoot, and the config's `root` is the outfit root name in the clone (`开发工具/通用工具/部件图鉴/PartAtlasCapture.cs:26`; README “config fields”); if the outfit isn't attached it can't shoot. So: [50](../50-outfit-and-hair-assembly.md) steps 1–3 (probe, judge compatibility, attach and confirm rendering) → step 2 capture and data → steps 3–6 build the atlas → then 50 step 4 (shrink keys) and 60 step 2 (menu).
**There is only one hard gate: menus and shrink keys may not be finalized before the atlas is complete.** Fitting tasks don't stop when the atlas is missing; only tasks that build or change menus stop and report when the atlas is missing.

**When it can't be done** (Unity occupied, capture tool not working): first fill the “description from images” and “vendor's own switches” columns from existing renders and vendor clips, write visual weight as “TBD”, and mark menu recommendations “pending atlas completion”.

## 2. Process (six steps)

| Step | What | Who | Exit criterion |
|---|---|---|---|
| 1 Look up | Previous section | Claude / DSH | One of the four states |
| 2 Data + capture | Capture tool `开发工具/通用工具/部件图鉴/` (per order only change the project's `_交付/部件图鉴_配置.json`) produces the list and 6～8 images per part; then fetch vendor showcase images and `.booth-meta.json` | DSH (Unity, scene read-only) | List entry count = the set's renderer count (including static MeshFilter parts inside the skeleton); `maxRenderersPerOutfit` = 0; report says “hierarchy md5 consistent”; target directory originally non-empty and the task brief doesn't say “overwrite same base avatar” → stop and report (output path doesn't distinguish base avatars, `PartAtlasCapture.cs:316-318`; png isn't in git, overwritten means unrecoverable) |
| 3 Label | Blind labeling (anonymous images, no mesh names or material names in the task brief) → name matching; plus one set-level comparison round | DSH `--model vision` | `dsh_task.js --images` per-image verification PASS (rejected ones don't count); first-round task brief and input image paths grep to no mesh or material names; all images read (sensitive images may be sent externally: the user decided 09-22 13:3x) |
| 4 Judge | Three axes → classification → menu recommendation → atlas layer of the conflict checklist → easter egg material, fill the template | Opus demonstration (H-03), DSH rollout (H-04/05) | All template fields; every N/A has a reason |
| 5 Falsify | Send visual conclusions to agy | Claude | agy record paths written into the atlas “evidence” column |
| 6 Decide | Visual weight, easter eggs, default values go to the user (AskUserQuestion) | Claude | The atlas “user wording” table has the original words |

For text masking, batching, sensitive images and difference pixels in step 3 see [Blind labeling and sensitive images](part-understanding-and-menu-layout/blind-labeling-and-sensitive-images.md).

## 3. Key points of each stage (details in subpages)

- **Three axes**: what it is × visibility condition (always visible / visible only when the outer layer is removed / visible only in specific poses) × visual weight (selling point / accent / base layer). **Switch granularity is decided by weight; the visibility condition only governs default values, texture tiers and conflict checks**: the user said on 09-22 that the Velour nipple covers should be “classified as underwear, but not toggled together with the panties”, because they are a selling-point item with obvious visual weight in a bold outfit 〔explicit〕. Names are only hints. → [Three axes and the naming trap](part-understanding-and-menu-layout/three-axes-and-naming-trap.md)
- **Classification**: the criteria, default menu handling and exceptions for each of 14 classes; the ambiguous “chest garment” is split into bra and corset. → [Part classification table](part-understanding-and-menu-layout/part-classification-table.md)
- **Menu layout**: separate switch or merged group, follow the full set, whether to use a radial, default values, hook vendor parameters or write the mesh, wording; each item tagged with its source, with trade-offs written where they conflict (including “separate nipple-cover switch vs bras under Top”). → [Menu layout decisions](part-understanding-and-menu-layout/menu-layout-decisions.md)
- **Conflict handling**: C01–C15, split into atlas layer and project layer; the project layer leaves only one line in the atlas, pointing to 60 steps 3/5. → [Conflict handling checklist](part-understanding-and-menu-layout/conflict-handling-checklist.md)
- **Easter eggs**: in the past there were only “play/gimmicks”; the atlas only records product-layer “easter egg material”, and whether to adopt it is decided by the project per requirements. → [Easter egg item layout](part-understanding-and-menu-layout/easter-egg-item-layout.md)
- **Vision subagent division of labor**: models judge “what it is, whether it's conspicuous”; counts, alignment and clipping go through geometry data; visual conclusions go through agy falsification. → [Visual division of labor and evidence](part-understanding-and-menu-layout/visual-division-and-evidence.md)
- **DSH dispatch**: fixed task-brief lines, default actions when undecided, integration points (H-06: 50/60/00/dispatch pages landed, lookup script pending). → [DSH execution points](part-understanding-and-menu-layout/dsh-execution-points.md)

## 4. Trade-offs

- **Visual weight has no pixel threshold**. Difference pixels can only measure “visible or not”, not “selling point or not” — nipple covers are small in area yet a selling point. So weight comes from showcase images, the product description + candidates from vision models, with the user deciding; pixel counts are only supporting evidence. With no showcase images write “TBD”, and list both menu recommendations (merged / separate) for the user to choose; don't pick yourself.
- **The atlas records the product layer; the project records this order's implementation**. Slot numbers, parameter names, priority chains and full-combination acceptance go into the project's `菜单结构.md`; wording the user decided in some order is written back into the atlas with a date, carried over by default in the next order, but can be overturned.
- **Body/foot blend shapes are recorded only as candidates**: the old methods are unverified (`CLAUDE.md` “division of labor” section; [Foot-shape and shrink key ownership](foot-and-shrink-key-ownership.md)). The atlas records “candidate keys + candidate host + to verify”, not conclusions.
- **Filing cost**: each set costs one extra capture round and two vision labeling rounds, in exchange for no longer classifying by name. For evidence of the cost see the examples in section 3 of [Three axes and the naming trap](part-understanding-and-menu-layout/three-axes-and-naming-trap.md) — most were only exposed at the “all off” cell or by the user's own testing.
- **Delivered orders are not reverted automatically**: problems in old orders exposed by the atlas (the nipple-cover-type items in Projects C and D) are listed in the atlas's “undecided” column, and the user decides whether to change them.

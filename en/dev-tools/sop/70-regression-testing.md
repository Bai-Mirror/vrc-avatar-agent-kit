> 🌐 English translation · [中文原文](../../../开发工具/SOP/70_回归测试.md)

# 70 · Regression test (auditing a project: data first)　🤖

> Rewritten 2026-09-19 based on the real-world audits of seven orders on 09-18/19. The old version (image-by-image per combination, overturned after an all-PASS) was moved to [`70-regression-testing-legacy-20260918.md`](_legacy/70-regression-testing-legacy-20260918.md) and serves only as a counter-example; conclusions that remain valid have been lifted into this page's subpages and into Troubleshooting (mapping in [`README.md`](_legacy/README.md)).
> Principle: **first let the tools read "visibility, every blend shape's value, and who is writing it" into data; the data picks out candidates, and images are only for pinpoint re-checks**, and conclusions from images must go through agy (blind tests preferred). Visual inspection is the most expensive and least reliable (the user's ruling, 09-18).

The tools are in `开发工具/通用工具/审查/` (docs: [`README.md`](../tools/audit/README.md), [perception/README.md](../tools/audit/perception/README.md)); for an overview see the [Tool index](00-overview/tool-index.md). Output goes to `_长程任务_20260918/审查产出/<工程>/` (or the directory agreed for this order).

---

## Steps

DSH executes by default; the lead agent does independent acceptance and is responsible for visual judgement. **Full builds and NDMF/VRCFury preprocessing must run in batch mode.** Play in steps 2–4/6 is limited to a self-launched interactive Unity: with the persisted full build output loaded, and all Play preprocessing entry points isolated. The current T1/T4 tools both need Play, with the entry point `Tools/AvatarAudit/Run Request`; `AuditBatch.ExportInventory` only does a non-Play inventory. **There is not yet an accepted general flow for "batch output → Play without rebuilding"**; if a prerequisite is missing, record `blocked/未测` (not tested) and continue offline preparation — never enter Play directly on the source scene. For switches, request samples and restore requirements, see [Play entry points and blockers](70-regression-testing/common-pitfalls/editor-invocation-and-resend.md).

### 1 · Preparation sheet (DSH, offline)
Dispatch DSH to read the scene/prefabs/controllers/clips and write `<工程>/_审查准备_<日期>.md`: avatar root, expression parameters, radial tiers (tier taken by i/n, audit uses (i+0.5)/n), body-part toggles and the objects they control, **blend-shape writer list** (vendor clips, MA ShapeChanger/BlendshapeSync, our generators), enclosed-part list, grab-pass materials, the 3 most suspicious items. Also draft the T1 request.
- The preparation sheet is a snapshot: conclusions overturned by the audit must be written back or flagged in the work log.

### 2 · Deployment and post-build menu (DSH·Unity, lead-agent acceptance)
- Deploy to `Assets/AvatarAudit/` with `sync_audit.py <工程>`; while DSH is modifying the audit source, add `--from-git HEAD` (otherwise the half-finished code fails to compile and the MCP bridge won't come up). T1 v4 checks the source hash in `Assets/AvatarAudit/VERSION` and refuses to run on mismatch.
- Once the Play prerequisites above are met, run the **T4 menu export** (`tool: menu`): get the real post-build parameter names (MA auto parameters carry a hash suffix), each control's actual value and reachability (whether the vendor submenu is hooked into the actual menu tree). Use it to fix the request in the preparation sheet; don't guess parameter names.

### 3 · T1 full scan (DSH·Play, lead-agent acceptance)
- `reset: declared` (reset to expression-parameter defaults; driver target parameters excluded from reset), with probes `grab_chain` (grab-pass chain), `coincident` (coincident meshes), `range` (out-of-range weights). State set = every radial tier × each body part single-off + all on / all off + both ends of body-shape parameters such as breast shape.
- How to read: state by state, compare the visibility diff and blend-shape diff between "all on" and "single-off" (visible parts only); use the i/n convention for radial tiers, don't take tier boundary values.

### 4 · Real sequences (DSH·Play, `reset: none`)
Run "off → on → switch tier → switch back" in real click order. **State-bleed defects only show up in real sequences** (Project B: in the purchased-outfit tier, turning a body-part toggle off and back on made the base-avatar cardigan pop out). For each order, run "off then on" at least once for every body-part toggle, and "switch away then back" at least once for every radial.

### 5 · Same-name key following and mismatch (DSH executes, lead-agent acceptance)
- The part inventory (`Export Part Inventory` or headless `AuditBatch`) produces key_follow: a garment carries the body's same-name key but nobody drives it → candidate.
- `key_follow_verdict.py` judges with T1 states: only a difference >5 from the body while the garment is visible counts as a mismatch.
- **For a mismatch, measure the geometry before judging** ([Visible consequences of shrink keys](50-outfit-and-hair-assembly/shrink-key-effects-render-comparison.md), [Breast-shape following](50-outfit-and-hair-assembly/breast-follow-keys-unsynced.md)): in edit mode set the body key to both ends, `BakeMesh` and compare the quantiles of the part-to-body nearest distance; a p95 change <1 mm is recorded as no visible consequence.
- It cannot find two classes: **key missing on a part** (Project D pasties lacking `Breast_small`), and **writer attached to the wrong part** (lop-eared rabbit shrink keys on the whole outfit, MMN flat-foot key on the socks) — these two are checked manually by comparing step 3's readings against the writer list.

### 6 · Pinpoint image checks on candidates (Claude·Play → agy)
Render only the candidates picked out by the data (T3 turntable):
- First hide occluders (hair, bags, outer clothing, `hide_renderers`/`only_renderers`), tile a 2×2 thumbnail to scan the framing first, then compare.
- When comparing "before/after fix" or "key 0/100", do a **positive control** (render only the body; the pixel difference must be obvious); in Play, AAO merges/renames meshes and reorders bones, so **don't swap meshes in Play for a control** — swap meshes in edit mode.
- Send to agy: phrase the prompt as "my conclusion, please overturn it", or a mixed blind test (answer key kept locally, `agy_panel` images numbered from `img00`). If agy only nitpicks the framing, re-render and resend.

### 7 · Fix and re-verify
- Fix small problems directly; for each fix: read the values back via T1 (e.g. the garment's and body's breast-shape keys identical value by value across three tiers), and render + agy if needed; **generator changes require a full regression run** (rerun the same request and diff state by state before vs. after the fix: only the expected differences are allowed).
- After each step, append to the project's `_施工记录.md` and `ws_git.py commit` (list only the paths to commit; `ProjectSettings.asset` changed by Play is restored at the end of the session).

---

> → [Required checklist: what actually occurred in seven real orders](70-regression-testing/required-checklist-test-cases.md) — same-name key not synced, key missing on a part, writer on the wrong part, state bleed, grab-pass point too early, alternative parts shown together, dead menu, deleted area relying on another part to cover it, delivery root missing a component, one toggle controlling several parts, each with its "how to check" landing point.

## Showcase-shot "outfit hit" assertion (trigger: before looking at images)

**Showcase shots must name the delivery outfit and assert "N parts named, N parts on".** Historical measurement: across 8 projects + client orders, a batch had 0 "outfit" hits (Rurune 7/7 and H6-Shinano 1/1 were the few done right); all the images existed yet couldn't prove what the delivered parts look like (`历史工程总览` §2.5, verified in this document).

- **Criterion**: the enabled outfit tiers can be read from the generation record / spec JSON; the number named equals the number of parts actually on — off by one is a failure.
- **If it can't be achieved**: reshoot, or state "the images do not represent the delivery outfit"; don't substitute old images ([90 Delivery](90-delivery-packaging.md)).
- **Implementation pitfalls** (compare `activeSelf`, not `activeInHierarchy`; a second avatar root in the scene gets captured too; plugin placement targets are real renderers) → [Clear the stage before whole-avatar renders](troubleshooting/observation-criteria/rendering-and-framing/clear-scene-before-full-render.md).

## Rendering under the Play convention (clamp=1)

**To judge the effect of extrapolated/out-of-range blend shapes, always render under the Play convention (`legacyClamp`=1).** In edit mode, because AAO forces the clamp bit to 0, **you can see extrapolated shapes that the client cannot** — treating the edit preview as the client's result is wrong ([Bake and compensation](30-face-sculpt/baking-and-compensation.md); for `legacyClamp` see [04](04-build-log-and-version-control.md) and pending item E-未核-08).

## Camera angles and dynamic poses

The default 4 shots (front / three-quarter / back / face) are not enough; add the four kinds **side 90°, low angle, top-down, hands**, plus the dynamic frames "walking, sitting, leg raised"; camera positions must cover the part's "side where it gives itself away" (open-heel items need a rear view) → table and criteria in [Camera angles and dynamic poses](70-regression-testing/camera-angles-and-dynamic-poses.md).

## Common pitfalls
`execute_code` resends, SIGSEGV/high CPU on entering Play, `scene.isDirty` before quitting Unity, whole T1 read-back batch aborted, 6-decimal echo, identifying the body by skinning weights and other pitfalls hit in real runs → [70 Common pitfalls](70-regression-testing/common-pitfalls.md).

## Coverage record
At the end of each order's audit, write one coverage line in the work log: what was run (number of T1 states / number of real sequences / T3 / T4 / key_follow / geometric distances), and **write out what was not run**. Once the perception mechanism's declaration reconciliation (`verdict.py`) is in place it merges into step 5; see `_长程任务_20260918/感知机制研究/04_第一期开工清单.md`.

### Required combinations T1–T9 (by project type, E §5)

Run each type the order belongs to; "single on / all on / all off" are common to all types, and only what is **unique to each type** is listed below.

- **T1 independent toggles, no mutual exclusion**: whether turning off while on reverts; breast/waist when on together with a body-key ShapeChanger.
- **T2 Int multi-way mutual exclusion** (3bitInt / KZ ClothChanger): each tier 0→N; **switching back and forth between tiers**; behavior when the parameter isn't in the sync table; alignment with `Foot_heel`/`Toe_heels` on the same tier.
- **T3 continuous radial** (`Cloth`/`Hair` Float): each integer tier; **`1/4`, `1/2`, `3/4` between two tiers**; rapid back-and-forth; stability when the value stays the same while another part's toggle changes.
- **T4 plugin-grouped outfit switching** (ClothGroup / FastCloth / MapleCloset): single part within a group; crossing between groups; **two groups selected at once**; don't treat backup objects as delivery content.
- **T5 per-part ShapeChanger key pressing**: sole/ankle/toes per part; **two pairs of shoes on at once**; socks + shoes + skirt stacked; whether keys revert after turning one part off.
- **T6 no body fitting** (no `Shrink_*`, scene ShapeChanger=0): which shrink keys the body already has; several `Costume_*` worn together; foot shape when switching shoes.
- **T7 face-tracking + native roots coexisting**: confirm the **single active root**; **whether the two roots share materials/textures**; mouth/eyes when face-tracking keys and expression animations drive together; check `BlendShare` >30 MB separately.
- **T8 PC + Quest dual avatars** (both descriptors active): run the menu independently on both roots; **Android materials/shaders/texture slots**; whether animator layers/ShapeChanger are missing on Android; whether the local VRCQuestTools is actually invoked.
- **T9 AAO/NDMF optimized product**: after changes, run a full build in batch mode (including NDMF and this project's other preprocessing); whether animation paths still resolve after optimization; after parameter trimming, **whether it also takes effect in the baseline/Pico scenes**; clipping checks still work after `MergePhysBone` merging.

**Two cross-type items**: stills (merged bounding box with several outfits all on ≤5×6×6, bounds after particles are enabled, uniqueness of the active root); dynamics (walk/turn/jump, crouch/sit, raise arms/raise legs).

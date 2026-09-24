> 🌐 English translation · [中文原文](../../../../开发工具/SOP/_旧版/70_回归测试_旧版_20260918.md)

> ⚠ **Frozen legacy snapshot**; for the current method see [70 · Regression testing](../70-regression-testing.md); still-valid conclusions have been lifted into the current pages, see [README](README.md).

# 70 · Regression Testing 🤖

> ⚠ **On 2026-09-18 the author judged the testing incomplete.** In the existing projects (Project C, Project A, Project B_Milfy, and the delivered Project D) **the body blend shapes were not properly adapted to the outfits**; Project D's foot blend shapes need rework; the all-PASS results written in old regression reports were later all overturned.
> The practices and criteria on this page, and `通用工具/PlayTest.cs` and each project's `_70回归/` scripts, **may only be used as samples that are “informative, with both positive and negative examples”**; they must not be reused directly as verified methods.

> **The most important section of the whole procedure.**
> Numbers from the v1.1 retrospective: **15 functional defects were found by the client in-game; I proactively found only 5 in the editor.**
> What was missing was not capability, but one systematic walk-through.

**Output**: `回归报告.md` (pass/fail table per combination + screenshots)

---

## Deterministic steps

### Step 1 · Confirm environment and state baseline 🤖

**Preconditions**
- [ ] Environment confirmed usable per [02 · Environment setup and manual intervention](../02-environment-and-manual-intervention.md)
- [ ] 60 has passed (menus and animator layers generated)

**Execute**
1. Run the skeleton-height self-check and record the baseline values
2. Clear leftover baked clones from the scene

**Post-criteria**

| Expected | How to read |
|---|---|
| Only 1 avatar descriptor in the scene | Count `VRCAvatarDescriptor` by component |
| Skeleton self-check reports “normal” | The self-check tool's output line |

**STOP**
- Descriptors >1 and can't be cleared → hand back to a human

---

### Step 2 · List the combination matrix (compute only, don't touch the project) 🤖

**Preconditions**
- [ ] Step 1 passed

**Execute**
1. Read from the menu generator's slot table: outfit slots × hairstyle slots × each part/accessory toggle
2. Write it to disk as a table of combinations to test

**Post-criteria**

| Expected | How to read |
|---|---|
| Number of combinations == product of the slot counts of each dimension (or the pruned number per design, with the pruning rationale written in the table) | Row count of the combination table |

> This step is pure computation and **can be fanned out in parallel**. See [01 · Automated execution and parallelism](../01-automation-and-parallelism.md).

---

### Step 3 · Judge each combination 🤖

**Preconditions**
- [ ] The combination table from step 2 exists

**Execute**
1. For each cell: use **real animation data** to Apply the parameters to that slot (not manual `SetActive`)
2. Read back the relevant objects' `activeInHierarchy` and renderer enabled state
3. **Restore the snapshot** after judging

**Post-criteria**

| Expected | How to read |
|---|---|
| In every cell “what should be on is on, what should be off is off”, violations == 0 | The violation column of the combination report |
| “At least one item is on for each body location”, deadlock cells == 0 | Same (suppression layers suppressing each other can turn both sides off) |

**STOP**
- A deadlock cell appears → it's a suppression-layer design problem; go back to 60 to fix, don't work around it here

---

### Step 4 · Switch away and back 🤖

**Preconditions**
- [ ] Step 3 all passed

**Execute**
1. For each radial do A → B → A, and compare the state snapshots of the two A's

**Post-criteria**

| Expected | How to read |
|---|---|
| The two A states are identical item by item, differences == 0 | Snapshot diff |

---

### Step 5 · Check clipping in motion and expression extrapolation 🤖 →🔒

**Preconditions**
- [ ] Step 4 passed

**Execute**
1. Scan all `.anim` files for expression extrapolation overflow (list each with peak >100)
2. Enter Play and go through the animations (don't look only at the T-pose)

**Post-criteria**

| Expected | How to read |
|---|---|
| Extrapolation overflows == 0, or each has a “recomputed” record | Scan report |
| No clipping of cuffs/skirt hems in motion | Play footage, **a human looks** |

**STOP**
- PhysBone-related appearance (hair drape, skirt collision) is **not simulated at edit time**; it must be tested in Play

---

### Step 6 · Produce acceptance images and pass external review 🤖 →🎨

**Preconditions**
- [ ] Step 5 passed

**Execute**
1. **First Apply the parameters to the target slot**, then shoot (see “Acceptance images must show the delivered state” below)
2. At least three angles per object: eye level / top-down / oblique full view
3. Batch them and send to external review in one go

**Post-criteria**

| Expected | How to read |
|---|---|
| Issues independently identified by ≥2 models == 0 | Review results |
| Every issue flagged by a single model has a re-check conclusion | Re-check record |

**STOP**
- Platform-override changes (texture budget, compression format, mesh compression, shader stripping) **cannot be verified in the editor** →
  either verify on a real device, or explicitly mark in the report “this item not verified on a real device”

---

## ⚠ Acceptance images must show the **delivered state**, not the bare editor state

When animator layers aren't driven in the editor, every outfit's hats, cat ears, and accessories **are all on** —
that is **a state that will never be delivered**. Using it as an acceptance image evaluates something the user will never see.

**Practice**: first use real animation data to Apply the parameters to the slot to be verified, then shoot.
The basis for “what this slot should show” is the animator layer, not the current check state in the scene.

Likewise, **manual `SetActive` cannot prove what the animator layer will write** — the two are often inconsistent.

## Three observation rules (set the rules first, then look at results)

**① Don't draw conclusions right after entering Play.** The animator hasn't evaluated yet and NDMF hasn't finished generating.
> Measured: this caused three false reports of “this layer didn't take effect”, two of which were refuted by the client with their own screenshots.
> Practice: run a few frames before observing, or use Gesture Manager to switch parameters manually and watch the live result.

**② Validation scripts themselves must be validated.**
> Measured: wrote a cross-block non-greedy regex to re-check animation curves, and on that basis reported “the file wasn't fully cleaned”.
> It had actually been correct all along — the regex crossed into an adjacent curve block and caught unrelated values.

**③ Platform-override changes cannot be verified in the editor.**
Texture import settings like `maxTextureSize` have two layers, “default” and “platform override”; **editor rendering always uses the default**.
After changing Android/Quest platform overrides, no editor screenshot **can possibly** reveal a problem; you must build and test on a real device.
Performance changes (texture budget, compression format, mesh compression, shader stripping) **all belong to this class** —
“it looks fine in the editor after the change” constitutes no evidence at all. Either verify on a real device, or **explicitly mark in the report “this item not verified on a real device”**.

## Six mandatory items

| # | Item | Practice | Where it's easy to miss |
|---|---|---|---|
| 1 | Combination traversal | Every outfit × every hairstyle × every part toggle; turn each radial, click each toggle | The menu went through three versions, and each had escapes reported back by the client |
| 2 | Switch away and back | A → B → A, see whether anything fails to come back | Timing bugs are the easiest to miss by hand-clicking, yet occur the most |
| 3 | All expressions | Focus on the modified ones, **but also re-check those judged “safe”** | Expression extrapolation overflows after face sculpting is baked into the mesh |
| 4 | Check clipping in motion | Go through the animations; don't look only at the T-pose | Cuffs and skirt hems can't be caught statically; measured: over-knee socks poking out through the crotch of long trousers |
| 5 | Parameter audit (Play mode) | `ParamAudit.cs` | Parameters generated at build time aren't visible at edit time |
| 6 | Multi-angle screenshots | **At least three angles**: eye level (seams, ground contact) / top-down (direction, gaps) / oblique full view | Declaring done after shooting only one angle — tripped over this five times |

## Make layer logic automatically regressable

VRChat's FX layer is attached via PlayableGraph — `animator.SetFloat` can't reach it,
and `animator.playableGraph` returns an invalid graph under GestureManager (two dead ends, recorded in `PlayTest.cs`).

**The approach that works**: attach the generated controller **alone to a temporary object** and run it,
directly verifying “given a parameter combination, which state each layer stops in”.

## On first entering Play after taking over a project, check these three places in order

1. **FX layer parameter defaults overriding the scene settings** — **both** `ExParameters.asset` and the controller must be changed
2. **A resident high-priority MergeAnimator layer suppresses everything** — `layerPriority: 999` + unconditionally resident
   flattens every expression that uses the same-named keys
3. **Expression extrapolation beyond 0–100**

## For material problems, always probe runtime ground truth first

A real device reported “some part is a white model”; finding the material by reading prefab YAML was **wrong three times in a row**:
misjudged as over-compressed texture → misjudged as another similarly named material (actually the same name with a prefix) →
misjudged as the outline layer (actually the body was another renderer). The first “fix” changed the wrong renderer,
and the external visual review judged on the spot “nothing changed at all, send it back”.

**Correct practice**: write a probe script and let Unity itself report each Renderer's actual `sharedMaterials`,
shader name, whether textures are null, and `mesh.colors.Length`. Located it precisely in one go.

Two reusable criteria:
- **Prefabs often have multiple Renderers** (body + outline/glow layer); replacing by material name easily hits the decoration layer
- **Two typical causes of white models**: ① the material is URP/Lit but `_BaseMap` is empty and `_BaseColor` is the default 0.8 light grey;
  ② the FBX has `materialImportMode: 0` and no remapping, falling back to Unity's default material (slot name shows as `Lit` — a good criterion)

## Visual outputs must pass external review

Looking at images yourself easily mistakes a “fake fix” for a real fix. Use `agy_panel.py`, **only accept issues identified by ≥2 models**.
Quota is limited, **batch and ask everything in one go**.

## ⚠ Acceptance-render camera positions must cover “the side where problems show” (measured 2026-09-09)

**Passing acceptance may be merely an artifact of framing.**

Example: Project B's foot-shape acceptance matrix had 106 images (13 slots × 4 foot-shape keys × 2 viewpoints);
slot 4 “bunny slippers” looked completely normal in both viewpoints, and passed on that basis.
But the user saw the problem at a glance from **the side** — **those slippers are open-heeled, and the matrix's two camera positions
(`Euler(0, 35°, 0)` front three-quarter + top-down) never had the heel in frame**.
The two images were not “two viewpoints” but two angles of the same side.

**Criterion**: before rendering acceptance images, first ask — **from which side could this thing give itself away? Is that side in frame?**

- Open-heel / open-toe / open items → **must have a rear or true side view**; a front three-quarter view can't show the opening
- Ring-shaped items (rings, wrist accessories) → must have a view along the axis
- Fitted items (sock cuffs, glove cuffs) → must have a close-up around the seam

**Asymmetric cost**: rendering one more camera position costs only a few seconds; missing that side carries the defect all the way to delivery,
and **every intermediate “acceptance pass” reinforces the false confidence** — the later it's found, the more it costs.

Related: [05 Multi-model review procedure](../05-multi-model-review.md) (image feeding granularity),
[Troubleshooting / Observation measures](../troubleshooting/observation-criteria.md) (a wrong observation measure is worse than not comparing and not concluding).

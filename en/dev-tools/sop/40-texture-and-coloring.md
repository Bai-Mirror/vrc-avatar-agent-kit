> 🌐 English translation · [中文原文](../../../开发工具/SOP/40_贴图配色.md)

# 40 · Texture and coloring　🎨 Aesthetic gate (can be delegated to Gemini for acceptance)

**Purpose**: turn the color descriptions in the requirements questionnaire into re-runnable recipes and pickable candidates.
**Outputs**: `配方.py` (parameters concentrated at the top of the file), candidate comparison images, `配色决策.md`
**Gate rule**: Agent produces candidates → `agy_panel` cross-review → **passes if ≥2 models report no blocker**; only escalate to the user on disagreement.

## Why aesthetics can be delegated

The user stated clearly on 2026-09-01: **trust Gemini's aesthetics**; the coloring gate can be delegated depending on how complete the requirements are.
The precondition is that the requirements questionnaire spells out the direction (tone / contrast colors / per-part colors / style preferences).
**Face sculpting is not included; that is a hard gate** ([30](30-face-sculpt.md)).

## Deterministic steps

### Step 1 · Confirm the environment is usable　🤖

**Preconditions**
- [ ] The requirements questionnaire clearly states tone / contrast colors / per-part colors / style preferences (if any one is missing, ask back first; don't guess)
- [ ] [20](20-asset-inventory-and-import.md) has imported the texture packs

**Execution**
1. Confirm the environment is usable per [02](02-environment-and-manual-intervention.md) (only step 4 needs Unity; steps 2~3 are offline, do them first while waiting for the environment)

**Post-criteria**

| Expected | How to read |
|---|---|
| Steps 1~4 of 02 all pass | Post-criteria of each step in 02 |

**STOP**
- 02 concludes “need a human” → ask for help per section 3 of 02, and meanwhile do steps 2~3 first

---

### Step 2 · Measure the atlases, separate base images from overlay layers, check shared materials　🤖

**Preconditions**
- [ ] Every color requirement in the questionnaire maps to a source: change `_Color` / some image in the base avatar texture pack / recolor by mask

**Execution**
1. Measure the atlas first, then act: for each replacement texture compute the alpha opaque ratio, and judge whether it's a “whole-image repaint” or an override image that “paints only its own area, rest transparent”
2. Ratio comparable to the base avatar original → whole base image, swap `_MainTex`; noticeably lower → overlay layer, prefer compositing offline into the base image; if the vendor's manual specifies a slot, follow it
3. Iterate over renderers' `sharedMaterials` and list which meshes share each material

**Post-criteria**

| Expected | How to read |
|---|---|
| Every replacement texture has a “ratio + type” record | Atlas list |
| Number of meshes sharing a material to be changed = 1; otherwise override images hook only to the specific mesh's slot | The list from item 3 |
| The eye / hair colors named in the questionnaire each have a source | Requirement ↔ source mapping table |

**STOP**
- A color requirement has no source → report it; that's an entire ordered requirement left undone
- Want to change a shared material directly → stop; it will break unrelated parts

---

### Step 3 · Script the compositing and do a read-back self-check　🤖

**Preconditions**
- [ ] The atlas list from step 2 is saved to disk

**Execution**
1. Write `配方.py` with parameters as constants at the top of the file, so changing one number reruns it; offline compositing uses `eye_composite.py` (command in the subpage)
2. Anything with relative operations must be idempotent: a state file records processed items, `dry-run` for details first, then apply **only once**
3. Read-back self-check; commit `配方.py` (atlases are binary and don't go into git; lose the recipe and it can't be reproduced)

**Post-criteria**

| Expected | How to read |
|---|---|
| Rerunning `配方.py` leaves the output hash unchanged | Run twice, compare hashes |
| Heterochromia left/right sampled colors differ (mask uses the eye-color layer's own alpha) | Script read-back output |
| Gradient top/bottom segment luminance difference > 0 and direction matches the requirement | Script read-back output |
| `git ls-files` hits `配方.py` | git |

**STOP**
- Both halves same color / top and bottom not distinguished → direction or mask is wrong
- Second apply drifts → the script is not idempotent, fix it first

---

### Step 4 · Produce candidates and render from the same camera position　🎨

**Preconditions**
- [ ] Step 3 passed; recoloring follows the non-destructive route: copy the vendor material and change `_Color`, ledger records the original material GUID (see subpage)

**Execution**
1. Produce 3–5 tiers per dimension, rules listed item by item (no `"*"` wildcard), each computed from the original
2. Render every tier with `AvatarPortrait.cs` at the same camera position and lighting
3. Read-back verification + skeleton height self-check

**Post-criteria**

| Expected | How to read |
|---|---|
| Tier count ∈ [3, 5]; camera spec JSON identical across all candidate images | Compare the JSON output by `AvatarPortrait.cs` field by field |
| Ledger row count = number of replaced slots | Ledger file |
| Empty material slots = 0; difference in world y between Head/Foot bones unchanged | Iterate `sharedMaterials` and count nulls; bone world coordinates |

**STOP**
- Camera positions inconsistent → re-render; they can't be compared
- Rule table contains a wildcard like `("Outfit_XXX", "*", tint)` → split into per-item rules

---

### Step 5 · Cross-review　🤖

**Preconditions**
- [ ] Candidate images complete; `配色审查.md` written (key points below)

**Execution**
1. `agy_panel.py --images 候选图... --task 配色审查.md`, batch the candidates and ask everything in one go

**Post-criteria**

| Expected | How to read |
|---|---|
| Some tier has ≥2 models with no blocker → pass | Per-model conclusions in the output json |
| Every tier has a score, reasons, and which requirement item it deviates from | Output json |

**STOP**
- No tier gets ≥2 models with no blocker → escalate to the user for a decision
- Flagged by a single model → downgrade to pending verification, re-check yourself; neither discard it outright nor trust it outright

---

### Step 6 · Finalize, write the decision, rerun menu generation　🤖

**Preconditions**
- [ ] One tier passed in step 5, or the user has decided

**Execution**
1. Apply the chosen tier to the project (same non-destructive route as step 4)
2. Write `配色决策.md`: which tier was chosen, why, and what was rejected
3. **Rerun menu generation** (`菜单架构/MenuGen.cs`, [60](60-menu-and-animation-layers.md)) — the color layer's material curves are sampled from the scene's current materials; if not rerun, the old curves overwrite it back
4. Read-back verification + skeleton height self-check

**Post-criteria**

| Expected | How to read |
|---|---|
| `配色决策.md` exists and has all three items | File |
| The target renderers' materials are in our own directory, not vendor originals | Iterate renderers, read `sharedMaterials` asset paths |
| The generated animator layer's material curves point to the new materials | `m_PPtrCurves` of the generated `.anim` |
| Empty material slots = 0; skeleton height unchanged | Same as step 4 |

**STOP**
- Material curves still point to the old material → menu generation didn't rerun successfully
- On restore, the ledger points to a deleted asset → magenta, see the subpage's “Three hard rules”

### Licensing and portability (trigger: before choosing a recolor route / when the source is a vendor item)

- **Register source PSD/CLIP centrally** (F §8): when layered source files exist, prefer editing them (see subpage); register which pack and which image they came from; don't scatter them across projects.
- **Shader GUIDs must resolve**: a font/paid shader reference that can't be resolved means magenta; reverse-look-up by GUID before delivery ([20](20-asset-inventory-and-import.md)). Patreon shaders, private shaders brought in by templates, and paid textures: **check the source order by order; they don't go into deliveries** (K #3/#4, F §6).
- **lilToon migrates materials one-way across major versions; back up first** (F §2): migration is irreversible; back up the current material arrays / `.mat` before upgrading.
- **Precedent**: H2-Eku `Eye change/` is a workable example of **scripted recoloring** (B §40).
- **What if it can't be met**: textures whose source can't be established are not used for delivery, or the user decides; don't use “looks the same” as evidence of source.

---

## Producing candidates

Produce 3–5 tiers for a dimension and render them side by side (same camera position, same lighting — using `AvatarPortrait.cs`), rather than deciding on one yourself.
Measured: eyelashes got 5 tiers (RGB 216 → 126) and the middle tier was chosen; guessing directly is very likely to mean rework.

**Candidate images must share the same camera position.** A/B comparisons from different camera positions are not comparable.

## Key points for the cross-review prompt

Write into the `--task` file:
- State the original requirement text (tone / contrast colors / per-part colors / style preferences) so the models have criteria
- Have it **score each candidate and explain its reasons**, rather than vaguely saying which one is better
- Require it to point out “which tier deviates from which requirement item”
- State explicitly: no fabrication, no softening

Quota is limited (Pro subscription); **batch the candidates and ask everything in one go**, not one tier at a time.

## Subpage index

| Subpage | When to consult |
|---|---|
| [Base texture and recolor techniques](40-texture-and-coloring/base-texture-and-recolor-techniques.md) | Before acting in steps 2~4, 6: base avatar textures (base image vs overlay layer, heterochromia, recoloring by mask, lilToon color overlay layers and blend mode enum, vertical gradients), shared materials, render amplification layer, batch idempotency, non-destructive recoloring and ledger, PSD source files, per-item recoloring and contrast accents |

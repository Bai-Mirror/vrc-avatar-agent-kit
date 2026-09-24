> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/问题定位/观测口径/判据的形状.md)

# The shape of a criterion: how to tell "it's not the thing under test that's wrong, it's the criterion"

> ← [Troubleshooting · Observation criteria](../observation-criteria.md)

The problem this page solves: when a closed-form criterion produces a pile of failures, **how to first decide whether to fix the thing under test or the criterion**;
and which criterion shapes are doomed to fool you when writing them.

Prerequisite: [Observation criteria](../observation-criteria.md) covers four categories: "timing / method / script bug / channel can't render it";
this page adds a fifth — **the criterion's boundary is drawn wrong**.

---

## 1 · "Failing neatly on one side only" = the shape of a wrong criterion

### Trigger
**When a closed-form criterion runs and reports a batch of failures (before you've started fixing the thing under test).**

### Ask
**"Is the distribution of these failures scattered or neat?"**

- **Scattered** → most likely real defects
- **Neat** (a whole row fails along one dimension, or **the failure set exactly equals the scope of some known rule**)
  → **suspect the criterion first**, not the thing under test

### What to do if you got it wrong
Remove that rule's scope and see what remains. If 0 remain, the criterion didn't recognize that rule.

### Evidence (2026-09-08 Project B_Milfy)
The same combination sweep; the criterion was wrong two rounds in a row, and both rounds' failure distributions were neat:

| Round | Failing cells | Distribution | Truth |
|---|---:|---|---|
| 1 | 96 | Tier 0 all pass, **tiers 1–12 all fail** | The assertion treated "base avatar root-level parts" as required in every tier; retracting the base avatar's own outfit when switching to a purchased full set was by design |
| 2 | 8 | Only "outfit 0 × hair Fluffy/Woofy" | The assertion didn't recognize the priority chain "hairstyle's built-in animal ears suppress the base avatar's bear ears" |

After fixing, 2496 cells with 0 failures. **Both rounds the criterion was wrong; the thing under test was never wrong.**

### Root fix: trace the criterion's boundary back from **authoritative artifacts**; don't hand-type lists

The "should" in "X should appear at this point" must have its boundary read from the generated artifacts:

- "Which parts belong to the current tier" → read the paths written as true in the full-set/hairstyle clips
- "Which parts are explicitly turned off by a higher-priority layer" → read the paths written as false in those clips

This way the criterion automatically keeps up as rules change, and **doesn't gain a batch of false positives with every new rule**.

Methods for reading artifacts (YAML wrapping, scripts appearing only as guids, instance changes in `m_Modifications`, negative samples iterating the full set) → "Reading authoritative artifacts" in [Criteria for verdict scripts](verdict-script-criteria.md).

---

## 2 · Absolute-threshold criteria get consistently false-triggered by structural offsets

### Trigger
**When writing a criterion like "some quantity must be < some number".**

### Ask
**"Is part of this quantity structural, i.e. supposed to be that large?"**

### What to do if you got it wrong
Switch to **comparison against a reference sample** — compare item by item with a known-correct object of the same kind, and only report "differs from reference".

### Evidence (2026-09-08 Project B_Milfy, two cases)

| Criterion | Why it's broken | Fix |
|---|---|---|
| "Longest bone segment < 500 mm" to check skeleton adapter nodes | The local coordinate of `Hips` under the armature root is just the hip height of 760 mm — that's not a bone segment but the armature root offset, **falsely reported every time** | Use another variant as reference, compare local transforms path by path, report only differences (result: 389 compared, 0 different ✓) |
| "AABBs intersect" to decide whether two parts compete for the same position | The authored bounds of 46 renderers are **big boxes the size of the whole body** (`Hair_Head` reports y ∈ [−0.126, 1.466]), overlap rate uniformly 100% | Criterion discarded; switched to solo renders to confirm each part |

The second case was **rescued by a self-check**: the criterion included an item "number of bounding boxes with any side > 1 m",
which reported 46, immediately showing this batch of data was untrustworthy.

> **Rule**: every statistical criterion must carry a self-check item **that can refute itself**.
> Without a self-check item, there's no way to judge whether the criterion's numbers are trustworthy.

---

## 3 · Reference samples must be matched by **full path**, not by name

### Trigger
**When writing a comparison criterion of the form "compare A and B item by item".**

### Ask
**"Does this asset set contain two things with the same name?"**

Very common in VRChat outfits: `Jacket` / `Tops` is both a mesh name and a PhysBone node name
(`PB/Jacket`, `PB/Tops/Collar`). Taking "the first one" by name compares a PB node with a mesh.

### Evidence (2026-09-08 Project B_Milfy)
Compared by name: 23 differences reported. Compared by full path: **0** (plus 24 paths present on only one side, exactly the expected new bone chains).
The 17 extra differences that appeared out of nowhere were all same-name mismatches.

Related: [50 · The name is not the part itself](../../50-outfit-and-hair-assembly.md).

---

## 4 · False negatives of difference criteria: can't tell "by design" from "misassembled"

### Trigger
**When using a difference quantity like "pixel difference between A and B" as a fit criterion.**

### Ask
**"Is this item supposed to expose that by design?"**

Peep-toe shoes, sandals and open-toe socks expose the foot by design — a large difference residue **doesn't mean** misassembly.
Conversely, a wrong foot **angle** (flat foot stuffed into a high heel) may be only a medium value in the difference and get ranked behind "exposed by design".

### What to do if you got it wrong
**Numbers are only for initial screening; the final call is on the contact sheet.** Produce both:
- Numeric ranking → narrow the candidates
- A **close-up render** for each candidate → a human (or the review panel) judges the angle

> **One step worse**: difference criteria can be **systematically reversed** (rewarding "making the thing under test disappear") → canonical source is "The criterion's direction may be reversed" in [The criterion itself may be broken](criterion-may-be-broken.md) (this section's original `Foot_highheels` 12755 vs 9531 evidence has been merged there).

### Evidence (2026-09-08 Project B_Milfy)
For the sandal set, pixel difference chose `Foot`, residue 12691 px, and the previous round judged it "foot exposure is by design".
The user's screenshot from a Play test showed: **the foot was flat, the shoe was high-heeled, the angle completely wrong**.
The criterion wasn't wrong in its algorithm; it was wrong in that **it cannot express the dimension of "angle"**.

Related: [03 · Occlusion is not occupancy](../../03-assembly-and-conflict-rules.md).

---

## 5 · Reproducing the delivered state: two things you must always do

"Posing the avatar into its delivered state from a set of parameters" is the prerequisite for all the render criteria above.
Running only our own clips is not enough.

### ① Vendor layers must be **simulated as whole layers**

We often **only drive parameters**, while mesh visibility is written in the **vendor's own layers**
(one `LEM/Jacket` controls a dozen or so meshes + a choice between two skirts).
Adding only a hand-written "parameter → mesh" mapping will never be complete —
you have to **evaluate every MA MergeAnimator controller in the scene as a whole layer**
(pick states by transition conditions: AnyState first, otherwise walk a few steps from the default state along transitions whose conditions are met),
and add the Relative prefix to paths.

### ② Evaluating in the wrong order yields **a confidently wrong image**

```
① Run our layers first → compute the values the Driver writes to vendor parameters
② Then run the vendor layers with the final parameter values
③ Finally overlay the properties we write (MA appends our layers after theirs)
```

**How to tell**: if what's missing from the image is **governed by vendor parameters**, suspect evaluation order first, not wiring.

> Evidence (2026-09-08 Project B_Milfy): the first version put the vendor layers first;
> at that point `LEM/Jacket` was still sitting at the **controller default false**,
> and in the acceptance image for the "outfit head accessory" tier the whole jacket vanished out of nowhere, nearly investigated as a wiring defect.

### ③ Don't apply only `m_IsActive`

Foot shape and bust size are `blendShape.*`. Miss them and you can't measure "does the shoe fit the foot".

### Implementation
These three are baked into a shared evaluator (in this order it's `Assets/Editor/State70.cs`) —
**acceptance renders, shape measurement and combination sweeps must all share the same copy**; writing one each will inevitably drift.

---

## 6 · Criteria for verdict scripts (identifying the body, can't-decide, exemptions, labels, counting, reading authoritative artifacts)
See subpage [Criteria for verdict scripts](verdict-script-criteria.md).

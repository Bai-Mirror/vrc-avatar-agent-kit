> 🌐 English translation · [中文原文](../../../../开发工具/SOP/50_服装发型装配/脚型与收缩键归属.md)

# 50 · Ownership of foot-shape and shrink keys

> **Rewritten 2026-09-20 (D-03).** The previous version (written 09-08, judged by the author on 09-18 as “method not fully tested, to be rewritten”) chose keys by **pixel difference**,
> and lacked the most critical check — “after the garment is turned off, is the shrink key still on?”. On 2026-09-20 the author directly saw the consequence in the Project B 43% slot.
> This page is changed to **produce data first, then look at images at targeted spots**. The still-valid positive and negative examples from the old version have been merged into the subpage;
> the old method **must not be reused directly as a verified method** ([old-regression-methods-unproven]).

> ← [50 · Outfit and hair assembly](../50-outfit-and-hair-assembly.md)　Sister page: [60 · Property ownership and writing](../60-menu-and-animation-layers/property-ownership-and-authoring.md),
> subpages: [Two key types, criterion bias and the writer list](foot-and-shrink-key-ownership/two-key-types-and-writers.md), [Shrink key visible consequences: render comparison](shrink-key-effects-render-comparison.md)

**In one sentence**: **a shrink key belongs to “the item that actually covers that segment”; a fitting-pose key belongs to “the shoe”** (the shoe determines the foot's angle).
These are **two types** of things: classify first, then decide ownership, and only then choose values — getting the type wrong costs far more than getting a value wrong;
definitions of the two types and counterexamples are in the [subpage](foot-and-shrink-key-ownership/two-key-types-and-writers.md).

## Step 1: list this set's “coverage table” (who covers which segment)

Split the foot into three segments: **ankle / instep and sole / toes**, and fill in “covers or not” item by item. **Look at the shoe's upper height, not the item name**.

> Measured (Project B 43% LopEarMine, 2026-09-20): the white-pink platform sneakers are **low-top** — covering the instep, sole and toes, **not the ankle**;
> the slouch socks cover the lower calf + ankle; the lace ankle socks cover the instep and toes.
> Platform ≠ high-top; **sole thickness has nothing to do with upper height**; this set was treated as covering the ankle precisely because it “looks thick”.

## Step 2: split shrink keys onto items by coverage

| Key | Which segment | Attached to |
|---|---|---|
| `Ankle` (`Ankle_L/R`) | Ankle | The item covering the ankle: mid-calf socks / slouch socks / long boots |
| `Foot` (`Foot_L/R`) | Instep and sole | Shoes **and** foot-covering socks (attached to both, same value) |
| `Toe` (`Toe_L/R`) | Toes | Same as above; open-toe styles **don't** get it |

**Taboo: attaching everything to the shoes.** The consequence is one-directional — once the item covering it is turned off, the body is still shrunk,
and **the person who just turned off that garment is looking right at that spot**.

> Measured (Project B 43%, 2026-09-20): `Ankle/Foot/Toe/Foot_heels` were all on one ShapeChanger on the shoe item.
> Socks off (shoes still on) → the lower calf to the ankle **collapsed into a sharp cone** plunging into the shoe opening, with large empty space in the shoe cavity.
> After moving `Ankle` to the slouch socks, all four combinations read back correctly and the cone disappeared (agy blind check: blocker before the fix, deliverable after).
> Project D Velvet China (09-19) is another form of the same pitfall: the shrink SC was attached to the **face tracking root**, and turning off the socks collapsed the calf.

**The same key attached to several items doesn't conflict**: MA multiple writers apply in hierarchy pre-order with later ones overriding; if the values are the same it doesn't matter;
but **the same object must not both Set and Delete the same key**.

## Step 3: fitting-pose keys follow the **shoes**

`Foot_heels` / `Foot_highheels` are “what angle the foot is posed at”, determined by **heel height**: **flat shoes get no pose key**;
heeled shoes pick one tier by heel height (determined by R9 measurement in step 5, not by gut feeling).

**Taboo: two pose keys both at 100 in the same state.** That's “tiptoe” stacked on “raised heel”, and the leg becomes a sharp spike.

> Measured (Project B 43%): the shoe item's SC writes `Foot_heels=100`, and the FX foot-shape layer **at the same time** writes `Foot_highheels=100`,
> while these are flat platform sneakers — that's the “leg turned into a spike” in the user's screenshot.

⚠ **A key often has two writers** (MA ShapeChanger on the outfit + the foot-shape layer in the FX).
Check both tables completely before acting; how to check is in the [subpage](foot-and-shrink-key-ownership/two-key-types-and-writers.md).

## Step 4: four combinations × **paired** criteria

| Combination | Shoes | Socks | Shrink keys that should be on | Pose key |
|---|---|---|---|---|
| All on | On | On | Union of both items' coverage | The shoe's tier |
| Shoes only | On | Off | **Only the segments covered by the shoes** | The shoe's tier |
| Socks only | Off | On | Only the segments covered by the socks | Written only if the socks are modeled in a tiptoe pose; otherwise not |
| **Bare foot** | Off | Off | **All 0** | **All 0** |

**The criteria must be paired** (a one-sided criterion will always be fooled into full marks by “deleting stuff”, see
[The criterion's direction may be backwards](../troubleshooting/observation-criteria/criterion-may-be-broken.md)):

1. **No poke-through**: poke patch area = 0;
2. **No pointless shrinking**: T-33 `shrink_cover` all `ok` (no “key on but no visible garment covering that segment”).

The “bare foot” cell is the **control group**: it must pass both with all keys at 0; if it fails, the criterion is broken.
⚠ When measuring, turn off underlayer body stockings/pantyhose — they cover the foot, and you can't measure whether the shoes fit.

## Step 5: how to produce the numbers (tools and measurement)

| To answer | Tool | Measurement notes |
|---|---|---|
| Does the body poke through the garment | poke (T-28a, merged into T-10) | See [65 Perception mechanism](../65-perception-mechanism.md) |
| Which pose key should this shoe use | R9 candidate ranking (T-08a) | **Must provide the `candidates_zero` zeroing domain**, otherwise all candidates measure the same pose = nothing tested |
| Is the key still on after the garment is off | T-33 `shrink_cover` | Threshold pending calibration (B-T33b); for now judge yourself from `uncovered_ratio` and `nearest_cover_path` |
| “After turning off X, is Y still left over” | State request `"reset":"none"` | The default `declared` resets at every step, which washes out leftovers; see [70 Common pitfalls](../70-regression-testing/common-pitfalls.md) |

After producing the numbers, **look at images at targeted spots**: render only the questionable cell, 4 directions, foot close-up (`LeftFoot` radius around 0.22 shows ankle to shoe opening clearly),
and send the conclusion to agy for a **blind check** (images only, no conclusion given).

## Knock-on: socks must also suppress toenails

The `shoes > toenails` suppression gate can't just say “wearing shoes” — **socks that cover the feet also cover the toes**, so the gate must be written as `shoes on OR socks on`;
**open-toe styles are the exception** (the user's habit: toenails follow shoe/sock occlusion, except open-toe sandals).
⚠ Multiple conditions in one transition are **AND**; you can't write **OR** → Suppress needs **two** transitions, while Empty needs only one.
Implementation in [60 · Property ownership and writing](../60-menu-and-animation-layers/property-ownership-and-authoring.md);
how to open a separate exception for open-toe slots is in Project C's stage-60 fix script (not public).

## Old conclusions

The old conclusions have been overturned (choosing keys by pixel difference, attaching everything to shoes); the still-valid positive/negative examples and the containment test have been merged into [subpage · Shrink key host](foot-and-shrink-key-ownership/two-key-types-and-writers.md); comparing by bone name is on the [50 main page](../50-outfit-and-hair-assembly.md).

> 🌐 English translation · [中文原文](<../../../../开发工具/SOP/60_菜单与动画层/层序与压制.md>)

# 60 · Layer order and override

> ← [60 · Menu and animator layers](../60-menu-and-animation-layers.md)

The problem this page solves: when taking route B (hand-written AnimatorController layers), how to order layers, how to override clipping that appears as soon as an accessory is turned on,
why the override range goes wrong after a radial gains more steps, and which layer requirements like “restore to X when the clothing is off” and “the outfit ships its own underwear” belong in.

> ⚠ **Precondition check (verified 2026-09-22 H-07): this page's “empty clip = pass-through from earlier layers” only holds when WD is really OFF after build.**
> Checkable question: does the avatar root have VRCFury `FixWriteDefaults` (`grep -n "class: FixWriteDefaults" <场景>`, `mode: 0` = Auto)?
> When FX has >10 ordinary states, Auto decides by a majority vote of on/off; **vendor FX, PCS, Realkiss and the like are mostly WD on, so the vote almost certainly comes out ON**, and then it changes all FX states (including our hand-written WD=OFF layers) to ON without adding empty states (`FixWriteDefaultsService.cs:159-223`; Project A 09-18 log “FX:595 on|99 off → ON”).
> Under WD on, by Unity semantics, a property written by any state in a layer but not written by the current state **may** be written back to its default and override earlier layers; but on 09-22 Project A, in a real build (VRCFury judged ON, after AAO optimization), 4 cases tested in Play (step 0 jacket off/mouth on/underwear off, step 3 cat-ear override) **none reproduced a failure** — AAO merges/rewrites layers, so the actual semantics must be measured; **you can neither assert by reasoning that it's broken, nor assert by reasoning that it's fine**.
> **Trade-off**: don't bet on the WD value — **let only one layer write a given property, and have every state of that layer explicitly write all the properties it owns**; express multiple conditions with multiple states + transition conditions in the same layer; that way WD on/off give the same result. Static equivalence simulation must be run once each under WD on and WD off semantics.

## Layer order is part of the design (when taking B)

```
part toggles  →  whole-outfit switch  →  hair  →  accessory conflict override  →  derived states
```
- When the base avatar default is selected: the whole-outfit layer doesn't write base avatar meshes → **part toggle values pass through** ✓
- When an external outfit is selected: the whole-outfit layer writes base avatar meshes = false → **overrides part toggles** ✓
- The external outfit's own meshes are gated by the root object; part toggles take effect freely ✓

## Accessory conflict override layer (turning on an accessory must turn off clothing sub-content that would clip, as needed)

Headwear on means tuck away the hat, wrist cuff on means tuck away long cuffs, ring on means tuck away gloves — these conflicts **must be handled**,
otherwise turning on an accessory clips immediately.

**Keep the semantics straight; this is not the same as “turn off B along the way when switching”:**

| | “Turn off B along the way when switching A” | **“Override B while the accessory is on”** |
|---|---|---|
| Semantics | Turned off once; the user can turn it back on afterward | Overridden as long as the accessory is on; restores automatically when the accessory turns off |
| Method | `VRCAvatarParameterDriver` changes B's parameter | **A separate layer writes B's mesh property** |
| Consequence of doing it wrong | Writing B's property in the clip → B can never be turned on | Using a Driver → once the user turns it back on manually, it clips again |

**Correct way to write the override layer** (the key: the state for “accessory off” must write nothing):

```
Layer: Acc_头饰_Suppress   (placed after the part-toggle layer and the whole-outfit layer)
  ├─ Empty      default state, clip has no curves at all   ← under WD=OFF, unwritten properties pass through unchanged from earlier layers
  └─ Suppress   condition A2_Headdress == true, clip writes kaguya_cloth/beret.m_IsActive = 0
```

**Criterion**: after turning off the accessory, that clothing sub-content comes back by itself = correct; doesn't come back = you've hard-written it in another layer.

**The conflict table must be filled from screenshots, not guesses.** First list suspect pairs by “same body part” (head: halo/headwear × hat/hair;
wrist: wrist cuff × long sleeves; fingers: ring × gloves; back: wings/pendants × jacket),
then screenshot each combination to confirm which really clip, write the confirmed ones into the conflict table, regenerate, and re-verify.

### ⚠ A conflict pair may only be overridden in **one direction**; overriding twice wipes both out

Writing the same conflict pair as two override layers in opposite directions is a very sneaky kind of bug:

```
Rule 1: accessory X selected → turn off clothing piece Y
Rule 2: clothing piece Y on → turn off accessory X
```

Each looks right on its own, but **when both hold they wipe each other out** — the user sees “nothing in this spot”,
not “one of them isn't showing”. Since no single rule is wrong, checking rules one by one won't find it.

**Rules**:
- First define a **global priority chain** (e.g. headwear > small outfit head pieces > ears); all conflicts are overridden along the chain,
  **only overriding the lower-priority side**.
- If the conflict table has both “A overrides B” and “B overrides A”, it's wrong, regardless of whether they were added in the same batch.
- Every entry in the table must be able to state **its position on the priority chain**; an entry that can't is redundant.

**Acceptance must iterate over “combinations”, not “single items”.**
The criterion can be written in closed form: run the full combination of `服装档位 × 冲突开关`,
and for each cell assert “at least one piece is on at this body position”;
it passes only with zero deadlocked cells. This assertion must be driven by **real animation data** (`Apply` the parameters and run the animator layers once);
toggling objects by hand proves nothing about what the animator layers will write.

⚠ When judging “deadlock”, watch for **intentional all-off steps**: e.g. a hood step requires “no headphones, no ears”, so both sides being empty is **by design**, not a bug; the criterion must count the hood itself toward that step, otherwise it false-alarms.

## When override layers need a “range” rather than a “threshold”

After a radial is extended from 2 steps to 4, the original `param > 1/2` overrides **all later steps** too.
Example from this project: after ears/tail were extended to four steps, the rule “override the outfit's built-in cat ears” went from overriding only step 2 (new ears/tail)
to also overriding step 3 (off) — when the user turned off ears/tail, the outfit's built-in cat ears became unusable instead.

Note for range overrides: **multiple conditions within one transition are ANDed; you can't write OR**,
so “leaving the range” needs **two** transitions (one for below the lower bound, one for above the upper bound).

## Layers gated “by occlusion state” rather than “by which outfit is selected”

One class of requirement is gated not by a radial but by **whether some body part is covered**:
bust size, nipple visibility, foot shape under socks… The client's words are often
“restore to X when the clothing is off”, in which case it shouldn't be hooked to the whole-outfit radial.

How to write it (WD=OFF; an upper layer's write covers lower layers): **one layer, two states**

```
“Bust” layer
  ├ Bare    : empty/write default + nipple on
  └ Clothed : write limit value + nipple off
  Gate = **OR** of the three part toggles A2_Coat / A2_Top / A2_Und
```

- Entering “clothed” needs **three transitions**, one condition each — conditions within one transition are **AND**ed; you can't write OR
- Returning to “bare” needs only one transition with three conditions
- When it must be broken down by outfit, the “clothed” state uses motion-time (`timeParameterActive`) to read the whole-outfit radial;
  otherwise use an ordinary clip. `timeParameterActive` is set **per state**, so both kinds of state can coexist in one layer

### Size requirements: first clarify “default value” or “maximum value”

One order went in a circle: first a whole **per-outfit fallback** mechanism was built for “set the base avatar's breasts to maximum by default”
(measuring which step each outfit supports, generating 34 clothing-side curves),
and once the actual requirement was clarified — **the baseline (all 0) is enough, no extra enlargement** — all 0 is the default body shape the vendor modeled,
every outfit was made to it and fits naturally, so the fallback mechanism wasn't needed at all.

**Measure the criterion before asking**: the base avatar ships at `Breast_small=100` (9.9% smaller than the baseline),
so “set to 0” is **already an enlargement** relative to the original state. Put that number in front of the client and one sentence settles it,
instead of building a mechanism first and tearing it down.

### Clothing-side keys must be held down too

Vendor outfit-switch animations often write things like `Breast_small` to 100 (MMN's Jersey/Maid ship that way);
override only the base avatar and not the clothing, and it shrinks back when switching outfits. Write both sides in the layer.

## “This outfit ships its own underwear” also belongs in the whole-outfit layer

Some third-party full outfits ship their own bra/panties (measured: the Kitty set); wearing it must turn off **the base avatar's own underwear**,
otherwise the base avatar's pair pokes out as a ring at the hip sides.

The fix is not adding a new toggle, but adding a curve in the **whole-outfit layer** for these pieces that “turns off only at certain steps”:
on at every step by default (it should be there anyway), and only the named step writes 0. That way:

- It uses no parameter bits;
- It doesn't fight the “underwear” part toggle (the part toggle sits above the whole-outfit layer, so the user can still turn everything off).

The same applies to: full outfits with their own socks vs the base avatar's stockings, full outfits with their own shoes vs the base avatar's loafers — whenever
**two layers exist at the same body part**, name and turn off the base avatar's copy in the whole-outfit layer. The criterion is checking each outfit's render for
“two layers of fabric interpenetrating”.

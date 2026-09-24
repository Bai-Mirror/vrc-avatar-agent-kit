> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/50_服装发型装配/脚型与收缩键归属/两类键与写者.md)

# 50 · The two types of foot-shape keys, criterion bias, and the writer list

> A subpage split out of [`foot-and-shrink-key-ownership.md`](../foot-and-shrink-key-ownership.md) (2026-09-20, parent page over 10 KB).
> Takes over the “⚠ First tell the two key types apart” section.

## ⚠ First tell the two key types apart: **fitting pose** vs **shrink-to-hide** (the user made this explicit 2026-09-09)

A base avatar's foot blend shapes are **not one kind of thing**; picking the wrong type is far worse than picking the wrong value:

| Type | Typical key names | What it does | When to use |
|---|---|---|---|
| **Fitting pose** | `Foot_heels` / `Foot_highheels` | Changes the foot's **angle** (pointed instep, tiptoe) so the foot sits into the shoe cavity in the right pose | **The vast majority of shoes use this** |
| **Shrink-to-hide** | `Foot` / `Toe` / `Shrink_*` | **Pulls in / hides** the foot's vertices | A few cases: the foot visibly pokes out, and the shoe is fully enclosed |

**The default action is “pick a fitting-pose key by heel height”, not “should I shrink the foot away”.**

### Why this is easy to get backwards

The symptom “foot poking through the shoe” can **seem** to be relieved by both key types:
the shrink key makes the foot too small to poke out, the fitting key poses the foot into the shape of the shoe cavity.
But the shrink key **destroys geometry** to buy occlusion:

- On **open-heel / open-toe / open shoes**, the distortion from shrinking **can't be hidden** and is shown directly
- Over-shrinking folds vertices into one spot and renders as **a sharp cone + long thin trailing strands** (measured: `Foot=100` and `Toe=100`)
- And the shrink key and the shoe are two independent pieces of geometry; the shoe doesn't change along with it — shrink too much and the foot shrinks into the shoe and “disappears”

**Self-check**: if you are choosing “how much to shrink” for a pair of shoes, step back and ask —
**how high is this shoe's heel? Have the corresponding `Foot_heels` / `Foot_highheels` tiers been tried?**
If not, try those first.

### A real counterexample (Project B, 2026-09-09)

The `Foot` layer had 4 states `none / Foot / Foot_highheels / Foot+Toe`,
and across 13 slots **`Foot_heels` was never used once** (even though the render matrix clearly rendered a `*_Foot_heels_*` candidate for every slot).
Result:
- Slot 4 flat **open-heel** slippers → chose `Foot` (shrink) — the distortion is directly exposed at the open heel
- Slot 6 heeled boots → chose `Foot+Toe` (double shrink) — sharp cone with trailing strands, and this combination **had no corresponding render anywhere in the 106-image matrix**; it was never verified

**The root cause wasn't a mistuned value; the whole layer was doing the job with the wrong key type.**
Slots were picked with “pixel-difference improvement” as the criterion — that criterion **systematically favors shrinking** (the more you shrink, the fewer pixels poke out),
so it pushes you all the way toward the wrong key type. **The criterion itself being biased was the most expensive lesson this time.**

## Before acting, list everyone who writes this key (2026-09-20 Project B)

A foot key may have **two writers at the same time**; looking at only one leads to fixing the wrong place:

| Writer | What it looks like | When it takes effect |
|---|---|---|
| MA ShapeChanger on an outfit item | Attached to **outfit objects** like `…/Shoes`, `…/Socks` | When that object is active |
| Foot-shape layer in the FX | E.g. a layer in the menu controller dedicated to foot shape, AnyState condition = (full-set slot × shoe switch × sock switch) | When the condition matches |

Measured (Project B 43% LopEarMine): the shoe item's SC writes `Ankle/Foot/Toe/Foot_heels=100`,
while the FX foot-shape layer also writes `Foot_highheels=100` — **two fitting-pose keys stacked** (equivalent to standing on tiptoe),
and these are **flat** platform sneakers. Checking only the SC, or only the animator layers, you'd think “there's only one writer”, and it would still be wrong after the fix.

How to check (in the editor, no need to enter Play; run both together):

1. All `ModularAvatarShapeChanger` in the scene → read the `ShapeName` list via `EditorJsonUtility.ToJson` → outfit writers;
2. All `AnimationClip` in the project → filter `blendShape.<键名>` via `AnimationUtility.GetCurveBindings` → animation writers,
   then trace back which layer/state of which controller uses that clip and under what condition.

Only the two tables combined give the key's **complete writer set**. It's the same rule as [Trace the existing mechanism before changing it](../../03-assembly-and-conflict-rules.md):
first ask “who drives it, how many tiers”, then act.

## The host of a shrink key must be “the item that covers it”

The consequence of attaching to the wrong item is **one-directional**: once the item covering it is turned off, the body is still shrunk — collapsed ankle, collapsed calf,
and **the person who just turned off that garment is looking right at that spot**.

Rule: split shrink keys by **coverage** onto the items that cover each segment — socks cover the ankle → `Ankle` goes on the socks;
shoes cover the sole and toes → `Foot`/`Toe` go on the shoes. Don't put everything on the shoes to save effort.

Measured cases:

- Project D Velvet China (09-19): the shrink SC was attached to the face tracking root; turning off the socks collapsed the calf; fixed after splitting onto the covering items.
- Project B 43% (09-20): `Ankle/Foot/Toe` were all attached to the **shoes**, which are low-top sneakers that don't cover the ankle;
  turning off the socks collapsed the ankle — the user saw it directly, while my checks kept reporting “no problem”.
- Vendor positive example: LUNALICE attaches the pose keys and the ankle and sole shrink keys to each sock-type part, and the shoe items only write pose keys — split correctly.
- Our negative example (old version before 09-08): VioletNocturne / WinterCozyKnit had added keys attached to the shoe/boot items, and after the user turned off the shoes the feet poked out of the socks. At the time it was attributed to “the socks had no blend shape sync configured” — **right direction, wrong mechanism**: those two socks had no foot-shape keys at all, and with no keys there's nothing to sync (first check whether the item has the keys).
- **Containment test** (whether a point is inside the closed shoe body) is useful for the “shoes on, socks off” cell: Project A MMN's vendor attached only to the socks, 2% of toes were inside the shoe; after also attaching to the shoes, 100%.

**Self-check question**: are the vertices affected by this key **still covered by any visible garment** in the current state?
There is a probe: T-33 `shrink_cover` (key weight >0 but the affected vertices aren't covered by any visible garment → reports `uncovered`). ⚠ **Not calibrated (B-T33b not passed)**: do not take its `ok` as “pass”, and do not use it to scan other projects and draw conclusions; use it only as a lead; known limitation — coverage judgment for the upper torso `Chest_2`/`Spine_2` is unreliable (R4, raw data in `审查产出/工程B/seq_t33_calib2/`; don't use the negative-sample table in CX_report). Once calibrated, write the thresholds back to this page and delete this prohibition.

## Choosing blend shapes by pixel difference: false negatives exist; values are only a first screen

Sandals / peep-toe shoes / open-toe socks expose the foot by design, so **a large residue doesn't mean it's fitted wrong**;
conversely, a “wrong angle” (flat foot stuffed into a high heel) may only produce a medium value in the difference and be ranked behind “exposed by design”.

**Produce both**: numeric ranking narrows the candidates → a **close-up render** of each candidate judges the angle.
Expanded in [The shape of a criterion · false negatives of difference criteria](../../troubleshooting/observation-criteria/shape-of-a-criterion.md).

### Why the bias is **systematic**, not occasional

The base avatar's foot-shape keys come in two types, and the criterion treats them asymmetrically:

| Type | Examples | Effect on the difference criterion |
|---|---|---|
| **Shrink keys** (fold the foot in to hide it) | `Foot` · `Toe` · `Foot_L/R` · `Toe_L/R` | Once the foot shrinks it can't poke out → **always the lowest score** |
| **Pose keys** (raise heel / tiptoe) | `Foot_heels` · `Foot_highheels` | The foot **moves** relative to the shoe, changing more pixels → **the score is actually worse** |

So the criterion reliably ranks “shrink the foot away” ahead of “make the foot fit”.
**In enclosed shoes (long boots, closed-toe shoes), shrinking the foot is standard practice and the criterion is right**;
**on open-toe shoes, strappy shoes and short socks the criterion is backwards**.

> Evidence (2026-09-08 Project B_Milfy · Petal Drape high-heel sandals):
> the correct answer `Foot_highheels` scored **12755** (worse than “write nothing” at 9531),
> while the criterion's pick `Foot+Toe` (2468) rendered as “**shoes with no feet**”.
> In the per-candidate images only `Foot_highheels` was right: heel raised, foot seated in the shoe, toes showing through the peep-toe opening.

> The whole “socks only” column is the same: when socks only reach the ankle the correct answer is always “write nothing” (the foot is exposed anyway),
> but the criterion always picks shrink keys, rendering “a cone sticking out below the sock opening” or two broken foot segments.
> Of 13 sets, only one (LUNALICE) had pantyhose that truly enclose the foot and are modeled in a tiptoe pose, needing a pose key.

### Acceptance images must include the “everything at that position off” cell

Three rows × each set: **shoes on socks on / shoes off socks on / shoes and socks both off**. The third row must be a **neutral bare foot**.

> Evidence: only the third row exposed that “the animal-paw shoe covers were classified under **leg accessories**” —
> with shoes and socks off, the paws were still on the feet. Normally they're lit along with other switches, so **the misclassification can't be seen**.
> This kind of classification error can only be caught by the “all off” cell.

### Measure each of three scenarios; the “bare foot” group is the criterion's control group

| Scenario | Shoes | Socks | Purpose |
|---|---|---|---|
| Wearing shoes | On | On | Determine the “shoe form” |
| Socks only | Off | On | Determine the “sock form” |
| **Bare foot** | Off | Off | **Control group**: must pick “write nothing”; if it doesn't, the criterion is broken |

⚠ When measuring, turn off **underlayer body stockings/pantyhose** — they cover the foot, and you can't measure whether the shoes fit.

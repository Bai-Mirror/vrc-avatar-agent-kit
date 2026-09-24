> 🌐 English translation · [中文原文](<../../../../开发工具/SOP/60_菜单与动画层/属性归属与写法.md>)

# 60 · Property ownership and authoring

> ← [60 · Menu and animator layers](../60-menu-and-animation-layers.md)　Sister page: [Layer order and override](layer-order-and-override.md)

The problem this page solves: how things break when **the same property (or vendor parameter) is managed from two places**,
which authoring style a layer should use to write it, and the three kinds of things whose ownership is most easily missed: “root objects”, “containers”, and “derived shapes”.

[Layer order and override](layer-order-and-override.md) covers “how layers are ordered, which side a conflict overrides”;
this page covers **what exactly to write, and not write, in the chosen layer**.

---

## Iron rule: a property may only be managed by one layer

When moving something from layer A to layer B, **you must also delete it from layer A's table at the same time**.
Adding without deleting has two kinds of consequences, with completely different symptoms:

| What's written in two places | Winning rule | Symptom |
|---|---|---|
| **Animation curves** (`m_IsActive` / `blendShape.*`) | **By layer order**; later layers cover earlier ones | Stably reproducible: that toggle “does nothing no matter how you click” |
| **Parameters** (`VRCAvatarParameterDriver` Set) | **By event order**; whoever enters a state last wins | Intermittent: “after switching around and back, the thing I just turned off came back by itself” |

The second is the most valuable item on this page and gets its own section.

### A Driver “writes once on entering the state”, not every frame

#### Trigger
**Before writing “on entering some step, set some vendor parameter to a constant along the way”.**

#### Question
**“Is any other layer writing this parameter?”**

If so, you can't write a constant. A Driver writes only **on the frame it enters the state**, so when two layers each Set the same parameter,
**layer order has no effect whatsoever** — the exact opposite of the rule for animation curves, and very easy to mix up.

#### What to do if you get it wrong
To express “in this step, this parameter equals another toggle's value”, use **`ChangeType.Copy` + `convertRange`**, not Set:

```csharp
new VRC_AvatarParameterDriver.Parameter {
    type = VRC_AvatarParameterDriver.ChangeType.Copy,
    name = "Crown_OFF", source = "RJ_S_Hed",
    convertRange = true, sourceMin=0, sourceMax=1, destMin=1, destMax=0,  // invert
}
```
Copy recomputes on every state entry, so whichever step you switch back from, the value equals the toggle's current value.

#### Criterion
**Edit time can't prove it, and combination renders can't show it either** (renders simulate clips, not event order).
The only thing you can check: **read the controller and count “how many layers write this parameter”**. >1 means change it to Copy or consolidate into one place.

#### Evidence (2026-09-08 Project B_Milfy)
Step 0 of the whole-outfit layer unconditionally wrote `Crown_OFF/Cardigan_OFF/Bottoms_OFF/Slippers_OFF = false`,
while these four parameters were simultaneously driven by four part-toggle layers →
“headwear off → switch to any outfit → switch back to step 0 → the crown comes back by itself”.

---

## Four authoring styles, chosen by “is this step its owner”

Under WD=OFF, “this layer didn't write it” = **pass through unchanged from earlier layers**, so “not writing” is also a form of expression.

| Style | Own step/ON | Other steps/OFF | When to use |
|---|---|---|---|
| **Owner** | Write true | Write false | Default. This layer is the property's owner |
| **Override** | — (Empty, no curves) | Write false | “Hold down someone else's thing while some toggle is on”, see [Layer order and override](layer-order-and-override.md) |
| **Suppress-only SupMine** | **Don't write** | Write false | “It belongs to this step, but **its visibility has another owner**” |
| **Release-only SupBlock** | Write false | **Don't write** | “It doesn't belong to this step, but belongs to **every other step**” |

### When the last two are unavoidable

**SupMine** — this step wants it to appear, but whether it appears also depends on **another toggle**.
Hard-writing true produces “floating parts with no body”.

> Evidence (2026-09-08 Project B_Milfy): the lop-eared bunny's floppy ears grow on the jacket hood,
> managed by the vendor's `LEM/Jacket` and the “top” toggle. The head radial hard-wrote
> `Jacket_Ear = true` in the “outfit head accessory” step, producing **a pair of floating floppy ears still hanging after the top is turned off**.
> Changed to: this step doesn't write it, other steps write false: the radial can only suppress, not release.

**SupBlock** — the vendor uses one parameter to **choose one of two** pieces, and you only want to yield in a certain step.

> Evidence: LEM's `Skirt` ↔ `Skirt_Jacket` are chosen one-of-two by the vendor's `LEM/Jacket`.
> Our “skirt·pants” ON state wrote both true → **wearing two skirts at once**.
> Changed to: ON doesn't write (let the vendor pick), only OFF writes false (put both away together).

> → [The cost of SupMine / SupBlock and the ownership audit](property-ownership-and-authoring/override-authoring-cost-and-audit.md) — after scattering “who is the owner” across two places, an ownership audit is mandatory, including the two pitfalls of Relative path prefix and WD=ON.

---

## The four kinds of ownership most easily missed

### 1 · Root objects (containers) need an owner too

#### Trigger
**When writing the table of “which objects a body part/step manages”, for every path.**

#### Question
**“Who manages its parent object?”** If you can't answer, it has no owner.

#### What to do if you get it wrong
Write the root object into the table as well, and keep writing the child meshes too — only when both levels are determined does it not depend on the scene's historical state.

#### Criterion
**Closed-form criteria collectively can't catch this class**: they only look at the written path itself, not its ancestors.
A child written true with an ancestor off still has `activeInHierarchy` false.
The only thing that can automatically catch it is the generator's **ancestor self-check**:

> For every path the default state writes true, walk up through its ancestors;
> if an ancestor is off **and not managed by any layer**, throw and don't generate.

#### Evidence (2026-09-08 Project B_Milfy)
The gyaru ears/tail were wired into step 1 of the head radial; generation readback all passed, 2496-cell combination traversal all passed, the ownership audit all passed —
**yet it just didn't show in renders**. `_Acc/WhitePink` (parent of the two meshes) was off at the time, and no layer wrote it.

### 2 · Container gating: switching two variant instances within one outfit

Conversely, **containers are a good thing**. When switching two instances within one outfit (e.g. hood up/down):

```
_Outfit/<container>         ← the whole-outfit radial manages this level
  ├ <instance A>            ← part layers / accessory radials manage children inside the container
  └ <instance B>
```

When the container is off, the children's state doesn't matter, so later layers can **write children freely**
without releasing this outfit under other whole-outfit steps.
Without a container, a rule like “show instance B when not in step X” takes effect under every whole-outfit step.

### 3 · Derived shapes follow **the part that triggers them**, not the whole outfit

Shapes “needed because a certain piece is worn”, like foot-shape keys and anti-clipping shrink keys,
**belong to the part toggle of that piece**, not the whole-outfit switch layer.

Writing them in the whole-outfit layer amounts to “one fixed foot shape per outfit”: feet still on tiptoe after removing shoes, a flat foot stuffed into sandals.

#### Method
The shape is a function of `(整套档, 部件开关…)`, and one layer's conditions must use several parameters at once.
Don't lay out `档数 × 2^n` states — build **a few result states + multiple AnyState transitions with multiple conditions**:
each outfit only needs 1~3 transitions into them.

⚠ Multiple conditions in one transition are **AND**; you can't write **OR**. For “shoes on **or** socks on” you need two transitions.

#### Priority
`鞋开 → 鞋的形态　｜　鞋关+袜开 → 袜的形态　｜　都关 → 全部归 0`

⚠ **The default of “the sock's shape” is not “none”**. Shoes go over socks, and socks are mostly **rigid meshes modeled in the tiptoe pose**;
turn the shoes off and reset the foot shape to neutral, and the foot pokes out of the sock.
See [50 · Foot-shape keys go on the “socks”, not the “shoes”](../50-outfit-and-hair-assembly.md).
Both tables must be **measured**; don't copy.

### 4 · Visibility can be derived too: if it belongs to a “Boolean combination”, it can't stay in the original part table

Item three above covers **blend shapes** following parts. The same reasoning applies to **visibility**:
for some pieces “should it appear” isn't decided by one part, but by a Boolean combination of several.

> Evidence (2026-09-09 Project C): Violet Nocturne's `Straps` (material literally named `Anklet`,
> straps wrapped around the ankles) were filed under “top”. So with shoes and socks off, barefoot, two loops of ribbon still hung on the ankles.
> The requirement: show if either shoes **or** socks are on, hide only when both are off.

#### Method
Open **a new layer** as its owner, with both On/Off states writing `m_IsActive`,
conditions written as above: `鞋 If → On`, `袜 If → On`, `鞋 IfNot 且 袜 IfNot → Off`.

⚠ **You must also delete it from the original part's object table**; adding the new layer without deleting the old = two writers,
the later layer covers the earlier one, and the symptom is “sometimes right, sometimes not”, which checking rules one by one can't find.
After deleting, remember to add it to the generator's `Excluded` whitelist, otherwise the coverage self-check will flag it as missed.

#### Which way the cost is asymmetric
Once moved out, **the original part toggle no longer controls it** — turn off the top and the ankle straps stay.
That's intentional (it's really a leg piece), but **must go into the delivery memo**,
otherwise the client, testing by the intuition “turning off the top should remove everything”, will treat it as a new bug.

Conversely, if you can't let this go and want both (follow shoes/socks and also be suppressed by the top),
fall back to a **type-B override layer**: the piece stays owned by the top, and another layer writes 0 when “shoes and socks both off”.
The cost is that it can never escape the top layer's 0 — with top off + shoes on, the straps **won't** appear.
**Both are correct; which to choose depends on who this piece semantically belongs to**; don't go by feel, ask
“with the top fully off and only shoes on, should this thing be there?”

#### Criterion
Don't judge by looking at renders (one or two loops of thin strap can't distinguish “right” from “almost” in an image).
The criterion is an **authoritative artifact**: compute the four-cell truth table by “stacking clip curves in layer order”,
then `grep` the whole project for that path's `m_IsActive`; **there must be only one writer**.

---

> → [Multiple sources at the same position: use a radial](property-ownership-and-authoring/same-slot-multi-source-radial.md) — the two inherent flaws of multiple Toggles overriding each other; aggregate toggle scopes must be closed by semantics (2026-09-08 Milfy two pairs of ears); attachments tied to vendor toggles are easy to miss.

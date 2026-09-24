> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/问题定位/观测口径/判据本身可能是坏的.md)

# The criterion itself may be broken (four ways it breaks, and self-checks)

> Subpage split out of [`observation-criteria.md`](../observation-criteria.md). It takes over the section of the same name and the sections after it; "wrong timing", "wrong method" and "script has a bug" remain on the main page. Sister pages: [The shape of a criterion](shape-of-a-criterion.md), [Rendering and framing](rendering-and-framing.md).

## The criterion itself may be broken

Besides "wrong timing", "wrong method" and "script has a bug", there is a fourth category:
**the observation channel simply cannot render the target phenomenon.**

Typical: when a script builds a camera and renders to a `RenderTexture` to produce acceptance images, `GrabPass` doesn't work,
so transparent materials that rely on screen grab compositing get rendered as **solid color blocks**.
Judging from such images mistakes a render pipeline limitation for a model defect — and it looks very much like "successfully reproduced".

**Rule**: before switching to another observation method, first confirm **this channel can faithfully reproduce the target effect**.
If it can't, admit the criterion only reaches a certain layer (e.g. "queue table"),
and hand the rest to a channel that can reproduce it (the Game view in Play mode).

## "Can't see it" isn't necessarily the avatar's problem

First ask: **are you looking in the Scene view or the Game view?**
In the **Effects dropdown** of the Scene view toolbar, two toggles hide things:

- When **Always Refresh** is off, the Scene view only redraws on interaction, so particles don't keep advancing; **selecting a particle system forces continuous redraw** →
  the symptom is "particles are only visible when selected", identical at edit time and in Play. **This is not the avatar's problem.**
- When **Particle Systems** is off, the Scene view doesn't draw any particles at all.

**Criterion (do this first; don't start by examining the avatar)**: enter Play and switch to the **Game view** for a look (unaffected by these two toggles);
or render one image with an off-screen camera — if it renders, material / shader / size / layer / culling are all fine.

> Stepped in it (Project A eye-area particles): curve bindings, path remapping, animator layers, empty material slots, particle size — a whole round of checks all normal,
> and the runtime probe kept reporting `渲染器=True 可见=True 12 颗粒子在发射` (renderer=True visible=True 12 particles emitting) — the data was right; what was wrong was the means of observation.
> For a conflict of "data says normal, eyes say abnormal", suspect the means of observation first, then the observed object.

## The criterion's boundary is drawn wrong → separate page

Failures neatly on one side only, absolute thresholds falsely triggered by structural offsets (every statistical criterion must carry a self-check item that can refute itself), comparisons mismatched by name, difference criteria that can't tell design from misassembly, reproducing the delivered state requiring whole-layer simulation of vendor layers → **[The shape of a criterion](shape-of-a-criterion.md)**; criteria for verdict scripts on identifying the body, can't-decide, exemptions, labels, counting and reading artifacts → **[Criteria for verdict scripts](verdict-script-criteria.md)**.

## "Useless" doesn't mean "harmless"

When you find a change had no effect, the easiest handling is "just leave it, it does nothing anyway". That is wrong.

**Instance we stepped in**: enlarged a renderer's bounding box, then found it was overwritten at build time, i.e. ineffective.
Left it in without reverting — but the bounding box's **center determines transparency sorting** (sorted by distance from center to camera);
once the center moved, a previously intermittent front/back flicker became constant.

**Rule**: when you want to keep an "ineffective but harmless" change, stop —
**"harmless" is a claim that needs evidence, not a default**. If you can't say why it's harmless, revert it.
When reverting, use a precise revert (revert by property), not the undo stack (which undoes others' operations too).

## A probe must not let "missing" silently become a legitimate value

The previous section was about "the script computed wrong". This one is subtler: **the script didn't compute wrong, but it reported "I don't know" as a concrete answer.**

| API | Returns when not found | Gets read as |
|---|---|---|
| `AssetDatabase.LoadAssetAtPath<T>()` | `null` | "this field is empty" |
| `material.GetTexture(p)` | `null` | same as above |
| `transform.Find(路径)` | `null` | "this object doesn't exist" (actually **its name was changed by the bake**) |
| `material.GetFloat(不存在的属性)` | `0` | "this toggle is off" |
| `GameObject.Find(名字)` | `null` | "it's not in the scene" (actually **inactive objects weren't searched**) |

This kind of bug is especially costly because **the output looks very informative**:
this order's probe reported "all 44 properties hit glass_*", which invites conclusions more readily than "found nothing".

**Rule**: for every `null` / `0` in a probe, you must be able to answer "is this **truly absent**, or **did I just not find it**".
If you can't, print these two cases as two separate results.

**Criterion**: once the probe is written, run it once each with **one input known to exist** and **one known not to exist**
(same practice as [20 · Implementation pitfalls, section two "Back-check before producing numbers"](../../20-asset-inventory-and-import/implementation-pitfalls.md)). The former must not show "not found"; the latter must.

> Two measured cases (Project C):
> ① Cross-project material diff: the Wendy base avatar's textures aren't in this project → `LoadAssetAtPath` all null → reported as "field is empty";
> ② In the baked body `root.Find("_Acc/…/Ears")` returned null (AAO flattened and renamed the path)
> → the subsequent `SetActive` **silently did nothing**, and four of the six acceptance images were byte-for-byte identical.

## When resolution isn't enough, push the parameter to the extreme

**"Didn't take effect" and "effect is reversed" look exactly the same at low contrast.**
A light color overlaid on skin tone, a 5% deformation, a faint highlight difference — in these cases looking at images only gives "doesn't seem to change much",
and that observation is **equivalent** under both hypotheses; ten more images won't separate them.

**Technique**: push the parameter under test to its **most physically exaggerated** value so that the two hypotheses produce results **distinguishable by eye**,
take one shot, settle it, then set it back to normal.

> Measured (Project C · lilToon overlay layer):
> the glass color bled onto the torso. I guessed twice in a row ("mask RGB is all white", "it reads the alpha channel"),
> **both guesses, both wrong**. In the end I set `_Color2nd` to **pure red, alpha = 1** and rendered one image —
> the whole torso was scarlet and the legs not tinted at all; the conclusion "**polarity is reversed**" was obvious at a glance.
> Several earlier renders with α=0.45 light blue-violet couldn't distinguish anything.

**Trade-off**: this is a **diagnostic technique**, not an acceptance technique.
A conclusion that holds at extreme values still needs **re-verification** back at normal values (nonlinear blending, clamping, and post-processing may only act within some range).
The cost is just one render, whereas "guessing" costs one code revision per guess.

**Scope**: any mechanism with "a continuous intensity knob" — masks, blend weights, blend shapes,
Additive layer amplitude, PhysBone stiffness. **Turn the knob all the way first, then discuss whether the mechanism is right.**

## The criterion's direction may be reversed: first ask "if I **delete** the thing under test, does the metric get better"

The previous sections were all "the criterion measured wrong". There's a worse kind: **the criterion measures correctly, but it rewards the wrong answer.**

**Trigger**: any criterion that compresses a 3D shape/image into **a single scalar** to pick the best —
pixel variance, edge count, "tidiness", bounding box volume, average brightness.

**Self-check question** (one sentence, ask before producing numbers):

> **If I deleted the thing under test entirely, would this metric get better or worse?**

**Better → the criterion is broken**, no matter how accurately it measures. Because the optimum will converge to "nothing at all".

**Why it's easy to fall for**: such criteria **rank correctly on most samples** and only fail on extreme samples —
and sweep-type experiments ("five levels × five sets") are precisely hunting for extremes, so they **inevitably reach that extreme sample**.

> Measured (Project C): when choosing a foot-shape key with "lowest pixel variance" as the criterion,
> it picked `Shrink_Foot=100` — which **deleted 32% of the foot's length and nearly half its volume**,
> so the image had fewer edges, lowest variance, first place. And that shoe was a **pump that exposes the instep**, with nothing but emptiness inside the shoe opening.

**Fix**: **for coverage / fit requirements, criteria must come in pairs** —
one measures "is what should be covered covered", the other "is what shouldn't move still there". A one-sided criterion will always be fooled into a perfect score by "deleting the thing".

| One-sided (bad) | Paired (good) |
|---|---|
| Lowest image variance | Clipping vertex count == 0 **and** foot volume change < 5% |
| Fewest millimeters exposed | Exposure ≤ 0 **and** foot vertex count unchanged |

> Second case (2026-09-08 Project B_Milfy · high-heeled sandals, difference criterion):
> the correct answer `Foot_highheels` scored **12755**, **worse** than "write nothing" at 9531;
> the criterion's pick `Foot+Toe` (2468) rendered as "**shoes but no feet**".
> Three different implementations all reach the same wrong answer — because what's wrong is **the criterion's direction**, not the implementation.
> **Self-check**: does the candidate set include an option that "hides the thing under test"? If so, this difference criterion is systematically biased toward it,
> and **must be paired with per-candidate close-ups**; you can't look at the ranking alone (for other false negatives of difference criteria see section four of [The shape of a criterion](shape-of-a-criterion.md)).

See [Occlusion is not occupancy](../../55-accessory-placement/rebinding-armature-and-occupancy.md): the other face of the same trap —
"peep-toe shoes can fool the occupancy criterion into a perfect score".

## "0" and "all the same" both don't mean pass

**Identical metrics across candidates** → most likely nothing was zeroed or the key wasn't written, not "the candidates are equivalent";
**a 0** may mean "none", or "some, but below the gate" — especially when the threshold was calibrated on **another body**.
Both have caused real missed detections; trigger moments, self-check questions and fixes → **[Zero and same aren't pass](zero-and-same-arent-pass.md)**


- **Occlusion/raycast criteria** have their own page: [Occlusion criteria](occlusion-type-criteria.md) — you must cull faces that "occlude themselves", validate the criterion against known states, and also ask "is this zero a zero with margin".

> → [The log saying it was saved ≠ actually saved](logged-doesnt-mean-saved.md) — `JsonUtility` **silently writes empty** for a `List<T>` whose element type isn't marked `[Serializable]`; the log prints the in-memory Count, while on disk it's an empty file. After saving you must read it back and count.

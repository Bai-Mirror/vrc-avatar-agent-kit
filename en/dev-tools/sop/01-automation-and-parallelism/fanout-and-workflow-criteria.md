> 🌐 English translation · [中文原文](../../../../开发工具/SOP/01_自动化执行与并行/扇出与工作流判据.md)

> ← [01 · Automation and parallelism](../01-automation-and-parallelism.md)

# Fan-out Units, Workflow Criteria, Readiness Ratings

The problem this page solves: **when one thing is repeated N times, is it worth running a multi-agent parallel computation**, and what each stage still lacks to be fully automatic.
For scheduling and dependencies see the main page; here are the three tables that decide “whether to start a workflow”.

---

## 1. Units that can fan out within a stage

“Fan-out” = the same thing repeated N times, each independent, suited for multiple agents computing **lists** in parallel.

| Stage | Fan-out unit | Independence | Notes |
|---|---|---|---|
| 20 Asset import | **Inventory and completeness check** of each asset package | Independent | ⚠ **The import action itself must be serial**: several sub-packages of the same product share folders/material GUIDs, and concurrent import will swallow each other's assets |
| 40 Texture recoloring | Generating and scoring each recoloring candidate | Independent | Applying to the project must still be serial |
| 55 Accessory placement | Pose computation for each accessory | Independent | Compute all poses into a table, then write to the scene in one go |
| 70 Regression test | **Judging** each combination | Independent | Just `Apply` parameters with real animation data; no bake needed |
| 80 Performance optimization | Tier judgment for each texture, attachment criterion for each PhysBone chain | Independent | Criteria are closed-form, naturally suited to fan-out |
| 05 Review | Each model | Independent | Already organized in parallel |

**Cannot fan out**: anything requiring a bake (expensive and mutually exclusive), asset import actions, scene writes.

---

## 2. When a multi-agent workflow is worth it

**Worth it** (start only if all hold):

1. Number of units ≥ 5
2. Each unit is **read-only + computation**, and the output is a one-line conclusion or a short list
3. The criterion is closed-form (number, boolean, enum) and does not depend on cross-unit context

Typical: pose computation for accessory placement, texture tiering, judging combination regressions, cross-model review, bulk document rewriting.

**Not worth it**:

- Anything that touches Unity (parallelism is meaningless and they interrupt each other)
- Fewer than 5 units (orchestration overhead exceeds the benefit)
- Criteria that require looking at images (image granularity and camera positions must all be unified; fan-out increases inconsistency)
- Order dependencies (asset import, layer-order design)

---

## 3. Automation readiness ratings

| Stage | Rating | Where it is stuck |
|---|---|---|
| 10 Order intake and filing | **Fully automatic** | — |
| 20 Asset inventory and import | **Fully automatic** | Import actions just need to be serial |
| 30a Face sculpting values | Manual | Aesthetics |
| 30b Bake, export, validation | **Fully automatic** | — |
| 35 Face tracking | **Fully automatic** | ⚠ The installer clones the avatar; tools that find the avatar by name will modify the wrong object |
| 40 Texture recoloring | Semi-automatic | Final decision needs a human nod; generating candidates and review are fully automatic |
| 50 Outfit and hairstyle fitting | **Fully automatic** | — |
| 55 Accessory placement | **Fully automatic** | Poses have closed-form criteria; look-and-feel issues go through review |
| 60 Menus and animator layers | **Fully automatic** | Layer order must follow established conventions, no improvising on the spot |
| 70 Regression test | Semi-automatic | Platform-override changes **cannot be verified in the editor**; must be tested on a real device |
| 80 Performance optimization | **Fully automatic** | PhysBone look-and-feel changes can only be seen in Play |
| 90 Delivery packaging | **Fully automatic** | — |
| 95 Upload final review | Manual | SDK upload must be done by a human |

**Net conclusion**: of 14 stages, 9 can be fully automatic, 3 semi-automatic, and only 2 are truly manual.
The bottleneck is not automation capability but **queuing at the gates**.

---

## 4. Second-stage fan-out = first-stage **output count** × number of perspectives; you must cap it yourself

**Trigger moment**: when writing a two-stage workflow like `pipeline(items, investigate, verify each)`.

**Hit before (2026-09-20, poke false-negative investigation)**: the first stage had 4 investigation Agents, and I thought the fan-out was 4.
In fact the second stage was “**each finding** × 2 refutation perspectives”, and the 4 Agents each submitted 8–11 findings → 4 × 9 × 2 ≈ **70 sub-Agents**.
The user only noticed something was wrong upon seeing 70 concurrent agents; I had not noticed myself.

**Checkable question** (must ask before launching):
> Am I limiting the **number of dimensions** or the **total of the second stage**? How many items will each first-stage Agent submit? Is that count **decided by the model** or by me?

**Rule**: whenever the size of the next stage is determined by the **output count** of the previous stage, it must be explicitly capped in the script:

```js
const TOP = 3                                   // max items to verify per dimension
const picked = (res.findings || [])
  .filter(f => f.confidence !== 'low')          // filter by confidence first
  .slice(0, TOP)                                // then hard cut
```

**Trade-off**: capping drops findings ranked lower. The cost is acceptable because
① have the first stage output in order of importance; ② if something is truly missed, run another targeted round with the existing conclusions.
Conversely, the cost of not capping is **uncontrollable** — the count is up to the model, could be 3 or 30.

**Another point**: adding `maxItems` to an array in the schema only constrains a single Agent's output;
it cannot constrain the product “number of dimensions × items per dimension”, so do not use it as a cap.

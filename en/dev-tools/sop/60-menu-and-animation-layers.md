> 🌐 English translation · [中文原文](<../../../开发工具/SOP/60_菜单与动画层.md>)

# 60 · Menu and animator layers　🤖

**Purpose**: make outfit switching controllable, keep parameters within budget, keep the structure script-traversable.
**Output**: menu assets + animator layers + `菜单结构.md`
**This is the most bug-dense stage.**

## The one-sentence iron rule

**Anything that already has a vendor parameter layer: always drive the parameter; don't touch the mesh.**
The same mistake was made three times in one order:

> → The three instances (one vendor parameter controlling mesh/bone pose/blend shapes at once) and the comparison of three projects' intervention intensity → [Structural conventions · Measured samples](60-menu-and-animation-layers/structural-conventions.md).

**Only turning off meshes is always safe** (with the mesh off, it doesn't matter how the bones are folded);
problems only go one way — **mesh on but bones not posed correctly**.

## Second iron rule: a property may only be managed by one layer

When moving layers, **you must also delete it from the original layer's table at the same time**. The winning rules for things written in two places **come in two kinds, and they're opposite**:

| Written in two places | Winner | Symptom |
|---|---|---|
| Animation curves | **By layer order**; later covers earlier | Stable: the toggle “does nothing no matter how you click” |
| Parameters (Driver Set) | **By event order**; whoever enters a state last wins | Intermittent: “after switching around and back, it came back by itself” |

The second can't be proven at edit time or by combination renders; the only way is to **read the controller and count “how many layers write this parameter”**.
Fixes and the four authoring styles → [Property ownership and authoring](60-menu-and-animation-layers/property-ownership-and-authoring.md).

## Two implementation routes, chosen by the base avatar's situation

| | A. MA reactive components (Object Toggle + Menu Item) | B. Hand-written AnimatorController layers (`菜单架构/MenuGen.cs`) |
|---|---|---|
| Form | One component per toggle, declarative | Generates controller + clips + menu assets |
| Suited to | **Clean base avatar, outfits ship MA and don't interfere with each other** | **Must interact with the vendor's existing parameter layers, needs precise layer-order control** |
| Advantages | Simple to generate and read back; structure directly traversable | Layer order fully controllable; can sync vendor parameters with ParameterDriver |
| Cost | Layer order decided by MA; hard to override when competing with vendor layers for the same property | Lots of code; changing base avatar means refilling three tables |

**Criterion**: first see which parameter layers the base avatar and outfits ship with ([50's Probe](50-outfit-and-hair-assembly.md)).
If vendor parameter layers **overlap** with what you need to control, take B; if **no overlap at all**, take A.

## Hard constraints

| Item | Limit |
|---|---|
| Controls per menu | **8** |
| Parameter budget | **256 bit** (Int/Float 8 each, Bool 1). Exceeding it doesn't necessarily mean cutting features — VRCFury compresses; see [VRCFury parameter compression](60-menu-and-animation-layers/vrcfury-parameter-compression.md) |
| ControlType | 101 button / 102 toggle / 103 submenu / 203 radial |

A plugin's own MenuInstaller slots into its own submenu via `installTargetMenu`; **don't modify plugin prefabs**.

> → [Parameter audit and semantic conflicts](60-menu-and-animation-layers/parameter-audit-and-semantic-conflicts.md): build-time generated parameters aren't visible at edit time (24/108 → 92/177); the common defect on top of the head is a semantic conflict (Milfy's two pairs of ears); don't write the criterion as “is there clipping”.

## Deterministic steps

### Step 1 · Probe parameter layers, choose the route　🤖

**Preconditions**
- [ ] Environment confirmed usable per [02](02-environment-and-manual-intervention.md)
- [ ] [50](50-outfit-and-hair-assembly.md) passed

**Execution**
1. Run 50's `Probe()` and list vendor parameter layers and the objects/blend shapes each controls
2. Intersect with the objects this order needs to control; write the intersection count and the route in the first line of `菜单结构.md`

**Post-criteria**

| Expected | How to read |
|---|---|
| Intersection == 0 → route A; > 0 → route B | First line of `菜单结构.md` |

**STOP**
- `Probe()` errors or some piece's parameter layers can't be read → hand back to a human

### Step 2 · Produce menu structure candidates　🎨 candidates need a decision

**Preconditions**
- [ ] Step 1 has stated the route
- [ ] Part atlases for each outfit exist (mark missing ones “to fill in”, [Part understanding and menu layout](50-outfit-and-hair-assembly/part-understanding-and-menu-layout.md))

**Execution**
1. Write `菜单结构.md` per [Structural conventions](60-menu-and-animation-layers/structural-conventions.md) (mechanisms hard, clustering soft) and “Hard constraints”: one line per control — section, ControlType, parameter name/type, target object
2. Only sections and naming get 2 candidates for a human to decide; mechanisms get no candidates

**Post-criteria**

| Expected | How to read |
|---|---|
| Controls per menu ≤ 8 | Count lines per section |
| Sum with Int/Float 8 each, Bool 1 ≤ 256 | Sum the parameter column |
| Whole outfit, hair, ≥2 accessories at the same position: ControlType == 203; ring: two lines, 102 + 203 (0–7) | Control column |

**STOP**
- Bits > 256 → hand back to a human to cut features; don't delete controls on your own
- Sections not decided → don't enter step 3

### Step 3 · Fill the conflict table from screenshots　🎨 candidates need a decision

**Preconditions**
- [ ] Step 2 decided

**Execution**
1. **First enumerate “sources” by position, not suspect pairs by piece** — for each position (ears/tail/head top/wrist/finger/back)
   list **every** piece that could occupy it: base avatar built-ins, each outfit's built-ins, **each hairstyle's built-ins**, purchased accessories.
   Let the scene enumerate the source list + solo-render each piece to confirm what it actually is; **don't guess by name**
2. Render each combination offscreen and send clipping to [05](05-multi-model-review.md) review; don't conclude yourself
3. Write confirmed ones into the conflict table, each noting its position on the priority chain

**Post-criteria**

| Expected | How to read |
|---|---|
| **Each position's source list matches “pieces in the scene that land at that position” item by item** | Source table vs solo renders |
| Number of pairs with both “A overrides B” and “B overrides A” == 0 | Count the conflict table by unordered pairs |
| Empty priority-chain positions == 0 | Conflict table |
| **Sources on at the same position in the default state ≤ 1** | Count after evaluating with default parameters |

**STOP**
- Review conclusions disagree → hand back to a human to look at the images

### Step 4 · Generate assets and read back　🤖

**Preconditions**
- [ ] Step 3 conflict table settled
- [ ] Only this one change lands; the previous invalid one has been reverted with `PrefabUtility.RevertPropertyOverride`, not the undo stack

**Execution**
1. A: add MA Object Toggle + Menu Item; B: fill the three tables of `菜单架构/MenuGen.cs` and run the menu item it registers
2. Check: override threshold == `1f / 档数`; single-frame clips get a `t = 1/60` tail frame; parent objects go into the curve table
3. Readback verification + armature height self-check ([Scene corruption and recovery](troubleshooting/scene-corruption-and-recovery.md)), then save

**Post-criteria**

| Expected | How to read |
|---|---|
| Each clip `GetCurveBindings(...).Length == want` | Generator readback line |
| Each menu asset > 330 bytes | File system |
| `eye.L` world y differs from baseline by < 0.02 | Self-check output line |

**STOP**
- Readback counts don't match → don't rerun; first check [Generator implementation pitfalls](60-menu-and-animation-layers/generator-implementation-pitfalls.md) ①
- Self-check fails → don't save

### Step 5 · Measure the delivery state after baking　🤖

**Preconditions**
- [ ] Step 4 passed and saved

**Execution**
1. Manual NDMF bake; all criteria read the **merged** controller, not the source project
2. Enter Play and run `ParamAudit.cs`
3. Run the full combination of `服装档位 × 冲突开关` with real animation data (`A2State.cs`)
4. Clean up `<名字>(Clone)`, then run the armature height self-check

**Post-criteria**

| Expected | How to read |
|---|---|
| Post-build bits ≤ 256; parameters without menu or animator layer == 0 | `ParamAudit.cs` output |
| Deadlocked cells where “not one piece is on at that body part” == 0 | Combination traversal output |
| Layer names targeted by `VRCAnimatorLayerControl` match the merged controller | Merged controller layer list |
| `VRCAvatarDescriptor` == 1; `eye.L` difference < 0.02 | Component count; self-check output line |

**STOP**
- Deadlocked cells > 0 → go back to step 3 to check override direction; don't change the generator
- Bits > 256 → go back to step 2
- Parameter Driver steps identical in offscreen images = expected; verify in Play only

## Acceptance

```
ParamAudit.cs (in Play mode)  → parameter count / bit count / whether each parameter has a menu and an animator layer
Per-asset readback            → byte size > empty-menu baseline
Per-combination traversal     → see 70 regression test
```

**You can read the menu tree without opening Unity**: for “what does the menu look like” and “which parameter a control is bound to”, parse the `.asset` YAML directly — fast and comparable across projects.
⚠ Indentation pitfall: controls are at **2 spaces**, `subParameters` entries at **4 spaces**; splitting by `\s*` produces ghost controls; group by indentation level first, then split.

## Symptom → where to look

Toggle does nothing no matter what (most common: a later layer unconditionally writes the same property), nothing shows at a position, mesh present but shape wrong →
the canonical triage table is in [03 · Symptom → where to look](03-assembly-and-conflict-rules.md).

> **Toggle shows in the Expressions menu but nothing happens in game** → two mandatory checks: layer default weight 0 with nobody raising it (H3-Eku `Breast`),
> clip paths unresolvable after AAO deleted/renamed them (dead parameters). The four mandatory checks (MA MenuItem, whether `ClothGroup` is in the real scene,
> mutual-exclusion mechanisms like `3bitInt`, dead parameters) → [Mutual-exclusion mechanisms](60-menu-and-animation-layers/mutual-exclusion-mechanism.md).

## Subpage index

| Subpage | When to open |
|---|---|
| [Layer order and override](60-menu-and-animation-layers/layer-order-and-override.md) | Ordering layers on route B; clipping as soon as an accessory is on; wrong step overridden after extending a radial; “restore to X when off”; outfit ships its own underwear |
| [Property ownership and authoring](60-menu-and-animation-layers/property-ownership-and-authoring.md) | A property written in two places; Driver vs curve winning rules differ; choosing among the four authoring styles; missed ownership of root objects/containers/derived shapes; multiple sources at one position should use a radial |
| [Humanoid arms and fingers](60-menu-and-animation-layers/humanoid-arms-and-fingers.md) | Arm pose requirements; all gestures broken, hands half-clenched; pose doesn't appear on desktop/in VR |
| [Generator implementation pitfalls](60-menu-and-animation-layers/generator-implementation-pitfalls.md) | Must read before changing `MenuGen.cs`; empty assets, unchanged images, off-step values, single-frame clips, clones, vendor Float parameters, particles, finger curve names; **material/texture-swap steps**; **two patch scripts writing the same field** |
| [Mutual-exclusion mechanisms](60-menu-and-animation-layers/mutual-exclusion-mechanism.md) | How to make multiple outfits/pieces at the same body part mutually exclusive; catalog and failure scenarios of `ClothGroup`, `3bitInt`, timeline radials, ObjectToggle; four mandatory checks (MA MenuItem, dead parameters, layer weight 0) |
| [Structural conventions](60-menu-and-animation-layers/structural-conventions.md) | Step 2; radials for whole outfits/hair, parts grouped by body part, two controls for rings; sections redivided per model; linked instances |
| [Parameter audit and semantic conflicts](60-menu-and-animation-layers/parameter-audit-and-semantic-conflicts.md) | Parameter count at edit time ≠ after build; semantic conflicts |
| [VRCFury parameter compression](60-menu-and-animation-layers/vrcfury-parameter-compression.md) | Look here first when bits exceed 256; don't rush to cut features |

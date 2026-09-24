> 🌐 English translation · [中文原文](<../../../../../开发工具/SOP/60_菜单与动画层/生成器实现坑/落盘与幂等.md>)

# Generator implementation pitfalls · Saving and idempotency

> ← [Generator implementation pitfalls (index)](../generator-implementation-pitfalls.md)　Parent: [60 · Menu and animator layers](../../60-menu-and-animation-layers.md)

The problem this page solves: pitfalls when the generator **writes assets, renames, reruns, or bakes clones** — symptoms that look like logic errors, with root causes in asset saving and idempotency.

## Four pitfalls you will hit

**① “Turn off B along the way when switching A” must change the parameter with a ParameterDriver, not write B's controlled property in the clip.**
Changing the parameter is “turn off once”, and it can be turned on again later; writing the property holds it down permanently, effectively disabling B.
> Measured: the first version did exactly this, and the hat could never be turned on.

**② Watch out for vendor layers that “play once and stop”.**
Some layers are structured as `A → play to end → unconditionally jump to Empty`, and after entering Empty they write no properties.
If you've overridden the properties it manages elsewhere, the values get **stuck permanently**.
> Measured: cat ears “disappearing after switching hairstyles and back” was exactly this.

**③ Generated assets may be empty, with no error.**
With `AssetDatabase.CreateAsset` **saving first, then adding content to the List, then SetDirty + SaveAssets** —
this change isn't guaranteed to be flushed. In one generation of 7 menu assets, 4 were fine and 3 were saved empty.
> **Correct approach**: create instances → **fill in the content** → finally `CreateAsset` all at once (in dependency order, leaves first) → **read back and verify**.
> **Detection technique**: compare the byte size of the same asset across commits — an empty menu is about 330 bytes, each control about 200 bytes.

**④ After face sculpting is baked into the mesh, expression extrapolation must be checked.**
Iterate over all `.anim` in the project; curve peak + baked amount > 100 is out of bounds.
> Measured: 17 of 102 clips out of bounds, max 177.7. Fix: change written values to `100 − 烘焙量`; for multi-keyframe curves scale the whole curve proportionally.

## Six pitfalls every generator hits (measured 2026-09-01; every one was actually hit)

This section is written as “symptom → root cause”, because what these pitfalls share is that **the symptoms are misleading**:
they look like logic errors but are actually low-level issues like asset saving, render capture, and parameter values.

### ① Fill content before CreateAsset; after saving you must read back and verify

**Symptom**: the generation report says “covers 16 objects”, but the saved `.anim` is only 1307 bytes with **zero curves**.
Every acceptance image after that is wrong, with no visible reason — because the script's own log is correct.

**Root cause**: content written to an asset after `AssetDatabase.CreateAsset()` is **silently lost**.
ScriptableObject List fields and AnimationClip curves are both affected, and **it doesn't lose every time** (harder to track down).

**Method**: fill the object completely in memory and `CreateAsset` only as the last step. Immediately after saving, read back and compare counts:

```csharp
int want = AnimationUtility.GetCurveBindings(c).Length;
AssetDatabase.CreateAsset(c, path);
// … after everything has been generated …
AssetDatabase.SaveAssets(); AssetDatabase.Refresh();
int got = AnimationUtility.GetCurveBindings(
    AssetDatabase.LoadAssetAtPath<AnimationClip>(path)).Length;
if (got != want) 报错;
```

**Where the assertion goes matters more than the assertion itself**: readback must reload the asset from disk and count; there must be no `DeleteAsset` / `Refresh` in the middle of generation.


### ⑥ Manual NDMF baking leaves a `<名字>(Clone)` in the scene

**Symptom**: you changed parameters and re-rendered, but the image didn't change at all.

**Root cause**: offscreen rendering also renders the clone as an avatar, adding `_00_` / `_01_` indices to file names;
the contact sheet sorts by file name and takes the first → it gets the **clone's** image, and the clone is frozen at the moment of baking.

**Method**: the bake tool cleans up the `VRCAvatarDescriptor` it added when it finishes;
the contact sheet tool explicitly excludes indexed file names (`img_tools.py sheet-by-tag` already does this).

## ⑦ Rename menu assets with `RenameAsset`; never delete and recreate

When sections are redivided, menus get renamed (`配件` → `服装配件`).
`DeleteAsset` + `CreateAsset` changes the GUID; **the plugin MenuInstaller's `installTargetMenu`
and the descriptor's `expressionsMenu` silently become null**, and everything falls back to the root menu.

```csharp
var err = AssetDatabase.RenameAsset(oldPath, newName);   // GUID unchanged
if (!string.IsNullOrEmpty(err)) throw new Exception(err); // the return value is an error string, not a bool
```
Likewise: if a menu/parameter asset **already exists, clear its content and reuse it in place**; only clips and controllers are pure generated output that can be recreated.

**Tracking down references that became null**: grep the guid of that `objectReference` in the scene YAML and compare with the guid in the asset's `.meta`; if they don't match, that's the disease.

**Material assignment is specified explicitly by “object name + slot index”**, not by matching the name of the material currently in the slot — when the slot is null there's no name to match, and on the second run the name has already changed.

**Check scripts must run both before and after the fix**; run only after the fix and you can't catch “the fix didn't happen”.

**Parameters referenced by the menu must be declared in the scene's `ModularAvatarParameters`**; the criterion is that the set difference in both directions is empty; **parameters with `localOnly=1` don't count toward the sync bit budget**.

## ⑦-2 · `[MenuItem]` names **must not contain `/`**

Unity treats `/` as a **submenu separator**. `[MenuItem("Milfy/73 量 脚型（鞋 / 袜 两种场景）")]`
actually creates a three-level menu `Milfy > 73 量 脚型（鞋 > 袜 两种场景）`,
and the item you want to call **doesn't exist at all** — `execute_menu_item` reports
“invalid, disabled, or context-dependent”, **which looks like a compile failure**.

**Criterion (do this first)**: look at the timestamp of `Library/ScriptAssemblies/Assembly-CSharp-Editor.dll`.
Newer than the script → it compiled; the problem is elsewhere (name, `[MenuItem]` spelling, class not static).
Older than the script → only then is it a compile problem; grep `error CS` in `Editor.log`.
⚠ `Editor.log` is **shared by multiple Unity instances**; errors you grep may come from another project — confirm by path.

## ⑧ Generators must be **idempotent**: one call may run twice

When calling menu items via MCP / automation, **a timeout doesn't mean it didn't run**; a client retry makes it run a second time.
Symptom: the log says “renamed: none”, “alignment changes 0”, looking like it did nothing, when actually the first run already did everything.

**Requirement**: write every step as “skip if already in the target state”, including creating containers, installing the second instance, renaming, and aligning the scene.
**Don't use “change count > 0” as the success criterion** — an idempotent script's second run is 0 by design.

## ⑨ Writing leaf names in the table is ambiguous when names collide — you need a “full path” form

The advantage of leaf-name resolution is that the table needn't change when swapping base avatars/recolors. But once two instances sit under a container,
`Jacket` matches two. The resolver must **throw** on ambiguity (not take the first),
and also provide an escape hatch like `X("完整路径")` for cases that genuinely need to name names.

## ⑩ After generation, **align the edit-time scene to the default parameters**, and run an ancestor self-check

Clips only take effect at runtime; the bare edit-time state isn't the same as the delivery state.
Don't hand-write a list of “what should be on” — **actually apply, in layer order, the clips of the states selected by default parameters**,
so the list comes from the animation data itself.

Also run an **ancestor self-check**: for every path the default state writes true, walk up through its ancestors;
if an ancestor is off **and not managed by any layer**, throw. This is the only criterion that can automatically catch the “root object has no owner” class —
combination traversal can't find it, because it only looks at the written paths themselves. See
[Property ownership and authoring](../property-ownership-and-authoring.md).


## One field may only be written by one script

### Trigger
**The same project already has a string of patch scripts** (`Fix60A` … `Fix60AB`), and you're adding another,
or rerunning one of them.

### Question
**“Which earlier script also writes the field my script writes? Will rerunning it overwrite my results?”**

Patch scripts are inherently written to be **idempotent and rerunnable** (each sets its own part from scratch),
which is a strength **within a single** script, but becomes a hazard once two scripts write the same field:
**the run order determines the final value, and the order is decided ad hoc by a human.**

### What to do if you get it wrong
Three treatments, by priority:

1. **Merge** into one script — the field has a single write point; cleanest;
2. The latter **reads the former's output** (the former writes a file, the latter reads the constant), and fix the constant in the former;
3. If they really must stay separate: state in **both scripts' file headers** “who is ultimately responsible for this field”,
   and have the non-responsible one **skip** that field.

⚠ Don't use “mind the run order” as the solution — that knowledge only lives in the current conversation and is gone next round.

### Criterion
`grep -l '"_那个字段"' Assets/Editor/<单号>/*.cs`, **the hit count must be 1**.
≥2 hits must be handled as above. This criterion takes two seconds; worth running every time a patch script is added.

### Evidence (2026-09-08 Project C)
`Fix60X` and `Fix60Z` both wrote `_Main2ndBlendMask`: X assigned the original mask, Z the inverted mask.
After Z fixed it, I reran X for something else, and **the original mask was written back**;
the symptom was “the polarity problem just fixed came back on its own”, and it took a round of investigation to find I'd overwritten it myself.
Fix: change the mask path in X to Z's output path (option 2 above), and add comments in both places.

### Deleting and recreating a directory nulls references on the **face-tracking clone root** (2026-09-19 Project A)
- **Trigger**: the generator starts with `AssetDatabase.DeleteAsset(<Gen 目录>)` and then recreates it, while the scene has a second avatar root cloned by the face-tracking installer.
- **Symptom**: Unity nulls scene references pointing to deleted assets; the generator only reconnects the **original root** by name, and 13 references on the live face-tracking root (`_Menu`'s MergeAnimator, the descriptor's `expressionsMenu`, each MenuInstaller) stay empty. After build our FX isn't merged in, the menu is disconnected, and AAO merges all clothing as static pieces into one — in Play, switching whole outfits **appears to change nothing**, and the renderer count drops sharply (166→114).
- **Question**: “Before and after regeneration, is the scene's reference count to each asset in the Gen directory the same?” — count by the `.meta` guid in the `.unity` and compare asset by asset with the previous commit; fewer means a broken link.
- **Method**: at the end, the generator backfills the Gen references on the original root to other roots with the same name prefix by “same relative path, same type and index of component, same property path” (fill empties only, don't overwrite); see Project A `MenuGenA2.MirrorGenRefsToClones()`. Better still is not deleting the directory and reusing assets in place (the approach of Project B MenuGen60), leaving GUIDs and references untouched.

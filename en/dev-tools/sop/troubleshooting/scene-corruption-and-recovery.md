> 🌐 English translation · [中文原文](../../../../开发工具/SOP/问题定位/场景损坏与恢复.md)

# Troubleshooting · Scene Corruption and Recovery

> This page covers **what to do after you have broken a scene**, and a few calls that have actually broken scenes before.
> Created 2026-09-03, prompted by stepping into the same pit a second time on Project A.

---

## ⛔ Never call `clip.SampleAnimation` on an avatar

```csharp
clip.SampleAnimation(avatar, t);   // ← on a humanoid avatar this is pressing the self-destruct button
```

The avatar uses a **Humanoid rig**. `SampleAnimation` does not "only write the few curves in the clip";
it **runs the animation through the Animator for retargeting**. When the clip has no muscle curves,
**the entire skeleton is written into a zero pose and collapses**.

Measured (Kaguya base avatar): `eye.L` world y went from **1.0551 → 0.339**, `Hips` dropped from 0.7306 to near 0.

Three things that fool you:

1. **A clip containing only boolean curves like `m_IsActive` / `m_Enabled` collapses it just the same.**
   The criterion is not "is this clip a humanoid clip", it is **"is the avatar a humanoid rig"**.
   (I stepped in it the second time precisely because I used the wrong criterion, and even wrote that wrong criterion into the tool's header comment.)
2. **It writes the scene directly, bypassing Undo.** Restoring only the few objects the clip touched in `finally` will not save you.
3. **If you save after the collapse, the scene on disk is broken too.**

### The right way to verify curve bindings

- **Preferred: don't sample at all.** Reading the clip data + checking whether objects exist answers 99% of questions:
  ```csharp
  foreach (var b in AnimationUtility.GetCurveBindings(clip))
  {
      var curve = AnimationUtility.GetEditorCurve(clip, b);
      var tr = avatar.transform.Find(b.path);        // is the path right
      var cmp = tr == null ? null : tr.GetComponent(b.type);  // is the component there
      // curve.Evaluate(t) is the value this state should write
  }
  ```
- If you truly must sample, use `AnimationMode.BeginSampling()` / `SampleAnimationClip()` / `EndSampling()`
  — it has its own restore mechanism.
- **Runtime behavior always goes into Play and is read with probes**; don't try to "simulate" it at edit time.

---

## Keep a skeleton-height self-check on hand and run it after every change

Compare a few known world coordinates; it tells you dead-or-alive at a glance. Put it in the tooling and **run it every time after changing the scene and before saving**.

```csharp
var eye  = avatar.transform.Find("Armature/Hips/Spine/Chest/Neck/Head/eye.L");
var hips = avatar.transform.Find("Armature/Hips");
bool ok = Mathf.Abs(eye.position.y - EYE_L_Y_已知good值) < 0.02f;
```

At the start of each project, record the world y of `eye.L` / `Hips` in the project status document.
Reference implementation: Project A's `Assets/Editor/AvatarGen/SceneRecover.cs`.

**Ordering discipline: self-check first, save second.** Saving without confirming state turns a recoverable error into an unrecoverable one.

---

## How to rescue a scene that is already broken (from cheapest to most expensive)

### ① Not saved yet → reload the scene

```csharp
EditorSceneManager.OpenScene(path, OpenSceneMode.Single);
```
Called from a script it **does not show a save prompt**; it simply discards in-memory changes.
(`EditorSceneManager.ClearSceneDirtiness` is not public in 2022.3 — don't bother looking.)

**Reloading clears the Undo stack** — unsaved user changes cannot be undone after reloading, so make sure everything that should be saved is saved before you act.

### ② Already saved → `Temp/__Backupscenes/0.backup`

Unity writes a scene snapshot here **every time you enter Play**. It is a binary format, but Unity can open it directly.

```
cp Temp/__Backupscenes/0.backup Assets/<某处>/_recover.unity
```
Then:
```csharp
EditorSceneManager.OpenScene("Assets/<某处>/_recover.unity", OpenSceneMode.Single);
// → run the skeleton self-check to confirm this copy is clean
EditorSceneManager.SaveScene(activeScene, "Assets/<真实路径>.unity");  // ForceText saves it as text
EditorSceneManager.OpenScene("Assets/<真实路径>.unity", OpenSceneMode.Single);
```
After the rescue, **delete `_recover.unity` and its .meta**; don't leave them in the delivery directory.

**Precondition**: the timestamp of that Play entry must be earlier than the moment of corruption. Check the times with `ls -la Temp/__Backupscenes/` first.

### ③ What if things the user adjusted by hand are gone

Don't count on "undo N steps" — even capping the step count at your own number of operations may undo someone else's work.
Better: use **known world coordinates** as the criterion and stop once they match, or use `RevertAllDownToGroup`.


**An Undo loop that "undoes until the criterion is satisfied" undoes the user's work along with yours** (measured: undoing 300 steps removed unsaved nail art) — cap the step count at the number of `RecordObject` calls you actually made, not by the criterion.

---

## Other known calls that "silently break the scene"

| Call | Consequence | Alternative |
|---|---|---|
| `clip.SampleAnimation(humanoidAvatar, t)` | Skeleton collapses | See above |
| Calling `AvatarProcessor.ProcessAvatar` in a loop | Eats a dozen-plus GB, freezes the editor; piles of `(Clone)` accumulate in the scene | Once is enough; clear the clones before each run |
| Entering Play and being interrupted by a script recompile | Scene restore on exiting Play may be incomplete (all accessories on, skeleton stuck in an animation pose) | Finish editing and compiling scripts before entering Play; run the skeleton self-check after exiting |
| Directly editing prefab assets under `Assets/<厂商>/**` | Overwritten when the vendor package is reimported, and pollutes other projects | Edit the components on the **scene instance** |
| Deleting the source of a script that is running while a bake hangs | **Does not stop it**; instead it queues a domain reload; the main thread is occupied, so the reload never gets its turn → looks like a complete hang | The only option is killing the process (the "Hold on" progress bar **has no cancel button**) |
| `DestroyImmediate(clone)` | Only deletes the scene object; **does not delete the generated assets written to `Packages/nadena.dev.ndmf/__Generated/<克隆名>/`** | Manually clean that directory after every bake |

---

## Self-check list before reporting "X didn't take effect"

Use together with [Observation criteria](observation-criteria.md):

1. Was this observation taken at **runtime**? Edit-time bakes don't run PhysBone / Animator / Parameter Driver.
2. **Is the PlayableGraph valid**? GestureManager only takes over after you click the avatar once in the Inspector.
   If the probe says `PlayableGraph 无效` (PlayableGraph invalid), every "didn't take effect" from that run doesn't count.
3. Particle systems **don't run at all** at edit time unless selected in the Hierarchy. "No particles seen" at edit time is not evidence.
4. Is a second layer fighting over the same property? Scan all `.anim` files in the project and compare by path + attribute.
5. Does the observation script itself have a bug? First check it backwards against **one known positive and one known negative sample**.

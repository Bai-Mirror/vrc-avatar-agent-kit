> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/state-driver-isolation.md)

# T1 · Callback isolation, avatar resolution, GestureManager takeover <!-- nav -->

> Formerly: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (original `审查/README.md`) §3.0.2 / "Avatar resolution rules" / "GestureManager takeover" / §3.1. § numbers follow the original; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous: [T1 · What each state does, sanity checks, volatile blend shapes](state-driver-steps.md) · Next: [T1 · reset modes and switch-residue tests](state-driver-reset.md) <!-- nav -->

### 3.0.2 Project-side editor callback isolation (`isolated_callbacks.json`, task G, shared by T1/T2/T3)

At the start of a request (`AuditRunner.Begin` calls `AuditCallbackIsolation.Install`), reflection is used to do three things:

1. Read the invocation list of `EditorApplication.update`;
2. Read the invocation list of `EditorApplication.playModeStateChanged` (the event's real storage lives in the static field
   `m_PlayModeStateChangedEvent` → `EventWithPerformanceTracker<T>` → `DelegateWithHandle<T>` → `Entry.Reference`;
   this tool only reads it out; removal goes through the official `remove_playModeStateChanged` accessor without altering internal structures);
3. For the known `AvatarGen.RuntimeProbe`: if the static field `_armed` exists, set it to `false`.

Every callback whose method's assembly name starts with **`Assembly-CSharp`** and whose declaring type is not in the **`AvatarAudit`** namespace is removed
(this tool's own types are in the `AvatarAudit` namespace — a double exclusion; since T-09 they live in the `AvatarAudit.Editor` assembly,
whose name does not start with `Assembly-CSharp` anyway), and written to the output directory's
`isolated_callbacks.json` (`isolated_callbacks` is a list of `ClassName.MethodName`).

**Timing (critical)**: removed callbacks are **not re-attached during the Cleanup in Play mode**. The old probes in these callbacks write files under `Assets/` precisely on `ExitingPlayMode` /
`EnteredEditMode`; Cleanup usually still runs inside Play, so re-attaching then would still fire them when Play exits.
Therefore: `Install` additionally subscribes to `playModeStateChanged` once → on receiving **`EnteredEditMode`** it re-attaches the removed callbacks in their original order,
writes `restored_at` back into `isolated_callbacks.json`, and unsubscribes itself; to avoid modifying the subscription table during event dispatch, the actual re-attach is scheduled on
`EditorApplication.delayCall`. Exception: if the request ran in edit mode to begin with (T3 allows this), then at Cleanup `EditorApplication.isPlaying=false`,
there is no "next Play exit", and `AuditRunner.Stop()` calls `AuditCallbackIsolation.Cleanup()` to restore immediately.

Side effect: during this round's Play these old probes do not run at all (the files they want to write are not produced); they are restored after exiting Play back to edit mode.
If the editor is force-killed during Play, nothing is restored (the process is gone; temporary changes in `ProjectSettings` may also be left dirty).

**Relation to Reload Domain (on by default)**: exiting Play triggers a domain reload, and the static subscriptions this class registered during Play are lost with it,
so the "re-attach on EnteredEditMode" path may not get to run under default settings (`isolated_callbacks.json.restored_at`
may stay `null`). This does not affect this round's correctness: **the guarantee (no files written when this round exits Play) comes from the handlers having been removed before `ExitingPlayMode`**
— that event is dispatched within the Play domain, before the domain reload (otherwise callbacks registered during Play would never be called); after the reload, the old probes' own
`[InitializeOnLoad]` static constructors resubscribe (RuntimeProbe's `_armed` and EarPlayProbe's `_sb` are also reset by the reload),
which is equivalent to restoring. If the project has Reload Domain turned off, there is no reload, and this class's `OnPlayModeChanged` receives `EnteredEditMode` normally and re-attaches explicitly.

### Avatar resolution rules (criteria)

The face-tracking installer clones the avatar into a second root, so:

- Only **scene** objects whose name matches exactly are accepted (prefab assets and objects not in the scene are excluded);
- Candidates are deduplicated first (a candidate that is a descendant of another candidate is dropped);
- Only `activeInHierarchy` candidates are accepted;
- Exactly 1 → use it; 0 → error listing the paths of all same-named objects; ≥2 all active → **error** listing the paths,
  and a human must turn one off; the tool does not guess.

### GestureManager takeover

- Prefer reusing a module already in `GestureManager.ControlledAvatars`;
- Otherwise call `ModuleHelper.GetModuleFor(VRC_AvatarDescriptor)` + `GestureManager.SetModule(module)` via reflection
  — exactly the internal path GM itself takes when "opening the GestureManager Inspector in Play mode"
  (`Scripts/Editor/GestureManagerEditor.cs:81 TryInitialize` → `:97 Manager.SetModule(module)`);
  under automation nobody opens the Inspector, so we walk that path for it.
- Takeover succeeds → output `gm_controlled: true` / `driver: "gesture_manager"`;
  fails → `driver: "animator"`, and `warnings` states "ParameterDriver / LayerControl will not be simulated; conclusions must be downgraded".
- Along the way, GM's `ModuleSettings.simulateCulling` is temporarily turned off (the default prefab has 0, i.e. off; once on,
  GM sets every `renderer.enabled` to false based on the editor camera's distance to the avatar, and snapshots all become "invisible"), restored at the end.

### 3.1 Temporarily creating a GestureManager when the scene has none (task F, `gm_created_by_audit`)

In practice most client scenes have no GestureManager component at all (e.g.
`工程A/Assets/_Work/工程A.unity` component count = 0); T1 then falls back to
`driver=animator`, and ParameterDriver / LayerControl are not simulated. So in **Play mode** T1 automatically adds a temporary GM:

- **Trigger**: `ensure_gm=true` (default) + `FindManager()` finds no component in the scene + `Application.isPlaying`.
  **Not created in edit mode**, keeping the original fallback (T1 cannot run in edit mode anyway).
- **Created following GM's own fallback path**: `new GameObject("GestureManager").AddComponent<GestureManager>()`
  (source: `Scripts/Editor/GestureManagerEditor.cs:63-68 CreateAndPing`). GM's menu item
  `Tools/Gesture Manager Emulator` (`:43-49 AddNewEmulator`) normally uses
  `PrefabUtility.InstantiatePrefab(GestureManager.prefab)` (`:51-55`); that prefab contains only one GameObject named
  `GestureManager` + the GestureManager component (script GUID `2398979b1d0d84349abc5ee9f0571350`,
  i.e. `Scripts/Runtime/GestureManager.cs.meta`), with the fields of `settings` serialized on the component
  (in the prefab `cullingDistance: 5`, `initialPose: 0`, `simulateCulling: 0`, etc.), and no other components/fields.
  This tool follows the fallback path but renames it `__AvatarAudit_GM` with `hideFlags = HideFlags.DontSave`, so it does not pollute the scene/saves.
- **Why `SetModule` works right after attaching (no need to wait for Awake/OnEnable/Start/coroutines)**:
  `Scripts/Runtime/GestureManager.cs` has no `Awake`/`OnEnable`/`Start` anywhere; its only lifecycle hook is
  `OnDisable` (`:23`); when `AddComponent` returns, the component is already enabled and the object active. Real initialization happens in
  `SetModule` (`:67`) → `ModuleBase.Connect` (`Scripts/Runtime/Data/ModuleBase.cs:148-154`, registers the module in
  `ControlledAvatars` and calls `InitForAvatar`) → `ModuleVrc3.InitForAvatar`
  (`Scripts/Editor/Modules/Vrc3/ModuleVrc3.cs:181-311`), all completed synchronously (ending with `_playableGraph.Play()` /
  `Evaluate(0f)`), independent of frames. `settings` is a prefab-serialized field, null when newed up at runtime,
  so `AuditIO.EnsureSettings` supplies a default `ModuleSettings` instance as a fallback.
- **Output**: `states.json` gains a boolean field `gm_created_by_audit`; `gm_note` also starts with
  `gm_created_by_audit=true；`. A value of `false` means the scene's existing GM was used (or takeover failed).
- **Cleanup**: T1 `Cleanup()` calls `GmgBridge.DestroyAuditManager()`, **only when `_auditCreatedGo` was created by us**
  (idempotent); existing GM components in the scene are left alone. Side effect: the temporary GM is not left for a later T3 in the same Play session to reuse —
  this is an explicit requirement of task F; in a scene without GM, T3 has no GM to use anyway (it only calls `GetControlledModule` and never creates one).

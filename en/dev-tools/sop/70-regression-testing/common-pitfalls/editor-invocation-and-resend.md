> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/70_回归测试/常见坑/编辑器调用与重发.md)

> ← [70 · Common pitfalls](../common-pitfalls.md). Trigger: when running heavy jobs (builds, measurements, NDMF, renders) via `execute_code` / `execute_menu_item`, adding locks against resends, or when Unity crashes during a build.

# Editor invocation and resend (execute_code / menu / lock / build crash)

## Play entry points and blockers

**T1/T4 require Play; the full hand-off has not yet passed acceptance (verified against source 09-23, not actually run).** `AuditStateDriver`/`AuditMenuDump` are both `RequiresPlayMode=true`; the entry point is `AvatarAudit.AuditRunner.RunRequestFromMenu()` / `Tools/AvatarAudit/Run Request`, which reads `<工程>/Library/AvatarAudit/request.json`. `auto_play:true` only calls `EnterPlaymode()` and does not isolate preprocessing; `sequence` also depends on the editor frame pump.

- The existing batch method `AvatarAudit.AuditBatch.ExportInventory` only opens the scene, does the part inventory, and exits; it cannot run T1/T4. The launcher's `--batch` carries `-quit`; stuffing the above asynchronous menu methods directly into `--method` does not automatically give you a flow that waits for Play, collects results, and exits on failure.
- `PlayTest.LayerLogic` only tests the cat-ear layer of a fixed controller; `BakeTest.Run` only bakes NDMF; neither can substitute for full preprocessing plus T1/T4.
- **Blockers**: a full batch entry point, a reloadable built avatar with all dependencies, Play hook isolation, and evidence of "reload output → T4/T1 complete with no second preprocessing" — if any one is missing, record `blocked/未测` (not tested), and continue with request preparation and offline inventory. A source avatar with plugins disabled is still not a finished product; old `done`/Play reports cannot be repurposed as proof of passing under the new criteria.

### Prerequisites for running in a self-opened interactive Unity

The following procedure has yet to pass acceptance on a real project.

1. First complete this project's full preprocessing in batch mode in an isolated project, and save the success log, source revision, plugin versions, output path and root name. The output must be a reloadable scene/prefab with persistent dependencies — not just an in-memory clone or JSON; the menu, parameters, FX, meshes/materials must still resolve. NDMF's default `Packages/nadena.dev.ndmf/__Generated` is cleaned up on exiting Play; VRCFury also cleans temporary assets before entering Play. `ManualProcessAvatar` has a persistent directory but still only runs NDMF and does not complete the full SDK chain.
2. Only once there is no live Unity on the same project, start an interactive session yourself with `bash 开发工具/通用工具/unity_run.sh --project "<隔离测量工程>"`. Load the built output; the target root must be unique and active, and script compilation finished; record the original scene path / dirty flag, Play state, relevant settings and a snapshot of the output's dependencies. Do not take over a session the user is using; when there are unsaved user changes, do not reload or discard directly.
3. **Isolate preprocessing before entering Play — disabling NDMF alone is not enough.** Taking Project A's local NDMF 1.14.3 source as an example: save and idempotently set `nadena.dev.ndmf.config.Config.ApplyOnPlay = false`, then read it back; `ApplyOnBuild` is a separate switch — a full build should have it enabled, and disabling the build must not be used to dodge errors. The menu `Tools/NDM Framework/Apply on Play` is a toggle, so do not blindly resend it. VRCFury separately calls the full SDK chain via `PlayModeTrigger`, and its switch reads `EditorPrefs.GetBool("com.vrcfury.playMode", true)`; first save whether that key exists and its old value, then temporarily set it to false and read back. **EditorPrefs is configuration shared by the same user**, so you must rule out affecting other editor sessions; if you can't, switch to an isolated user configuration or record it as a blocker. Other emulators (especially Av3Emulator) and project-specific Play callbacks must each be verified as isolated too; the two switches above cannot guarantee the project has no other entry point.
4. Save the restore snapshot outside of the Play domain reload; after entering Play, read the switches back again and check the full editor log for no new preprocessing runs. The request must explicitly set `auto_play:false`; run T4 first, then generate T1 from its real parameters. If preprocessing is re-triggered, stop measuring and go to recovery; don't wait for an interactive build to "fill it in". `warmup_frames` only waits frames; it neither proves a full build nor blocks one.

### How to use the existing request samples

For the format see request §3 in [T1](../../../tools/audit/docs/state-driver-request.md) and [T4](../../../tools/audit/docs/menu-dump.md); old root names, parameters and sentinels must be rewritten for this round's output. Write the two below as **separate** request files, replacing them with the actual root name and a new absolute output directory for each; do not trigger if the prerequisites are not met.

```json
{"tool":"menu","avatar":"<已构建根名>","out":"<本轮T4绝对目录>","auto_play":false,"warmup_frames":10}
```

```json
{"tool":"state","avatar":"<已构建根名>","out":"<本轮T1绝对目录>","auto_play":false,"ensure_gm":true,"version_check":true,"reset":"declared","states":[{"id":"default","params":{}}]}
```

The default state is only an entry smoke test; it cannot replace full-state coverage and `reset:none` real sequences. After one trigger, poll each one's `status.json`; T1 needs `state=done`, a passing version stamp, and `states.json.gm_controlled=true` / `driver=gesture_manager`, and you must check the state count, read-back assertions and warnings; `driver=animator` cannot verify VRC parameter-driver interactions. For T4, check that the menu/descriptor/parameters exist, the warnings and undeclared parameters — don't just look at `done` (missing SDK fields can also write out an empty result). T1 parameter names are taken from T4 of the same output.

### The session must be restored at the end

Leave the report first, then exit your own Play normally; handle failures per the [environment recovery procedure](../../02-environment-and-manual-intervention/b850-linux-environment/memory-budget-and-concurrency.md). Restore from the snapshot the NDMF switches, the VRCFury EditorPrefs (if the key didn't exist originally, restore it to not existing), emulators/callbacks and any ProjectSettings changed this time, including `legacyClampBlendShapeWeights`; read each value back. T1 Cleanup keeps the final-state parameters and only restores the temporary GM/probe settings; it does not replace exiting Play. For read-only measurements, after confirming there are no unsaved user changes, reload the scene from disk and check `activeSelf`, `Renderer.enabled`, references and setting differences; temporary copies don't overwrite the source scene, and Play-derived settings are not committed into the project. After a restart, don't assume the disabled switches are still in effect.

## Resends and crashes

- `execute_code` timeouts get resent (DepCompiler Apply ran 4 times): long, non-idempotent operations go through "menu + request file". See [02](../../02-environment-and-manual-intervention.md) section 2-③.
  **⚠ Correction 2026-09-21: `execute_menu_item` gets resent too** (the Project B 80 texture tiering run actually executed **4 times**,
  with four `[Opt80Tex] 执行` lines in the log). So "going through the menu" is **not** a way to avoid resends, just a different entry point —
  the real requirement is that **the menu action itself is idempotent**. The texture-modifying part of that tool is idempotent (runs 2–4 reported "0 changed" and the code has
  an `if (apply && plans.Count > 0)` guard), so this resend **caused no damage**.
  > **Queryable question**: when this operation runs a second time, what will it write over the state it has **already finished**?
  > Especially "the logs/backups used for rollback" — those are exactly what a second run is most likely to wipe.
  **⚠ Addendum 2026-09-22: a file lock that is "deleted when done" doesn't stop resends.** The resent request **queues behind the Unity main thread**
  and only runs after the current round finishes — at that moment the lock has just been deleted by `finally`, so it brazenly runs a whole round again
  (Project B `ParamCost90` finished after 14 minutes, deleted the lock at 01:23:44, and a second round started right after; meanwhile every other `execute_code` timed out).
  **How to write it**: in `finally`, **refresh** the lock's timestamp instead of deleting it, so the cooldown window counts from "finished"; to rerun intentionally, manually `rm` the lock file first.
  > **Queryable question**: is my lock timed from the "start" time or the "end" time? Resends happen after the end.
  **⚠ Unity native crashes during builds are not a "which round" issue (corrected 09-22)**: two crashes at 01:31 and 01:57 on 09-22, the second being **the first round after a restart**.
  In the gdb dump the crashing thread is `UnityGfxDeviceW`: `VKWindow::Reshape → GfxDeviceVK::AdjustPrimarySwapChain → … → libnvidia-glcore`,
  i.e. **Vulkan rebuilds the swapchain when the window is resized and crashes inside the NVIDIA driver** (xrdp's X only attaches the iGPU; Vulkan runs on the dGPU and presents onto an iGPU window).
  "The third round always crashes" was a pattern I cobbled together from counts and has been overturned; for details see the graphics API section of [This machine (Linux) environment](../../02-environment-and-manual-intervention/b850-linux-environment.md).
  **Current practice (09-23)**: full builds and NDMF/VRCFury preprocessing go through `bash 开发工具/通用工具/unity_run.sh --project "<工程>" --batch --method <入口>`; see [Memory budget](../../02-environment-and-manual-intervention/b850-linux-environment/memory-budget-and-concurrency.md). `--project` is required, and `<入口>` must be a static method that really exists in this project and can run in batch mode. `delayCall` only applies to other measurements/renders that must be done in the editor; it makes the call return immediately, but you still need a request ID, a single-flight lock and a completion file to prevent resends, and it cannot eliminate build crashes.
  **⚠ Not just menus: any `execute_code` that might exceed ~20 s in a single call counts as a heavy job** (Project A crash, 09-22 04:43): DSH called
  `AvatarProcessor.ProcessAvatar(clone)` directly in `execute_code`; a single NDMF pass took 29–51 s, the request timed out and was resent, and the log showed **the same source running overlapped** (the report file was rewritten under the same name),
  followed by a crash on a `Baselib_ThreadLocalStorage` assertion → FMOD `AudioManager::systemCallback` → SIGSEGV in `profiler_begin` — **not the Vulkan Reshape stack**.
  > **Queryable question**: is it a full build/preprocessing? If yes, batch mode; otherwise only if it must be in the editor and exceeds 20 seconds, hang it on `delayCall`, write the result to a report, check the single-flight lock at the start, return immediately and then poll for the completion marker.
  Trade-off: add request de-duplication and status recording to reduce repeated execution; the task brief must name this item explicitly.
  Two compile/interception pitfalls inside `execute_code` (reported by DSH, 09-22): `Object` is ambiguous with `System.Object`, so always write `UnityEngine.Object`; `File.Delete`/`FileUtil.DeleteFileOrDirectory` get blocked by safety_checks, so deleting a lock file needs `safety_checks=false`.

- **While the editor is open, don't rewrite an open `.unity` from outside (even a single line)** (Project A froze twice, 09-22): Unity detects the change and reimports the scene, dragging along an NDMF preview proxy rebuild, after which the main thread stops responding, MCP returns `Command TCS timed out` repeatedly, SIGTERM does nothing and only SIGKILL works. To restore derived fields (such as `RenderSettings.m_IndirectSpecularColor`), change them in the editor and then save, or close the editor before editing the text.
  **Don't rely on another editor call to rerun a full build**: switch to batch mode; destroy the clone after measurement/persistence is complete.
  **Freeze criteria**: CPU ≈ 0, the `Library/ArtifactDB-lock` timestamp stops moving, MCP times out 3 times in a row ⇒ stop and report `CRASHED`; Claude then handles the fallback: SIGKILL → delete `Temp/UnityLockfile` and `~/.unity-mcp/unity-mcp-status-<哈希>.json` → reopen.

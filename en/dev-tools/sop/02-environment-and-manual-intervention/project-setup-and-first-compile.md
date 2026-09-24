> 🌐 English translation · [中文原文](../../../../开发工具/SOP/02_环境准备与人工介入/建工程与首轮编译.md)

> ← [02 · Environment preparation and manual intervention](../02-environment-and-manual-intervention.md)

# Creating a VCC Project and the First Compile

The problem this page solves: **creating a compilable VCC avatar project from scratch**, and how to fix the first compile of a new project, which is bound to fail.
Daily work in an existing project does not need this page.

---

## 1. Creating a project without the GUI (this machine (Linux) / Linux)

There is no official Linux version of VCC. On this machine (Linux) use **ALCOM** (GUI, `/usr/bin/alcom`) and **vrc-get** (CLI, `~/.local/bin/vrc-get`);
both share `~/.local/share/VRChatCreatorCompanion/` (`settings.json`, `Repos/` community sources, same structure as VCC).

**Easiest**: create from the Avatar template in the ALCOM UI (the template is built in), then go back to the command line to install packages.

**Pure command line** (⚠ written during the 2026-09-18 cleanup, **not yet fully tested on this machine (Linux)**; add criteria the first time it is used):

1. Copy the skeleton from an existing project that compiles: `ProjectSettings/`, `Packages/manifest.json`, `Packages/vpm-manifest.json`
   (do not copy `Assets/` and `Library/`)
2. Install packages at the frozen versions in `../../_工具链基准.md`: `vrc-get install <包 id> <版本> -p <工程>`,
   then `vrc-get resolve -p <工程>` to fill in locked dependencies. **Do not chase the latest** (see the version freeze in [20 · Asset inventory and import](../20-asset-inventory-and-import.md))
3. Write the project path into `userProjects` in `~/.local/share/VRChatCreatorCompanion/settings.json` so it shows up in ALCOM

**Post-condition criterion**: the number of `locked` entries in `vpm-manifest.json` == the number of VPM package directories under `Packages/`.

> In the old Windows machine (Windows) era, the practice was to copy `%LOCALAPPDATA%\VRChatCreatorCompanion\VRCTemplates\Avatar` and unpack offline from `Repos/*.zip`;
> on this machine (Linux) `Repos/` only contains source-list JSON with no package zip cache, so that route does not work.

### When Unity MCP is needed, copy the package URL exactly

```
com.coplaydev.unity-mcp: https://github.com/CoplayDev/unity-mcp.git?path=/MCPForUnity#v10.1.2
```

Write it into `Packages/manifest.json`. The subpath is `/MCPForUnity`; **do not write anything else from memory**.
Remove this line from the manifest before delivery.

⚠ **After adding a package to `Packages/`, Unity must be restarted.**
Refreshing assets and resolving packages are not enough — `packages-lock.json` will update,
but the package's dll will not appear in `Library/ScriptAssemblies/`. **The criterion is whether the dll exists, not the lock file.**

---

## 2. Criteria for launching Unity

Launch commands and graphical-session requirements are in [this machine (Linux) Linux environment](b850-linux-environment.md). On Linux just quote the whole path;
there is no Windows `Start-Process` space-splitting pitfall.

### Judging “is Unity really working”

**Watch whether `Library/` is growing, not whether the process is alive.**
Force-killing a batch instance leaves `Temp/UnityLockfile` behind; before the next open, confirm there is no Unity process and then delete it.

### Judging “did the compile really succeed”

**Check whether `Library/ScriptAssemblies/Assembly-CSharp-Editor.dll` exists and whether its timestamp is later than the source.**
Do not count `error CS` lines in `Editor.log` —
a brand-new project failing its first compile and succeeding in later rounds is normal; errors from both rounds are mixed in the log,
and judging by the log leads to repeated misjudgments.
⚠ This only holds for **your own scripts**: when an assembly with a vendor-supplied asmdef fails to compile, `Assembly-CSharp-Editor.dll` will still be new,
so separately check whether that assembly's own dll exists (the migration-acceptance practice: take the old machine's list of `*.csproj` names and check each against `Library/ScriptAssemblies/*.dll`).

---

## 3. Three pitfalls of a brand-new project's first compile

After bulk-importing third-party packages into a newly created project, the first compile almost always fails. Three known causes:

**① Missing SRP core.**
Some tools use `CommandBufferPool` (in `com.unity.render-pipelines.core`),
while the VCC template is the built-in pipeline without this package → dozens of CS0103 → directly triggers Safe Mode.
Just add `"com.unity.render-pipelines.core": "14.0.11"` to `Packages/manifest.json`;
**it does not switch the render pipeline** (that requires specifying a pipeline asset in Graphics).

**② `VRC_SDK_VRCSDK3` deadlock.**
Many scripts wrap `using VRC.SDK3.Avatars.Components;` in `#if VRC_SDK_VRCSDK3`,
and this macro is only written into Player Settings by the SDK **after the first successful compile** —
compile fails → macro undefined → more scripts fail to compile.
Manually add `Standalone: VRC_SDK_VRCSDK3` to `scriptingDefineSymbols` in `ProjectSettings/ProjectSettings.asset`
to break the deadlock.

**③ lilToon 2.x's editor assembly is `autoReferenced: false`.**
`Assembly-CSharp-Editor` cannot see `lilToonInspector`,
so third-party `CustomInspector.cs` files written in the old form all fail with CS0246.
Changing `autoReferenced` in that package's `*.asmdef` to true solves it at once,
but **this is a local change to a VPM package and reinstalling reverts it** — record it in the project notes.

---

## 4. Unpacking a `.unitypackage` does not need Unity

It is just a gzip tar; each asset is `<guid>/pathname` + `<guid>/asset` + `<guid>/asset.meta`.
Two streaming passes (first collect pathnames, then write to disk) restore it into `Assets/`, **with original GUIDs untouched**.

Safer than dragging folders in Unity (dragging a folder changes the GUID of the folder's `.meta`),
and entries can be excluded precisely.

Note: if the package **has no folder entries**, folder GUIDs will be newly generated by Unity —
the result is the same with the official import dialog; this is a problem of the package itself, not of the method.

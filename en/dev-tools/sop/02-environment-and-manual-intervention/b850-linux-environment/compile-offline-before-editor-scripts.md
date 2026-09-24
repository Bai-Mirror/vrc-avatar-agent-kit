> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/02_环境准备与人工介入/B850_Linux环境/改编辑器脚本先离线编译.md)

> ← [This machine (Linux) Linux environment](../b850-linux-environment.md) · [02 · Environment preparation](../../02-environment-and-manual-intervention.md)

# After Editing `Assets/Editor/*.cs`, Compile Offline Before Letting Unity Refresh

## Trigger moment

The moment you have finished writing or editing an editor script and are about to call `AssetDatabase.Refresh` / `refresh_unity`.

## Why

Once Unity fails to compile, it **pops up an `Enter Safe Mode?` modal dialog** that freezes the whole editor.
At that point MCP cannot get in (`No Unity Editor instances found` or timeout), and only a **human** can click the button —
a trivial error like a missing `using` drags the user in once. Measured 2026-09-21: `ParamCost90.cs` was missing
`using System.Collections.Generic;`, the user was blocked by the dialog, and work was interrupted.

## How

```bash
开发工具/通用工具/unity_csc.sh <工程根> [程序集名，默认 Assembly-CSharp-Editor]
```

Exit code 0 = pass; otherwise it prints `error CSxxxx` as-is. It does not enter Unity or trigger a domain reload; results in seconds.

## Key point: **use the project's own `.rsp`; do not hand-roll a `-r` list**

Every time Unity compiles, it writes the complete, correct reference set into
`Library/Bee/artifacts/*.dag/<assembly>.rsp`. What the script does is copy this rsp,
replace only `-out:`, and feed it to Unity's bundled Roslyn
(`Editor/Data/NetCoreRuntime/dotnet` + `Editor/Data/DotNetSdkRoslyn/csc.dll`,
with `-nostdlib -noconfig`).

Hand-rolled reference lists **will certainly hit** these two (both hit on 2026-09-21):

| Symptom | Cause |
|---|---|
| `CS0433 类型"MenuItem"同时存在于 UnityEditor 和 UnityEditor.CoreModule` (type “MenuItem” exists in both UnityEditor and UnityEditor.CoreModule) | The monolithic `Managed/UnityEditor.dll` and the modular `UnityEditor.CoreModule.dll` are both referenced |
| `CS0518 预定义类型"System.Object"未定义` / `CS0433 StringBuilder 同时存在于 mscorlib 和 netstandard` (predefined type “System.Object” is not defined / StringBuilder exists in both mscorlib and netstandard) | `mscorlib` / `netstandard` missing, duplicated, or version mismatched |

## Prerequisites and what to do if they are not met

- This rsp requires the project to **have been successfully compiled by Unity at least once**. For a brand-new project or when `Library/` has been cleared, the rsp cannot be found;
  the script reports “rsp not found” and exits 2 — in that case the only option is to let Unity compile once; do not fall back to hand-rolling references.
- The source-file list in the rsp is from **the last compile**. On the first run after adding a file, the new file is not in the list
  and will not be compiled. The script keeps the `Assets/` lines as-is; for newly added files, either let Unity compile once to refresh the rsp,
  or manually append a line with the new file's path to the temporary rsp.

## Add newlines when assembling an rsp yourself (09-23 tongue-piercing chain L6-A, moved from “Scripting pitfalls” on 2026-09-25)
After `cat refs.rsp >> my.rsp`, if the original file does not end with a newline, the next `-out:` gets glued onto the previous `-additionalfile:` line and is treated as a filename, and csc writes the dll/pdb under the default name into the **working directory (project root)**. When concatenating, `printf '\n'` after each segment; after running, check `git status` for extra `*.dll`/`*.pdb` in the project root.

## What to do if Safe Mode has already popped up

1. First compile offline to locate the error (Unity's own `Editor.log` also has `error CS`; `grep -nE "error CS[0-9]+"` is fastest);
2. Fix the file until the offline compile passes;
3. Then ask the user to click **Ignore** (not Enter Safe Mode) — the file is already fixed and Unity will recompile on its own;
   Safe Mode would halt importing of the rest of the project, adding an extra step to exit.

## Appendix: every VRChat SDK build rewrites a batch of texture `.meta` files

Measured twice on 2026-09-21, same shape: **`mipMapMode` in 285 vendor texture `.meta` files flipped en masse from 0 to 1**
(mip filter Box → Kaiser), and another 253 had an explicit default `platformSettings` block inserted. Nobody had touched these files.

⚠ **Attribution correction**: the first time I hit it, I judged it as “Unity re-imported everything after restarting from a crash”, **which was wrong**.
The timestamps the second time (289 `.meta` files and `ProjectSettings/GraphicsSettings.asset` all at 12:20)
were exactly the few minutes when the user clicked upload in the SDK panel — **the trigger is the SDK build itself**.
The crash case is also explained: two full preprocessing chains had just run before the crash.

The same build also changes these two ProjectSettings:
- `m_FogStripping: 0 → 1` in `GraphicsSettings.asset` (the SDK's `EnvConfig.SetFogSettings`, **does not revert on its own**)
- `lilToonSetting.json` (lilToon's `VRChatModule`, preprocessing chain order=100, strips unused shader features;
  in this case 48 off, 56 kept. **Check before panicking**: compare the stripped items against the `_UseXxx` switches of the avatar's actual materials;
  in this case `EMISSION_2ND` was stripped and both eye materials had `_UseEmission2nd: 0`, so no effect)

- **Checkable question**: after a build / upload, is there a swath of `.meta` changes in `git status`?
- **Criterion**: one import flipping the same field **in the same direction** across hundreds of vendor items is importer normalization, not anyone's setting.
  Compare against `git grep -h "<字段>:" HEAD -- <Assets>` to see the original distribution (in this case HEAD had 949 with 0 and only 2 with 1).
- **Handling**: revert them one by one with `git checkout`, then run a **plain** `AssetDatabase.Refresh()` (without `ForceUpdate`) to re-verify
  whether they get changed back again. In this case 0 were changed back on re-verification.
- **Trade-off**: **always revert** that batch of `.meta` — real optimizations like texture tiering are mixed with this kind of noise in the same batch of files,
  making the delivery diff unreadable and making it impossible to prove “the texture settings the client gets are exactly the ones we tuned”.
  The two ProjectSettings are **committed as-is** (reverting them just gets them changed back on the next build),
  with only `m_FogStripping` recorded as a to-do: change it back to 0 after the last build, then package.
- ⚠ **Before reverting, check whether anything real is mixed in**: the same batch of changes may include the
  `blueprintId` written back by a successful upload (in this case the face-tracking root got `avtr_…`). That is a real result; do not checkout it away along with the rest.

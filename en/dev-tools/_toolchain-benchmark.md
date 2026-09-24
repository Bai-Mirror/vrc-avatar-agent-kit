> 🌐 English translation · [中文原文](../../开发工具/_工具链基准.md)

# Toolchain Baseline (VPM package versions)

> **When taking a new order, copy this page, not the previous order's `建档.md`.**
> The previous order's setup record says “what that order used at the time”; this page records “why these versions”.
> Last checked: **2026-09-06** (when Project C started)

## Conclusion: **frozen**, don't chase the latest

It's not about playing safe — **the dependency graph itself leaves no room for choice** (see the ceiling below).
When each order starts, copy this whole table into the project's `vpm-manifest.json`;
**no upgrades while an order is in progress**.

## Current baseline (checked 2026-09-06, all installable offline)

| Package | Version | Newer version in cache? |
|---|---|---|
| `com.vrchat.avatars` / `com.vrchat.base` (SDK) | **3.10.4** | None — **already the newest in cache** |
| `jp.lilxyzw.liltoon` | 2.3.4 | None |
| `dev.vrlabs.av3manager` | 2.1.2 | None |
| `world.anlabo.mdnailtool` | 0.10.61 | None |
| `de.thryrallo.vrc.avatar-performance-tools` | 1.3.7 | None |
| `gogoloco` | 1.8.6 | None |
| `com.triturbo.face-blendshape-fix` | 0.1.3 | None |
| `vrchat.blackstartx.gesture-manager` | 3.9.9 | None (`3.9.9-pr6` is a pre-release and doesn't count) |
| `com.vrchat.core.vpm-resolver` | 0.1.29 | — |
| `nadena.dev.modular-avatar` | 1.18.1 | ↑ 1.18.7 |
| `nadena.dev.ndmf` | 1.14.3 | ↑ 1.14.8 |
| `com.anatawa12.avatar-optimizer` | 1.9.16 | ↑ 1.9.18 |
| `com.vrcfury.vrcfury` | 1.1414.0 | ↑ 1.1426.0 |
| `io.github.azukimochi.light-limit-changer` | 2.12.3 | ↑ 2.13.0 |

Implicit dependencies (no need to fill in manually, the resolver brings them itself): `com.vrchat.base`, `jp.lilxyzw.avatar-utils` 2.1.2.
**16 `Packages/` directories = the 14 named + these 2.**

## ⚠ There is a baseline on the UPM side too — this page originally only covered VPM; added 2026-09-06

Besides VPM (`Packages/vpm-manifest.json`), `Packages/manifest.json` also has things that must be locked.
**Missing it causes compilation to fail with 72 errors right after importing the Triturbo FT framework**, and the error messages
(a pile of `FbxManager` / `FbxScene` not found) don't reveal the root cause.

| UPM package | Version | When it's required | Available offline |
|---|---|---|---|
| `com.autodesk.fbx` | **4.2.1** | Whenever **Triturbo BlendShare** is installed (comes with the FT framework zip) | ✅ in the UPM cache |
| `com.coplaydev.unity-mcp` | git URL | When you want to drive the editor with UnityMCP | Needs network |

### Pitfall: the vendor unpacks the package loose into `Assets/Packages/`, and UPM won't resolve its dependencies

The `package.json` of `com.triturbo.blendshare 1.0.3` states explicitly `dependencies: {com.autodesk.fbx: 4.2.1}`.
In the previous order (Project A) it was a proper UPM package installed under `Packages/`, and UPM **automatically** pulled in the FBX SDK (depth 1).
In this order it was **unpacked loose into `Assets/Packages/`** from a unitypackage — that's the location the vendor specified in the unitypackage,
but **UPM doesn't read any package.json under `Assets/`**, so the dependency will never be resolved automatically.

**Criterion**: after installing the Triturbo FT framework, run batchmode once;
if the timestamp of `Library/ScriptAssemblies/Assembly-CSharp-Editor.dll` didn't update = compilation failed.
**Symptom signature**: all errors are types not found in the `Autodesk.Fbx` namespace.
**Fix**: add `"com.autodesk.fbx": "4.2.1"` to `Packages/manifest.json`; don't modify the vendor source.

> Incidentally: BlendShare v1.0.3's `BlendShapeDataSOEditor.cs:235` **ships with a vendor syntax error — a missing semicolon**,
> in the `#if !ENABLE_FBX_SDK` branch. Once the FBX SDK is installed that branch doesn't take part in compilation, so it's normally not exposed.
> In this order the semicolon was added and the original backed up to `_厂商源码备份/` (outside `Assets/`, so Unity won't index it).

### ⚠ Before delivery, `com.coplaydev.unity-mcp` must be removed from `manifest.json`

It's a **git URL dependency**; if the client has no network / the repo changes its tag, the project won't open —
exactly the kind of dependency that made 4 projects unopenable in memory `archive-dependency-reproducibility`.
It's fine during development; **delete it before packaging**.

## The ceiling: three packages together pin the SDK below 3.11

This is the hardest reason for “not chasing the latest” — read directly from the `dependencies` in each package's `locked` section:

| Package | SDK requirement |
|---|---|
| `com.anatawa12.avatar-optimizer` | `>=3.7.0 **<3.11.0**` |
| `dev.vrlabs.av3manager` | `**3.2 - 3.10**` |
| `vrchat.blackstartx.gesture-manager` | `>=3.10.4 **< 3.11.X**` |

**Upgrading the SDK to 3.11 would break all three at once.** And the SDK is currently sitting right at the 3.10.4 ceiling,
so “use the latest SDK” is currently an **empty option**, not a trade-off.

NDMF side: `modular-avatar` needs `>=1.14.3 <2.0.0-a`, `LLC` needs `^1.9.0`, `AAO` needs `>=1.8.0 <2.0.0`
— upgrading NDMF within 1.x is safe, but there's no reason to upgrade it on its own.

## When to re-check: **by event, not by calendar**

| Trigger | How you find out |
|---|---|
| ① A VRChat game update forces an SDK upgrade | **Upload rejection** is the hard signal; don't guess |
| ② A bug in some package directly blocks the workflow | e.g. NDMF bake aborts, MA fitting stops working, AAO optimization errors |
| ③ A new asset pack declares it requires a higher version | Vendor README / `vpmDependencies` in package.json |
| ④ **The gap after an order is delivered** | Routine; upgrading costs the least at this point |

**Never upgrade while an order is in progress.** The reason is SOP hard gate ② “land only one change at a time” —
if the toolchain and the assets change at the same time, a problem can't be attributed, and you can only roll everything back and start over.

## What happens on the client side after delivery

The `locked` section of `vpm-manifest.json` **is the freeze**. When the client opens the project in their own VCC
they may be prompted about updates, **but nothing upgrades unless they click**. We can't control whether they click,
so the delivery notes should include a line: “The project has locked versions; upgrading is not recommended unless you run into problems.”

## Look at these together at the next check

Currently known upgradable but **not upgraded this round** (kept as the candidate set for the next baseline):
`modular-avatar 1.18.1→1.18.7` · `ndmf 1.14.3→1.14.8` · `avatar-optimizer 1.9.16→1.9.18` ·
`vrcfury 1.1414.0→1.1426.0` · `light-limit-changer 2.12.3→2.13.0`

How to check: run `开发工具/通用工具/vpm_baseline_check.py` (compares the VCC `Repos/*.json` cache with the project's locked section).

## Related

- Dependencies must be written as VPM version numbers; `file:` / `git#master` will make archives unopenable → memory `archive-dependency-reproducibility`
- How to create projects and install packages offline → memory `vcc-project-scaffold-and-import`, SOP `02_环境准备与人工介入/建工程与首轮编译.md`

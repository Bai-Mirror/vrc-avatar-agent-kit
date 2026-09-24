> 🌐 English translation · [中文原文](<../../../../开发工具/SOP/60_菜单与动画层/VRCFury参数压缩.md>)

> ← [60 · Menu and animator layers](../60-menu-and-animation-layers.md) · [00 · Master table](../00-overview.md)

# VRCFury parameter compression: 256 bits is not a hard wall (read from VRCFury 1.1414.0 source, 2026-09-21)

**Trigger**: `CalcTotalCost()` approaches or exceeds 256, before considering “cutting features”.

## When it kicks in

`Editor-Avatars/Service/Compressor/ParameterCompressorSolverService.cs` starts with:

```csharp
var originalCost = paramz.CalcTotalCost();
if (originalCost <= maxCost) return new ParameterCompressorSolverOutput();   // within the limit → not a single byte compressed
```

→ **A number like 254/256 is the real uncompressed cost, not “already compressed”**.
The compression hook is `VrcfAvatarPreprocessor` (`order = int.MaxValue - 100`), running in the SDK preprocessing stage,
**not inside NDMF `ProcessAvatar`** — so the cost read from a manual NDMF build in the editor is always pre-compression.

## How it compresses

It replaces “synced parameters bound to menu Toggle / RadialPuppet / TwoAxis / FourAxis” with
a small number of **time-multiplexed slots**, broadcast in turn:

```
finalCost    = original cost − Σ(cost of compressed parameters) + numeric slots×8 + bool slots×1 + batch index bits
batch count  = max(ceil(numeric count/numeric slots), ceil(bool count/bool slots))
index bits   = ceil(log2(batch count + 1))
one sync round = batch count × (BATCH_TIME 0.1 s + 1/60 s) ≈ batch count × 0.117 s
```

`OptimizationDecision.Optimize()` **keeps adding slots until all 256 are used**,
in order to shorten sync time — so the post-compression cost always hugs 255~256,
and **“how many bits are left after compression” is a meaningless number**.

## What can't be compressed (this is the real budget)

The solver excludes from candidates: parameters the controller doesn't use at all, Contact / PhysBone / VRCRaycast automatic parameters,
those bound only to Button / SubMenu, and those neither in the menu nor driven and not prefixed `FT/` (OSC-only).
Only what remains is compressible.

> **Checkable question**: of my N bits, how many are **bound to menu toggles/radials**?
> Only that part can be compressed. **The sum of the uncompressible part + 9 + index bits = this model's real hard floor.**

## A measurement (Project B_Milfy, 2026-09-21)

| Item | Value |
|---|---|
| Synced parameters | 114 = **254 bit** |
| Of which compressible | 93 (12 numeric + 81 bool) = 177 bit |
| **Uncompressible hard cost** | **77 bit** |
| Maximum compression floor | 77 + 8 + 1 + 7 = **93 / 256** |

With the scheme VRCFury actually picks (slots filled up):

| Added | Original | Compressed | Batches | One sync round |
|---|---|---|---|---|
| None | 254 | 255 | 1 | 0.12 s |
| +10 menu toggles | 264 | 256 | 2 | 0.23 s |
| +60 menu toggles | 314 | 256 | 2 | 0.23 s |
| +20 menu radials | 414 | 256 | 2 | 0.23 s |

## ⚠ This does not hold for **face-tracking parameters**

Face-tracking (VRCFaceTracking / Triturbo) parameters are driven by OSC and **not bound to any menu control**,
while VRCFury compression only takes “synced parameters bound to Toggles/radials” — so face-tracking parameters are **entirely uncompressible**,
and every synced parameter added is a 1:1 hard cost.

Project B_Milfy measured (two roots of the same project):

| | Non-FT version | Face-tracking version |
|---|---|---|
| Sync cost | 254 bit | **398 bit** |
| Of which `FT/` prefix | — | 110 = **138 bit** (only 1 bound to the menu) |
| **Uncompressible hard cost** | 77 | **208** |
| Maximum compression floor | 93/256 | **224/256** (still transmittable) |
| VRCFury actual choice / one sync round | 255/256 / 0.12 s | 256/256 / **0.58 s** |

> **Checkable question**: can the batch of parameters I'm adding **be attached to menu controls**?
> If yes → VRCFury can absorb them, sync just gets slower; if no (OSC-driven, Contact, PhysBone) → 1:1 against the budget.
> Trade-off: before installing face tracking, compute “hard cost + face-tracking parameters” once; don't wait for the upload error.

**Trade-off**: at design time, don't cut features for 256 — as long as new parameters are **menu-bound synced parameters**,
VRCFury can absorb them, at the cost of switching latency. Only come back to free up space when upload actually errors,
and when freeing, prioritize the 77 bits: change parameters only you see to `networkSynced=false` (local parameters don't count),
and delete synced parameters the controller doesn't use at all.

**The compression switch under Tools → VRCFury →** has three settings (`CompressorMenuItem`):
`Compress` (default, auto-compress) / `Ask` (pop-up prompt) / `Fail` (fail outright). The default is fine.

## Measuring the true value requires running the full SDK preprocessing chain (measured on Project B, 2026-09-21)

The compressor hangs off `VF.Hooks.ParameterCompressorHook`, `callbackOrder = int.MaxValue-100 = 2147483547`;
it's an `IVRCSDKPreprocessAvatarCallback`, **not inside NDMF's `AvatarProcessor.ProcessAvatar`**.

- Running only NDMF measures the **pre-compression** number. Project B face-tracking root: NDMF-only measured **398**, the full chain **256**. (After the 09-22 split, outfit roots A/B likewise: NDMF-only 345/324, full chain 256/256.) **The pre-upload gate report must list both numbers side by side and mark which one is the upload criterion**; checkable question: was this `CalcTotalCost()` read before or after compression?
- You also **can't** use the `VRCExpressionParameters` attached to the descriptor in the project as the criterion — that only has the hand-written ones
  (22 entries / cost 99 on Project B); the real one or two hundred are assembled at build time by MA MenuInstaller + the face-tracking package.
- Correct method: `Instantiate` a clone → run every `IVRCSDKPreprocessAvatarCallback` **one by one** in `callbackOrder` order
  (don't call `VRCBuildPipelineCallbacks.OnPreprocessAvatar` as a whole; it only returns a bool,
  and “who rejected it, and whether the compressor ran before the rejection” is all invisible) → read `expressionParameters.CalcTotalCost()` of the descriptor on the clone.
- **256/256 is not a cliff**: the compressor's algorithm grows slots until 256 is filled, so “exactly 256” is its normal output.

⚠ Menu items that run heavy work like this must carry their own file lock: MCP's `execute_menu_item` resends on timeout;
measured: one build-measurement menu item was resent and ran three times, Unity RSS grew from 3 GB to 14 GB, and it finally crashed with `Exiting early due to double fault`.
The lock must **refresh its timestamp when done** rather than be deleted — the resend queues behind the main thread and executes right after the lock is deleted (see [70 Common pitfalls](../70-regression-testing/common-pitfalls.md)).

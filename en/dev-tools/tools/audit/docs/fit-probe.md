> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/fit-probe.md)

# T2 Fit Probe AuditFitProbe · Deployment, Dispatch, Requests <!-- nav -->

> Formerly: T2 (originally `审查/README_T2.md`) page header / §1–§3. § numbers follow the original; for cross-page § references, look them up in the [document index](../README.md). <!-- nav -->
> Next: [T2 Fit probe · algorithm and criteria (1–6)](fit-probe-algorithm.md) <!-- nav -->

# T2 · Fit Probe `AuditFitProbe` — Deployment, Conventions and Acceptance Self-Check

> For the file header's `【项目沉淀】` (project lessons), see `AuditFitProbe.cs`. This page only covers **how to deploy, how to send requests, what the output looks like, and how to self-check**.
> Design basis: the T2 section of `_长程任务_20260918/审查工具设计.md` + `派工/E_审查工具T2.md`.
> This round only writes code and doesn't open Unity; runtime behavior is compiled/first-run checked by Claude in the Project A project (see section 10).
>
> **v3 (2026-09-18, two corrections measured on Project A)**:
> 1. **Coverage scope**: body vertices only count toward `covered`/`pierced` for “clothing whose own skinning covers that region”; other hits are recorded as
>    `out_of_scope`. — Fixes the `sailor` top falsely reporting the hands (cuff geometry within the 25 mm range) as pierced.
> 2. **Foot-specific checks**: changed from “pick the one piece of clothing with the most coverage per foot” to “output separately for each foot × each piece of clothing covering that foot”,
>    and classify clothing as `footwear` (shoes) / `legwear` (socks) / `other`. — Fixes `feet` picking `stocking` (socks) and then measuring
>    “sole to shoe insole”.
> Details in §4.6 and item 7 of §4; regression checklist in §9.5.

---

## 1. Deployment

Source directory: `开发工具/通用工具/审查/` (after T-09, `.cs/.shader` are in `审查/unity/Editor/`). When auditing a project,
always use `perception/sync_audit.py` (see `README.md` §1): it lays `审查/unity/` out into
`<工程>/Assets/AvatarAudit/` (`Library/` isn't in version control and isn't imported; after auditing, it's deleted along with delivery cleanup):

```
AuditIO.cs            # Common layer: hand-written JSON, status.json, menu entry, multi-frame state machine pump, IAuditTool
AuditStateDriver.cs   # T1
AuditTurntable.cs     # T3
AuditFitProbe.cs      # ← this file (T2)
README.md             # T1/T3 overall description (produced by tool C)
README_T2.md          # ← this page
```

`AuditFitProbe.cs` depends only on `UnityEngine` / `Unity.Collections` / `Unity.Jobs` (the latter two are UnityEngine's
built-in `NativeArray`/`JobHandle`, **no extra packages needed**), and doesn't depend on VRChat / MA types; for the coupling surface with AuditIO see section 2.

---

## 2. Dispatch to add in AuditIO (one line)

When this round started, `AuditIO.cs` already existed with a dispatch table (produced by tool C); its architecture is `IAuditTool` + a multi-frame pump.
So T2 **implements `IAuditTool`** and is dispatched by AuditIO the same way as T1/T3. Add one line to the dispatch chain in `AuditRunner.StartFromJson`
(currently around lines 1060~1062 of `AuditIO.cs`):

```csharp
if (toolId == "state") tool = new AuditStateDriver();
else if (toolId == "turntable") tool = new AuditTurntable();
else if (toolId == "fit") tool = new AuditFitProbe();          // ← add only this line
else { Debug.LogError("[AvatarAudit] 未知 tool: " + toolId + "（支持 state / turntable / fit）"); return; }
```

The interface T2 implements (also written in the header comment of `AuditFitProbe.cs`):

```csharp
namespace AvatarAudit
public sealed class AuditFitProbe : IAuditTool
{
    string ToolId                { get { return "fit"; } }
    bool   RequiresPlayMode      { get { return true; } }   // states set by T1 only exist in Play; and only Play uses batching
    int    DefaultTimeoutSeconds { get { return 1800; } }
    void   Begin(AuditContext ctx);   // runs everything synchronously: parse request → bake → rays → write geo_<state_id>.json
    bool   Tick();                    // always returns true (Begin already did everything; wrap up next frame)
    void   Cleanup();                 // idempotent fallback: restore temporary changes, destroy temporary objects
}
```

**Why everything is done in Begin**: T2 is essentially a batch of ray computations with no need to “wait N frames”; internally `Run` uses
`RaycastCommand.ScheduleBatch` to submit everything at once and then `Complete()`. Large projects block the main thread for several to a dozen-plus seconds, which is expected.
`Tick()` is always true, so AuditIO's pump ends on the next frame.

**Precondition**: T2 measures the “current pose”. First have T1 set the state and **stay in Play mode**, then send the T2 request
(use `state_id` to label which state). T2 itself **doesn't set any Animator parameters**. `RequiresPlayMode=true`;
outside Play mode AuditIO reports an error directly (you can use the request field `auto_play:true` to have AuditIO enter Play first).

Reused AuditIO common components: `AuditAvatar.Resolve` (same-name multiple-root convention consistent with T1/T3), `AuditJson`/`JsonObject`
(JSON output, key order = insertion order, deterministic), `AuditStatus` (status.json and audit.log), `AuditUtil`
(`RelPath` / `ScenePath` / `SafeFileName`), `AuditContext.Warn` (collects warnings and writes them into the result).

---

## 3. Request JSON

```json
{"tool":"fit","avatar":"<头像根名>","out":"/abs/path","state_id":"default",
 "body":"auto",
 "exclude_name_regex":"(?i)(hair|face|eye|lash|tooth|tongue|head|halo|particle|nail|avatarhight|tail|ear)",
 "include_only":null,
 "cover_mm":25, "pierce_mm":15, "min_depth_mm":1.0,
 "region_min_share":0.02,
 "foot":{"enabled":true,"probe_mm":40,"sole_min_mm":4,
         "footwear":["kaguya_cloth/loafer"],"legwear":["kaguya_cloth/stocking"]},
 "perturb":null,
 "hide":null,
 "markers_top":200}
```

| Field | Default | Meaning |
|---|---|---|
| `tool` | Required | Must be `"fit"`. |
| `avatar` | Required | Avatar root GameObject name. Goes through `AuditAvatar.Resolve`: when face tracking clones produce two same-name roots that are both active, it errors and lists the paths. |
| `out` | Required | Output directory (absolute path). |
| `state_id` | `default` | Only affects the output file name `geo_<state_id>.json` and the `state_id` field. |
| `body` | `auto` | `auto` or the body mesh's hierarchy path relative to the avatar root (a full scene path is also accepted). `auto` rules in item 1 of section 4. |
| `exclude_name_regex` | See above | Excludes clothing candidates by **GameObject leaf name**. v2's default additionally excludes `nail`/`avatarhight`/`tail`/`ear`. |
| `include_only` | `null` | New in v2: regex; **only tests** clothing whose leaf name matches (filtered after `exclude_name_regex`); `null`/omitted means no limit. |
| `cover_mm` | 25 | Outward ray length; `<=0` means use the default. |
| `pierce_mm` | 15 | Inward ray length; `<=0` means use the default. Also the baseline for `depth_saturated` (see section 4.5). |
| `min_depth_mm` | 1.0 | Pierce depths below this aren't counted; `<=0` means use the default (to accept everything, use `0.001`). |
| `region_min_share` | 0.02 | **v3**: only when the share of clothing vertices whose “main bone maps to a region” reaches this is the clothing considered to cover that region. Both `0.02` and `2` mean 2%; invalid values fall back to 0.02. See §4.6. |
| `foot` | On if omitted | Write `{"enabled":false}` to turn it off; no `foot` key or `null` both mean on, with `probe_mm=40`. |
| `foot.probe_mm` | 40 | Length of the rays above/below the sole; `<=0` means 40. |
| `foot.sole_min_mm` | 4 | **v3**: **thickness** below the sole ≥ this → `footwear`; can also be written as top-level `sole_min_mm` (the one inside `foot` takes precedence); `<=0` means 4. |
| `foot.footwear` | `[]` | **v3**: explicit path list of shoes (matching full path relative to the avatar root or leaf name); classification basis recorded as `request`, highest priority. |
| `foot.legwear` | `[]` | **v3**: explicit path list of socks, same as above. |
| `perturb` | null | Self-check: `{"renderer":"<路径>","blendshape":"<名>","weight":100}`, temporarily sets a blend shape before baking. |
| `hide` | null | Self-check: `"<衣物渲染器路径>"`, temporarily `enabled=false` before baking. |
| `markers_top` | 200 | Output the N deepest pierce points. |


> `params` field: the output `params` is exactly your request object (embedded verbatim via AuditIO's `JsonObject`),
> with field order matching the request; because the `AuditJson` parser doesn't accept comments, the request file must be **valid JSON** (don't copy
> `//` comments from examples in this document).

---

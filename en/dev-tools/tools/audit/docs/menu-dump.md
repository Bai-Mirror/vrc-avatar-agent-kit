> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/menu-dump.md)

# T4 Post-build menu tree and parameter export AuditMenuDump · deployment, requests, behavior <!-- nav -->

> Former name: T4 (originally `审查/README_T4.md`) page header / §1–§4. § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Next page: [T4 menu export · output fields](menu-dump-output.md) <!-- nav -->

# T4 · Post-build menu tree and parameter export `AuditMenuDump` — deployment, fields, and acceptance self-check

> For the file header [project notes], see `AuditMenuDump.cs`. This page only covers **how to deploy, how to send requests, what the output looks like, what the fields mean, known limitations, and how to self-check**.
> Design basis: the first T4 item in `_长程任务_20260918/审查工具设计.md` ("automatically list the controllable parameters and discrete values from the baked `VRCExpressionParameters`
> and the menu structure") + dispatch `L`.
> This round **only writes code; it does not open Unity or call MCP**; runtime behavior is checked by Claude by compiling / first-running inside the Project A project (see section 8).

---

## 1. Deployment

Source directory: `开发工具/通用工具/审查/` (after T-09 the `.cs/.shader` files are in `审查/unity/Editor/`). When auditing a project,
always use `perception/sync_audit.py` (see `README.md` §1): it lays `审查/unity/` out into
`<工程>/Assets/AvatarAudit/` (`Library/` does not go into version control; delete it during delivery cleanup after the audit):

```
AuditIO.cs            # Shared layer: JSON, status.json, menu entry, multi-frame pump, IAuditTool (**do not touch** this round)
AuditMenuDump.cs      # ← this file (T4)
AuditStateDriver.cs   # T1 (used when setting parameters per menu combination)
README_T4.md          # ← this page
```

`AuditMenuDump.cs` depends only on `UnityEngine` / `UnityEditor` and the shared parts of `AuditIO.cs`;
it **does not reference VRChat SDK types directly** (everything is via reflection), so a project without the SDK / with a different SDK version only degrades to writing warnings.

---

## 2. The dispatch line AuditIO needs (one line, added by Claude)

The current dispatch chain in `AuditIO.cs` (around lines 1418~1421):

```csharp
if (toolId == "state") tool = new AuditStateDriver();
else if (toolId == "turntable") tool = new AuditTurntable();
else if (toolId == "fit") tool = new AuditFitProbe();
else { Debug.LogError("[AvatarAudit] 未知 tool: " + toolId + "（支持 state / turntable / fit）"); return; }
```

Change it to:

```csharp
if (toolId == "state") tool = new AuditStateDriver();
else if (toolId == "turntable") tool = new AuditTurntable();
else if (toolId == "fit") tool = new AuditFitProbe();
else if (toolId == "menu") tool = AuditMenuDump.Create();      // ← add only this line
else { Debug.LogError("[AvatarAudit] 未知 tool: " + toolId + "（支持 state / turntable / fit / menu）"); return; }
```

The interface this class implements:

```csharp
namespace AvatarAudit
public sealed class AuditMenuDump : IAuditTool
{
    public static IAuditTool Create();                 // static entry point (also noted in the file header)
    string ToolId                { get { return "menu"; } }
    bool   RequiresPlayMode      { get { return true; } }   // the built menu only exists in Play
    int    DefaultTimeoutSeconds { get { return 300; } }
    void   Begin(AuditContext ctx);   // parse request + soft-resolve the avatar (does not throw on failure; logs a warning)
    bool   Tick();                    // wait warmup_frames frames → read everything once + write 3 outputs → done
    void   Cleanup();                 // read-only tool, no temporary changes, no-op (idempotent)
}
```

**Why wait `warmup_frames` frames before reading**: NDMF's Apply on Play runs in `AvatarActivator.Awake`
(`nadena.dev.ndmf/Runtime/ApplyOnPlayGlobalActivator.cs:186-191`, `DefaultExecutionOrder -9995`),
while AuditIO may call `Begin` already in the `EnteredPlayMode` callback. Waiting the default 10 frames so the build has fully landed before reading is the safest;
the request field `warmup_frames` is adjustable (set 0 = don't wait).

**Precondition**: Play mode must be entered first (`RequiresPlayMode=true`; outside Play, AuditIO reports an error directly;
you can add `"auto_play": true` to the request to have AuditIO enter Play first and then start automatically).

---

## 3. Request JSON

```json
{"tool":"menu","avatar":"<头像根名>","out":"/abs/path",
 "warmup_frames":10,
 "root_label":"顶层",
 "max_depth":20,
 "max_controls":5000}
```

| Field | Default | Meaning |
|---|---|---|
| `tool` | required | Must be `"menu"`. |
| `avatar` | required | Avatar root GameObject name. Goes through `AuditAvatar.Resolve`: when face tracking clones produce two same-named roots that are both active, it errors and lists the paths. |
| `out` | required | Output directory (absolute path). `menu_tree.json` / `params.json` / `menu_tree.md` are written here. |
| `warmup_frames` | 10 | How many frames to wait after entering Play before reading (waiting for the NDMF/MA build to land). `0` = read immediately. |
| `root_label` | `顶层` | Root prefix of menu paths. |
| `max_depth` | 20 | Upper limit on submenu recursion depth; exceeding it logs a warning and stops. |
| `max_controls` | 5000 | Upper limit on total control count; exceeding it logs a warning and stops. |

---

## 4. Behavior

1. Use `AuditAvatar.Resolve` to find the active avatar root (same convention as T1/T3).
2. Read `VRCAvatarDescriptor` via reflection:
   - `expressionsMenu` (`VRCExpressionsMenu`) → recursively walk `controls`; cycle prevention **deduplicates by instance ID**
     (cycles, as well as the same submenu shared by multiple controls, are expanded only once and a warning is logged);
   - `expressionParameters` (`VRCExpressionParameters`) → parameter table
     `name / valueType / defaultValue / saved / networkSynced`;
   - `baseAnimationLayers` → the parameter table of each layer's `animatorController`.
3. Output for each control: `path` (`顶层/子菜单名/控件名`), `type` (**the enum name + integer value obtained by SDK reflection**),
   `parameter_name`, `value`, `sub_parameters[].name`, `labels`.
4. For each parameter, aggregate "the values that appeared in the menu" and "suggested values", plus the paths of the controls that reference it.
5. Mark two set differences:
   - `params_not_in_menu`: parameters present in controllers but not in the menu;
   - `menu_params_undeclared`: parameters present in the menu but not in `expressionParameters`
     (in VRChat these are not synced; menu operations have no effect or are local only).
6. Write `menu_tree.json` / `params.json` / `menu_tree.md`; when a type/field can't be read, only write a warning, don't throw.

**Where warnings go**: `ctx.Warn(...)` appends each warning to `out/audit.log`, and it also goes into
the `warnings` arrays in both `menu_tree.json` and `params.json`. `status.json` is managed centrally by AuditIO
(it only holds `state` / `progress` / `message`); this tool does not push warnings into it separately. For details, check `audit.log`
and the `warnings` of the two JSON files.

---

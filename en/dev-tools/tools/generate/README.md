> 🌐 English translation · [中文原文](../../../../开发工具/通用工具/生成/README.md)

# `生成/` — dependency compiler (T-06)

This directory contains only three `.cs` files, three layers of the same thing: **read the declaration → compute the plan → materialize writers**.

```
decl.json ──DeclJson.LoadFile──▶ DeclDoc ──DepPlan.Build──▶ DepPlanResult ──DepCompiler.Execute──▶ scene/controller
   (read-only data model)            `DeclJson.cs`            (pure plan, runs offline)  `DepPlan.cs`        (Unity editor)    `DepCompiler.cs`
```

The key layering constraint: `DeclJson.cs` and `DepPlan.cs` **do not `using UnityEditor / UnityEngine`** (`DeclJson.cs:6-7`),
so they can be compiled offline with Mono csc to run the plan standalone; only `DepCompiler.cs` references MA/Unity and must run in the editor.
Design source: `_长程任务_20260918/感知机制研究/04_第一期开工清单.md` T-06.

---

## DeclJson.cs — read-only data model for `decl.json`

**What it does**: reads the declaration JSON produced by `decl_validate.py` into typed objects (`DeclDoc` /
`DeclAvatar` / `DeclMenu` / `DeclControl` / `DeclSlot` / `DeclOutfit` / `DeclObject` /
`DeclToggle` / `DeclPart` / `DeclTarget` / `DeclCase` / `DeclDep`, see `DeclJson.cs:20,234-317`).
Missing fields always degrade to default values without throwing — the declaration is produced by another tool, and the compiler would rather do one item less than fail the whole batch (`DeclJson.cs:9-10`).

**Input/output**: input `<工程>/_感知/decl.json` (`schema=perception/0.2`); output is the in-memory object `DeclDoc`.
Entry point `DeclDoc.LoadFile(path)` (`DeclJson.cs:48`); the underlying JSON parsing borrows `AuditJson.Parse` from `AuditIO.cs`
(`DeclJson.cs:57`); this file doesn't pull in a third-party JSON library.

**Who calls it**: `DeclDoc.LoadFile(declPath)` at `DepCompiler.cs:189`; `DepPlan.cs` only reads it throughout.

---

## DepPlan.cs — plan layer of the dependency compiler (runs offline)

**What it does**: compiles the `writer: gen|ours_legacy` entries in the declaration into a "writer plan": condition expression
`PExpr` → DNF (`DepPlan.cs:192-356`), then decides which backend each dependency goes to —
`sc` (attach an MA ShapeChanger on the covering part object, condition = that object's `activeSelf`, only for kind ∈ {D1,D3}
and the condition simplifies to "an OR of several vis") or `clip` (generate a two-state `Decl: <dep_id>` layer in our FX controller,
`DepPlan.cs:12-18`). Layer names/asset names are normalized first (`.` and other illegal characters → `_`, `DepPlan.cs:870-877`) and reconciliation recognizes only normalized names.

**Input/output**: input `DeclDoc`, the `decl.json` path and SHA, `out/inventory.json`
(`InventoryIndex.Load`, `DepPlan.cs:521`), existing controller layer names; output `DepPlanResult`
(`ScWriter` / `ClipWriter` lists, `TotalTransitions`, warnings, `DepPlan.cs:415`).
Entry point `DepPlan.Build(doc, declPath, declSha, inv, existingLayerNames, controllerPath)` (`DepPlan.cs:911`).

**Who calls it**: `DepCompiler.cs:198`; this file doesn't touch Unity and can be run offline to verify "which backend is chosen, how the condition simplifies,
which values the two states write".

---

## DepCompiler.cs — execution layer (Unity editor)

**What it does**: materializes the plan computed by `DepPlan` into two kinds of writers: the `sc` backend does
`Undo.AddComponent<ModularAvatarShapeChanger>()` on the covering part object; the `clip` backend generates
a `Decl: <dep_id>` layer in our FX controller (`DepCompiler.cs:9-12`). Idempotent: a rerun first deletes, by normalized layer name + `gen_writers.json`,
the clip layers and `Decl_*.anim` this tool produced itself, then rebuilds; sc is verified by `component_fingerprint` (`DepCompiler.cs:13-16`).
After running it writes back `<工程>/_感知/gen_writers.json` (`DepCompiler.cs:184,325`).

**Input/output**: input `<工程>/_感知/decl.json` + `out/inventory.json` (`DepCompiler.cs:176-184`);
output MA ShapeChangers on scene objects, `Decl_*.anim` and controller layers under `Assets/_Work/Gen/`, and `gen_writers.json`.
Entry point `Run(projectDeclDir, dryRun)` (`DepCompiler.cs:157`) → `Execute` (`DepCompiler.cs:172`);
menus `Tools/AvatarGen/DepCompiler/Dry Run` / `Apply` (`DepCompiler.cs:70,73`);
the menus only read `Library/AvatarGen/depcompiler_request.json` and write results to `depcompiler_status.json` (`DepCompiler.cs:22-26`).

**Who calls it**: ① at the end of `MenuGenA2.Run()`, **synchronously** calls `DepCompiler.Run(declDir, false)` to close out the generation order
(`工程A/Assets/Editor/AvatarGen/MenuGenA2.cs:686-699`, paired with `DepCompiler.cs:28,31-34`);
② editor / MCP goes through `execute_menu_item("Tools/AvatarGen/DepCompiler/Apply")` then polls status.
⚠ Don't call apply directly from `execute_code` — it bypasses the menu's asynchronous queue (`DepCompiler.cs:26-27`).

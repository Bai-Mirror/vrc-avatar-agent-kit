# 生成/ —— 依赖编译器（T-06）

这目录只有三个 `.cs`，是同一件事的三层：**读声明 → 算计划 → 落成写者**。

```
decl.json ──DeclJson.LoadFile──▶ DeclDoc ──DepPlan.Build──▶ DepPlanResult ──DepCompiler.Execute──▶ 场景/控制器
   （只读数据模型）                  `DeclJson.cs`            （纯计划，离线可跑）      `DepPlan.cs`        （Unity 编辑器）  `DepCompiler.cs`
```

分层的关键约束：`DeclJson.cs` 与 `DepPlan.cs` **不 `using UnityEditor / UnityEngine`**（`DeclJson.cs:6-7`），
所以能用 Mono csc 离线编出来单跑计划；只有 `DepCompiler.cs` 引用 MA/Unity，必须进编辑器。
设计出处 `_长程任务_20260918/感知机制研究/04_第一期开工清单.md` T-06。

---

## DeclJson.cs —— `decl.json` 的只读数据模型

**做什么**：把 `decl_validate.py` 产出的声明 JSON 读成类型化对象（`DeclDoc` /
`DeclAvatar` / `DeclMenu` / `DeclControl` / `DeclSlot` / `DeclOutfit` / `DeclObject` /
`DeclToggle` / `DeclPart` / `DeclTarget` / `DeclCase` / `DeclDep`，见 `DeclJson.cs:20,234-317`）。
字段缺失一律降级为默认值、不抛异常 —— 声明是别的工具产出的，编译器宁可少做一条也不能整批跑不动（`DeclJson.cs:9-10`）。

**输入输出**：输入 `<工程>/_感知/decl.json`（`schema=perception/0.2`）；输出是内存对象 `DeclDoc`。
入口 `DeclDoc.LoadFile(path)`（`DeclJson.cs:48`），底层 JSON 解析借 `AuditIO.cs` 的
`AuditJson.Parse`（`DeclJson.cs:57`），本文件不引第三方 JSON 库。

**谁调用**：`DepCompiler.cs:189` 的 `DeclDoc.LoadFile(declPath)`；`DepPlan.cs` 全程只读它。

---

## DepPlan.cs —— 依赖编译器的计划层（离线可跑）

**做什么**：把声明里 `writer: gen|ours_legacy` 的条目编译成「写者计划」：条件表达式
`PExpr` → DNF（`DepPlan.cs:192-356`），再决定每条依赖走哪个后端 ——
`sc`（在覆盖件物体上挂 MA ShapeChanger，条件 = 该物体 `activeSelf`，仅 kind ∈ {D1,D3}
且条件化简为「若干 vis 的或」）或 `clip`（在我方 FX 控制器里生成 `Decl: <dep_id>` 两态层，
`DepPlan.cs:12-18`）。层名/资产名先规范化（`.` 等非法字符 → `_`，`DepPlan.cs:870-877`）并对账只认规范化名。

**输入输出**：输入 `DeclDoc`、`decl.json` 路径与 SHA、`out/inventory.json`
（`InventoryIndex.Load`，`DepPlan.cs:521`）、现有控制器层名；输出 `DepPlanResult`
（`ScWriter` / `ClipWriter` 清单、`TotalTransitions`、warning，`DepPlan.cs:415`）。
入口 `DepPlan.Build(doc, declPath, declSha, inv, existingLayerNames, controllerPath)`（`DepPlan.cs:911`）。

**谁调用**：`DepCompiler.cs:198`；本文件不碰 Unity，可离线跑验证「选哪个后端、条件怎么化简、
两态写什么值」。

---

## DepCompiler.cs —— 执行层（Unity 编辑器）

**做什么**：把 `DepPlan` 算出的计划落成两种写者：`sc` 后端在覆盖件物体上
`Undo.AddComponent<ModularAvatarShapeChanger>()`；`clip` 后端在我方 FX 控制器里生成
`Decl: <dep_id>` 层（`DepCompiler.cs:9-12`）。幂等：重跑先按规范化层名 + `gen_writers.json`
删本工具自产的 clip 层与 `Decl_*.anim`，再重建；sc 按 `component_fingerprint` 校验（`DepCompiler.cs:13-16`）。
跑完写回 `<工程>/_感知/gen_writers.json`（`DepCompiler.cs:184,325`）。

**输入输出**：输入 `<工程>/_感知/decl.json` + `out/inventory.json`（`DepCompiler.cs:176-184`）；
输出场景物体上的 MA ShapeChanger、`Assets/_Work/Gen/` 下的 `Decl_*.anim` 与控制器层、`gen_writers.json`。
入口 `Run(projectDeclDir, dryRun)`（`DepCompiler.cs:157`）→ `Execute`（`DepCompiler.cs:172`）；
菜单 `Tools/AvatarGen/DepCompiler/Dry Run` / `Apply`（`DepCompiler.cs:70,73`），
菜单只读 `Library/AvatarGen/depcompiler_request.json`、结果写 `depcompiler_status.json`（`DepCompiler.cs:22-26`）。

**谁调用**：① `MenuGenA2.Run()` 末尾**同步**调 `DepCompiler.Run(declDir, false)` 做生成顺序收口
（`工程A/Assets/Editor/AvatarGen/MenuGenA2.cs:686-699`，配套 `DepCompiler.cs:28,31-34`）；
② 编辑器/ MCP 走 `execute_menu_item("Tools/AvatarGen/DepCompiler/Apply")` 后轮询 status。
⚠ 别从 `execute_code` 直接调 apply —— 会绕过菜单的异步排队（`DepCompiler.cs:26-27`）。

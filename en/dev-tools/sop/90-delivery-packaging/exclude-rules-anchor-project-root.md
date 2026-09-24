> 🌐 English translation · [中文原文](../../../../开发工具/SOP/90_交付打包/排除规则锚定工程根.md)

# ⛔ Exclude rules must be anchored to the project root

> Subpage split out of [`90-delivery-packaging.md`](../90-delivery-packaging.md). Continues the section of the same name; the exclusion criteria of step 2 and the compile acceptance of step 3 remain on the main page.

## ⛔ Exclude rules must be anchored to the project root

**`-xr!Library` recursively matches same-named directories at any depth.**

> **Delivered defect found on 2026-09-01**: the Project G project delivered for Project G **did not compile** —
> under `Packages/vrchat.blackstartx.gesture-manager/Scripts/{Editor,Runtime}/Library/`,
> 19 `.cs`/`.meta` files had been excluded. As soon as the client opened it, it reported
> `error CS0234: 命名空间 BlackStartX.GestureManager 中不存在类型或命名空间名 Library` (the type or namespace name `Library` does not exist in the namespace BlackStartX.GestureManager).
> Project F and Project E (8-28) and Project D (8-19) in the same batch were not affected; only the 8-20 run was.

- **Correct form**: exclude only at the project-root level. Other names with the same risk: `Temp` / `Logs` / `obj` / `Captures`
- **Acceptance action (mandatory)**: unpack the project zip to a temporary directory,
  **open it once with Unity batchmode to see whether it compiles** —
  `Unity.exe -batchmode -projectPath <解出的工程> -logFile <log> -quit`,
  then check whether `Library/ScriptAssemblies/Assembly-CSharp-Editor.dll` exists
- Only checking “number of excluded entries is 0” **cannot catch this class**, because what was wrongly removed are files inside a plugin, not on the violation list

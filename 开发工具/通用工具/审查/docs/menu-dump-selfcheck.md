# T4 菜单导出 · 自检与已知局限 <!-- nav -->

> 旧称：T4（原 `审查/README_T4.md`） §6–§8。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T4 菜单导出 · 输出字段](menu-dump-output.md) <!-- nav -->

## 6. 自检 1：反射用到的 SDK / Unity 符号（逐条核对过）

| 用到的符号 | 来源（本机路径） | 读法 |
|---|---|---|
| `VRCAvatarDescriptor.expressionsMenu` / `.expressionParameters` / `.baseAnimationLayers` | `Packages/com.vrchat.avatars/Runtime/VRCSDK/Plugins/VRCSDK3A.dll`（strings 核到字段名） | 反射字段 |
| `VRCExpressionsMenu.controls` | 同上 | 反射字段 |
| `Control.name/.type/.parameter/.value/.subParameters/.labels/.subMenu` | 同上 | 反射字段 |
| `Control.Parameter.name` | 同上（`Control` 的取值在 `Control.value`，Parameter 只有 name） | 反射字段 |
| `Control.ControlType`（Button/Toggle/SubMenu/TwoAxis/FourAxis/RadialPuppet） | `Editor/.../ExpressionsControlOptions.cs:200-370` 的 switch | `FieldType` 反射枚举 → `ToString()` + `Convert.ToInt32` |
| `VRCExpressionParameters.parameters` | dll + `VRCExpressionParametersEditor.cs` | 反射字段 |
| `Parameter.name/.valueType/.defaultValue/.saved/.networkSynced` | `Editor/.../ExpressionParameter/ExpressionParameterField.cs:78`（networkSynced）等 | 反射字段 |
| `Parameter.ValueType`（Int/Float/Bool） | `VRCExpressionParametersEditor.cs:187-203` | 同上 |
| `CustomAnimLayer.type/.isDefault/.animatorController` | `Editor/.../VRCAvatarDescriptorEditor3AnimLayerInit.cs:85-196` | 反射字段 |
| `AnimatorController.parameters` → `AnimatorControllerParameter.name/.type` | `Managed/UnityEditor.dll`（`get_parameters` 符号）+ `Managed/UnityEngine/UnityEngine.AnimationModule.dll` | 反射属性/字段 |
| AuditIO 公共件 | `AuditIO.cs` 现状 | `AuditAvatar.Resolve` / `AuditAvatar.FindDescriptor` / `AuditJson.WriteFile` / `JsonObject` / `AuditStatus` / `AuditUtil` / `AuditContext.Warn` |

**不硬编码枚举整数**：`type` / `valueType` / `layer_type` 都从 SDK 反射到的枚举实例上取名字和
`Convert.ToInt32`。这样 SDK 改了枚举值也不会把工具的判断带偏（输出里能看到真实值）。

---

## 7. 已知局限 / 明确没做的

1. **只读 `baseAnimationLayers`**，不读 `specialAnimationLayers`（坐姿/TPose 等专用层）。
   需要时在 `ReadDescriptor` 里加一段即可，接口已留好。
2. **只展开一份子菜单**：按实例 ID 全局去重（这也是防环的手段）。同一子菜单资产被多个控件共享时，
   只有第一次的路径会出现在输出里，后面几次记 warning。**这会漏掉「同一个子菜单挂在两个父菜单下」的路径**；
   若要全列，需要把「防环」改成「只防当前递归栈上的环」。
3. **`params_not_in_menu` 会包含大量 VRChat/GM 内置参数**（GestureLeft、Grounded…）。
   已用 `likely_builtin` 标记，不要据此报缺陷。
4. **`menu_values` 对 Radial/轴的连续参数为空**（它们没有离散取值）；给 T1 的候选看 `suggested_values`。
5. **构建时机**：靠 `warmup_frames` 等 NDMF 构建落地。若构建仍未完成就读，会得到编辑期的菜单
   （控件数偏少、没有 MA 注入项）。判断方法：`menu.control_count` 与菜单里肉眼可见的项数对不上时，
   加大 `warmup_frames` 重跑。工具本身无法自动判定「NDMF 已完成」。
6. **控制器类型**：`AnimatorController.parameters` 只在 `UnityEditor.Animations.AnimatorController`
   上有；运行时若拿到别的 `RuntimeAnimatorController` 子类，该层参数记 warning 后留空。
   `AnimatorOverrideController` 只向下拆一层。
7. **面捕克隆**：若进 Play 后出现两个同名活跃根，`AuditAvatar.Resolve` 会和 T1 一样**报错**，
   需人工关掉一个；这是刻意不猜。
8. **写文件的副作用**：只写 `out` 目录下的 3 个文件与 AuditIO 的 `status.json`/`audit.log`；
   不改场景、不改参数、不改 Animator，所以 `Cleanup` 是空操作。

---

## 8. 自检 2：本轮做了 / 没做

**做了（可复现）**：离线编译 0 error / 0 warning。用 README.md §0.2 的命令（临时脚本
`_长程任务_20260918/派工/tmp/compile_audit_L.sh`，日志 `L_compile_full.log`）：

```bash
MONO=<Unity安装根>/Editors/2022.3.22f1/Editor/Data/MonoBleedingEdge/bin/mono
CSC=<Unity安装根>/Editors/2022.3.22f1/Editor/Data/MonoBleedingEdge/lib/mono/4.5/csc.exe
BASE=<Unity安装根>/Editors/2022.3.22f1/Editor/Data
REFS="-nostdlib+ -r:$BASE/NetStandard/ref/2.1.0/netstandard.dll"
for f in $BASE/NetStandard/compat/2.1.0/shims/netstandard/*.dll \
         $BASE/NetStandard/compat/2.1.0/shims/netfx/*.dll \
         $BASE/Managed/UnityEngine/UnityEngine*.dll \
         $BASE/Managed/UnityEditor.dll; do REFS="$REFS -r:$f"; done
$MONO "$CSC" -nologo -target:library -langversion:9 -warn:4 -out:audit_L_full.dll $REFS \
     开发工具/通用工具/审查/unity/Editor/AuditIO.cs \
     开发工具/通用工具/审查/unity/Editor/AuditStateDriver.cs \
     开发工具/通用工具/审查/unity/Editor/AuditTurntable.cs \
     开发工具/通用工具/审查/unity/Editor/AuditFitProbe.cs \
     开发工具/通用工具/审查/unity/Editor/AuditMenuDump.cs
# → exit 0，无任何 error / warning
```

**没做（别当成已验证）**：本轮没开 Unity、没进 Play、没在真实构建后的头像上跑过，因此——

1. 「NDMF Apply on Play 之后 descriptor 上的 `expressionsMenu`/`expressionParameters` 确实被换成
   构建产物」这件事，**只有设计文档与插件源码作依据，没有实跑证据**；
2. `Control.subMenu` / `Control.value` 等字段在**构建产物**里的实际取值形状没有实测；
3. `baseAnimationLayers` 在 Play 构建后指向的是不是 `AnimatorController`（能读 `parameters`），没有实测；
4. `menu_tree.md` 的排版、`suggested_values` 的档位是否好用，需要 Claude 首跑后按 T1 的取用情况微调。

**Claude 首跑重点核对**（跑一次 工程A 的 `{"tool":"menu",...}`）：
- `status.json` 是否 `done`，`warnings` 里有没有「读不到字段 / 找不到类型」；
- `menu.control_count` 是否明显多于编辑期可见项（证明 MA 注入被读到）；
- `expression_parameters.count` 与 VRChat SDK 面板一致；
- `params_not_in_menu` 是否只剩内置参数（若全是内置，说明差集口径正确）；
- `menu_params_undeclared` 是否非空（真实工程里常见，值得留意）。

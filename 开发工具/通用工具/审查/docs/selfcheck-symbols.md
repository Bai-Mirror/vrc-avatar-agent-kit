# 自检 1 · 反射用到的 GM / SDK 符号出处 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §7。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T3 · 透明排序判据](turntable-transparency.md) · 下一页：[自检 2 · 临时改动→恢复对照表；自检 3 · 编译期](selfcheck-restore.md) <!-- nav -->

## 7. 自检 1：反射用到的 GM / SDK 符号出处（逐条核对过）

包路径：`工程A/Packages/vrchat.blackstartx.gesture-manager/`（GM 3.9.9）；
下面全部用 `grep -n` / `sed -n` 在本机核对过，19/19 命中。

| 代码里反射的字符串 | 源码出处 | 该行内容 |
|---|---|---|
| `BlackStartX.GestureManager.GestureManager` | `Scripts/Runtime/GestureManager.cs:10` | `public class GestureManager : MonoBehaviour` |
| `ControlledAvatars` | `Scripts/Runtime/GestureManager.cs:13` | `public static readonly Dictionary<GameObject, ModuleBase> ControlledAvatars = new();` |
| `SetModule` | `Scripts/Runtime/GestureManager.cs:67` | `public void SetModule([NotNull] ModuleBase module)` |
| `BlackStartX.GestureManager.Data.ModuleBase` | `Scripts/Runtime/Data/ModuleBase.cs:14` | `public abstract class ModuleBase` |
| `Avatar`（字段） | `Scripts/Runtime/Data/ModuleBase.cs:26` | `public readonly GameObject Avatar;` |
| `Settings`（字段） | `Scripts/Runtime/Data/ModuleBase.cs:34` | `public ModuleSettings Settings;` |
| （模块登记进 `ControlledAvatars` 的位置） | `Scripts/Runtime/Data/ModuleBase.cs:153` | `GestureManager.ControlledAvatars[Avatar] = this;` |
| `simulateCulling` | `Scripts/Runtime/Modules/ModuleSettings.cs:20` | `public bool simulateCulling;` |
| `BlackStartX.GestureManager.Editor.Modules.ModuleHelper` | `Scripts/Editor/Modules/ModuleHelper.cs:11` | `public static class ModuleHelper` |
| `GetModuleFor` | `Scripts/Editor/Modules/ModuleHelper.cs:20` | `public static ModuleBase GetModuleFor(GmgAvatarDescriptor descriptorComponent)` |
| GM 自己创建模块的路径 | `Scripts/Editor/GestureManagerEditor.cs:81` / `:97` | `if (Application.isPlaying) TryInitialize();` / `if (module != null) Manager.SetModule(module);` |
| `BlackStartX.GestureManager.Editor.Modules.Vrc3.ModuleVrc3` | `Scripts/Editor/Modules/Vrc3/ModuleVrc3.cs:39` | `public class ModuleVrc3 : ModuleBase` |
| `Params`（字段） | `Scripts/Editor/Modules/Vrc3/ModuleVrc3.cs:82` | `[PublicAPI] public readonly Dictionary<string, Vrc3Param> Params = new();` |
| `GetParam` | `Scripts/Editor/Modules/Vrc3/ModuleVrc3.cs:1045` | `public Vrc3Param GetParam(string paramName)` |
| `PoseIK` / `PoseT`（internal 字段，用 NonPublic 绑定） | `Scripts/Editor/Modules/Vrc3/ModuleVrc3.cs:105` / `:106` | `internal readonly Vrc3Param PoseIK;` / `internal readonly Vrc3Param PoseT;` |
| `BlackStartX.GestureManager.Editor.Modules.Vrc3.Params.Vrc3Param` | `Scripts/Editor/Modules/Vrc3/Params/Vrc3Param.cs:13` | `public class Vrc3Param` |
| `Vrc3Param.Set(ModuleVrc3, float, object)` | `Scripts/Editor/Modules/Vrc3/Params/Vrc3Param.cs:42` | `public void Set(ModuleVrc3 module, float value, object source = null)` |
| `FloatValue` | `Scripts/Editor/Modules/Vrc3/Params/Vrc3Param.cs:86` | `public virtual float FloatValue()` |
| `Type`（字段） | `Scripts/Editor/Modules/Vrc3/Params/Vrc3Param.cs:19` | `public readonly AnimatorControllerParameterType Type;` |
| （GM 拒绝写 AAP 参数，解释 no_effect） | `Scripts/Editor/Modules/Vrc3/Params/Vrc3Param.cs:168` / `:189` | `private bool _isAap() => ...` / `if (_isAap()) return;` |
| （`Set` 触发 ParameterDriver / LayerControl 联动） | `Scripts/Editor/Modules/Vrc3/ModuleVrc3.cs:1276` / `:1262` | `AvatarParameterDriverSettings(...)` / `AnimatorLayerControlSettings(...)` |
| （GM 内建参数的默认值来源） | `Scripts/Editor/Modules/Vrc3/ModuleVrc3.cs:258-275` | `GetParam(Vrc3DefaultParams.*).InternalSet(...)` |
| （GM 按距离剔除整个头像） | `Scripts/Editor/Modules/Vrc3/ModuleVrc3.cs:975` | `foreach (var renderer in _renderers.Where(...)) renderer.enabled = !culled;` |

任务 F（§3.1 临时创建 GestureManager）追加核对的 4 条：

| 代码里依赖的行为 | 源码出处 | 该行内容 |
|---|---|---|
| 菜单创建 GM 走 prefab | `Scripts/Editor/GestureManagerEditor.cs:43-49` | `[MenuItem("Tools/Gesture Manager Emulator", …)]` → `AssetDatabase.LoadAssetAtPath<GameObject>(StringPath)` |
| GM 自己的兜底创建 | `Scripts/Editor/GestureManagerEditor.cs:63-68` | `new GameObject("GestureManager").AddComponent<GestureManager>()` |
| GM 预制体只含一个组件、settings 已序列化 | `GestureManager.prefab` | GameObject `GestureManager` + MonoBehaviour `guid: 2398979b1d0d84349abc5ee9f0571350`（= `Scripts/Runtime/GestureManager.cs.meta`），`settings.cullingDistance: 5` |
| GM 组件无 Awake/OnEnable/Start，初始化全在 SetModule→Connect→InitForAvatar | `Scripts/Runtime/GestureManager.cs:10-78`；`Scripts/Runtime/Data/ModuleBase.cs:148-154`；`Scripts/Editor/Modules/Vrc3/ModuleVrc3.cs:181-311` | 无生命周期初始化；`Connect()` → `InitForAvatar()` 同步建 PlayableGraph |

VRChat SDK（**只发 DLL，没有源码**，从 GM 源码 + DLL 符号表交叉核对）：

| 反射字符串 | 佐证 |
|---|---|
| `VRC.SDK3.Avatars.Components.VRCAvatarDescriptor` | `ModuleVrc3.cs:32 using VRC.SDK3.Avatars.Components;` + `:45 [PublicAPI] public new readonly VRCAvatarDescriptor AvatarDescriptor;`；DLL `com.vrchat.avatars/Runtime/VRCSDK/Plugins/VRCSDK3A.dll` 符号表含 `VRCAvatarDescriptor` |
| `VRC.SDKBase.VRC_AvatarDescriptor` | `ModuleHelper.cs:3-7` 别名 `GmgAvatarDescriptor = VRC.SDKBase.VRC_AvatarDescriptor`（`GetModuleFor` 的形参类型） |
| `expressionParameters`（字段） | `ModuleVrc3.cs:126 private VRCExpressionParameters Parameters => AvatarDescriptor.expressionParameters;`；DLL 符号表有 `expressionParameters` |
| `VRCExpressionParameters.parameters` | `ModuleVrc3.cs:1013 foreach (var parameter in parameters.parameters)`；DLL 符号表有 `parameters` |
| `Parameter.name` | `ModuleVrc3.cs:1014/1015/1024` 直接读 `parameter.name` |
| `Parameter.defaultValue` | `ModuleVrc3.cs:1024 Params[parameter.name].InternalSet(parameter.defaultValue);`；DLL 符号表有 `defaultValue` |
| （`Parameter.valueType` / `networkSynced`，本工具暂未用，仅记录） | `Vrc3Param.cs:40`；DLL 符号表有 `valueType` / `networkSynced` |

> 为什么用 `AppDomain.CurrentDomain.GetAssemblies()` + `Assembly.GetType(fullName, false)` 而不是
> `Type.GetType("..., assembly")` 或 `GetTypes()`：GM 可能作为 asmdef 包（`vrchat.blackstartx.gesture-manager[.editor]`）
> 存在，也可能被塞进 `Assets/GestureManager/` 编到 `Assembly-CSharp-Editor`。全程序集扫名字两种情况都能命中；
> `GetTypes()` 会强制加载所有类型、在有坏依赖的程序集上抛 `ReflectionTypeLoadException`，还慢得多。

任务 G（§3.0.2 回调隔离）追加核对的 `UnityEditor.dll` 符号（2022.3.22f1，用 `monodis` 反汇编核对）：

| 代码里反射的字符串 | 类型 | 出处 / 结构 |
|---|---|---|
| `update` | `EditorApplication` 公有静态字段 | 类型 `EditorApplication/CallbackFunction`（`.field public static class .../CallbackFunction update`） |
| `m_PlayModeStateChangedEvent` | `EditorApplication` 私有静态字段 | `add_/remove_playModeStateChanged` 里 `ldsflda ... m_PlayModeStateChangedEvent` |
| `add_/remove_playModeStateChanged` | 公有静态 specialname 方法 | 事件 `playModeStateChanged` 的访问器（自定义 add/remove，**不是**字段式事件） |
| `m_Delegate` | `EventWithPerformanceTracker<T>`（值类型）私有实例字段 | 类型 `DelegateWithHandle<T>` |
| `m_DelegateOrList` | `DelegateWithHandle<T>` 私有实例字段 | 类型 `EventWithPerformanceTracker/Entry`（值类型） |
| `Reference` | `EventWithPerformanceTracker/Entry` internal 实例字段 | 单个委托，或多订阅者时的 `Entry[]`（每个元素再取 `Reference`） |

`AvatarGen.RuntimeProbe._armed`：`工程A/Assets/Editor/AvatarGen/RuntimeProbe.cs:44`（`static bool _armed`）。

---

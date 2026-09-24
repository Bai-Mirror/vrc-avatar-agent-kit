> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/selfcheck-symbols.md)

# Self-check 1 · Origins of GM / SDK symbols used via reflection <!-- nav -->

> Formerly: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (originally `审查/README.md`) §7. § numbers follow the original; for cross-page § references see [Documentation index](../README.md). <!-- nav -->
> Previous: [T3 · Transparency sorting criteria](turntable-transparency.md) · Next: [Self-check 2 · Temporary change → restore table; Self-check 3 · Compile time](selfcheck-restore.md) <!-- nav -->

## 7. Self-check 1: Origins of GM / SDK symbols used via reflection (checked one by one)

Package path: `工程A/Packages/vrchat.blackstartx.gesture-manager/` (GM 3.9.9);
everything below was checked on this machine with `grep -n` / `sed -n`, 19/19 hits.

| String reflected in code | Source location | Line content |
|---|---|---|
| `BlackStartX.GestureManager.GestureManager` | `Scripts/Runtime/GestureManager.cs:10` | `public class GestureManager : MonoBehaviour` |
| `ControlledAvatars` | `Scripts/Runtime/GestureManager.cs:13` | `public static readonly Dictionary<GameObject, ModuleBase> ControlledAvatars = new();` |
| `SetModule` | `Scripts/Runtime/GestureManager.cs:67` | `public void SetModule([NotNull] ModuleBase module)` |
| `BlackStartX.GestureManager.Data.ModuleBase` | `Scripts/Runtime/Data/ModuleBase.cs:14` | `public abstract class ModuleBase` |
| `Avatar` (field) | `Scripts/Runtime/Data/ModuleBase.cs:26` | `public readonly GameObject Avatar;` |
| `Settings` (field) | `Scripts/Runtime/Data/ModuleBase.cs:34` | `public ModuleSettings Settings;` |
| (where the module registers into `ControlledAvatars`) | `Scripts/Runtime/Data/ModuleBase.cs:153` | `GestureManager.ControlledAvatars[Avatar] = this;` |
| `simulateCulling` | `Scripts/Runtime/Modules/ModuleSettings.cs:20` | `public bool simulateCulling;` |
| `BlackStartX.GestureManager.Editor.Modules.ModuleHelper` | `Scripts/Editor/Modules/ModuleHelper.cs:11` | `public static class ModuleHelper` |
| `GetModuleFor` | `Scripts/Editor/Modules/ModuleHelper.cs:20` | `public static ModuleBase GetModuleFor(GmgAvatarDescriptor descriptorComponent)` |
| GM's own module-creation path | `Scripts/Editor/GestureManagerEditor.cs:81` / `:97` | `if (Application.isPlaying) TryInitialize();` / `if (module != null) Manager.SetModule(module);` |
| `BlackStartX.GestureManager.Editor.Modules.Vrc3.ModuleVrc3` | `Scripts/Editor/Modules/Vrc3/ModuleVrc3.cs:39` | `public class ModuleVrc3 : ModuleBase` |
| `Params` (field) | `Scripts/Editor/Modules/Vrc3/ModuleVrc3.cs:82` | `[PublicAPI] public readonly Dictionary<string, Vrc3Param> Params = new();` |
| `GetParam` | `Scripts/Editor/Modules/Vrc3/ModuleVrc3.cs:1045` | `public Vrc3Param GetParam(string paramName)` |
| `PoseIK` / `PoseT` (internal fields, bound with NonPublic) | `Scripts/Editor/Modules/Vrc3/ModuleVrc3.cs:105` / `:106` | `internal readonly Vrc3Param PoseIK;` / `internal readonly Vrc3Param PoseT;` |
| `BlackStartX.GestureManager.Editor.Modules.Vrc3.Params.Vrc3Param` | `Scripts/Editor/Modules/Vrc3/Params/Vrc3Param.cs:13` | `public class Vrc3Param` |
| `Vrc3Param.Set(ModuleVrc3, float, object)` | `Scripts/Editor/Modules/Vrc3/Params/Vrc3Param.cs:42` | `public void Set(ModuleVrc3 module, float value, object source = null)` |
| `FloatValue` | `Scripts/Editor/Modules/Vrc3/Params/Vrc3Param.cs:86` | `public virtual float FloatValue()` |
| `Type` (field) | `Scripts/Editor/Modules/Vrc3/Params/Vrc3Param.cs:19` | `public readonly AnimatorControllerParameterType Type;` |
| (GM refuses to write AAP parameters, explains no_effect) | `Scripts/Editor/Modules/Vrc3/Params/Vrc3Param.cs:168` / `:189` | `private bool _isAap() => ...` / `if (_isAap()) return;` |
| (`Set` triggers ParameterDriver / LayerControl side effects) | `Scripts/Editor/Modules/Vrc3/ModuleVrc3.cs:1276` / `:1262` | `AvatarParameterDriverSettings(...)` / `AnimatorLayerControlSettings(...)` |
| (source of default values for GM built-in parameters) | `Scripts/Editor/Modules/Vrc3/ModuleVrc3.cs:258-275` | `GetParam(Vrc3DefaultParams.*).InternalSet(...)` |
| (GM culls the whole avatar by distance) | `Scripts/Editor/Modules/Vrc3/ModuleVrc3.cs:975` | `foreach (var renderer in _renderers.Where(...)) renderer.enabled = !culled;` |

4 additional items checked for task F (§3.1 temporarily creating a GestureManager):

| Behavior the code relies on | Source location | Line content |
|---|---|---|
| Creating GM from the menu goes through the prefab | `Scripts/Editor/GestureManagerEditor.cs:43-49` | `[MenuItem("Tools/Gesture Manager Emulator", …)]` → `AssetDatabase.LoadAssetAtPath<GameObject>(StringPath)` |
| GM's own fallback creation | `Scripts/Editor/GestureManagerEditor.cs:63-68` | `new GameObject("GestureManager").AddComponent<GestureManager>()` |
| The GM prefab contains only one component, settings already serialized | `GestureManager.prefab` | GameObject `GestureManager` + MonoBehaviour `guid: 2398979b1d0d84349abc5ee9f0571350` (= `Scripts/Runtime/GestureManager.cs.meta`), `settings.cullingDistance: 5` |
| The GM component has no Awake/OnEnable/Start; all initialization is in SetModule→Connect→InitForAvatar | `Scripts/Runtime/GestureManager.cs:10-78`; `Scripts/Runtime/Data/ModuleBase.cs:148-154`; `Scripts/Editor/Modules/Vrc3/ModuleVrc3.cs:181-311` | No lifecycle initialization; `Connect()` → `InitForAvatar()` builds the PlayableGraph synchronously |

VRChat SDK (**ships DLLs only, no source**; cross-checked from GM source + DLL symbol tables):

| Reflected string | Evidence |
|---|---|
| `VRC.SDK3.Avatars.Components.VRCAvatarDescriptor` | `ModuleVrc3.cs:32 using VRC.SDK3.Avatars.Components;` + `:45 [PublicAPI] public new readonly VRCAvatarDescriptor AvatarDescriptor;`; the symbol table of DLL `com.vrchat.avatars/Runtime/VRCSDK/Plugins/VRCSDK3A.dll` contains `VRCAvatarDescriptor` |
| `VRC.SDKBase.VRC_AvatarDescriptor` | `ModuleHelper.cs:3-7` alias `GmgAvatarDescriptor = VRC.SDKBase.VRC_AvatarDescriptor` (parameter type of `GetModuleFor`) |
| `expressionParameters` (field) | `ModuleVrc3.cs:126 private VRCExpressionParameters Parameters => AvatarDescriptor.expressionParameters;`; the DLL symbol table has `expressionParameters` |
| `VRCExpressionParameters.parameters` | `ModuleVrc3.cs:1013 foreach (var parameter in parameters.parameters)`; the DLL symbol table has `parameters` |
| `Parameter.name` | `ModuleVrc3.cs:1014/1015/1024` reads `parameter.name` directly |
| `Parameter.defaultValue` | `ModuleVrc3.cs:1024 Params[parameter.name].InternalSet(parameter.defaultValue);`; the DLL symbol table has `defaultValue` |
| (`Parameter.valueType` / `networkSynced`, not yet used by this tool, recorded only) | `Vrc3Param.cs:40`; the DLL symbol table has `valueType` / `networkSynced` |

> Why use `AppDomain.CurrentDomain.GetAssemblies()` + `Assembly.GetType(fullName, false)` instead of
> `Type.GetType("..., assembly")` or `GetTypes()`: GM may exist as an asmdef package (`vrchat.blackstartx.gesture-manager[.editor]`),
> or may be dropped into `Assets/GestureManager/` and compiled into `Assembly-CSharp-Editor`. Scanning names across all assemblies hits in both cases;
> `GetTypes()` forces loading of all types, throws `ReflectionTypeLoadException` on assemblies with broken dependencies, and is much slower.

`UnityEditor.dll` symbols additionally checked for task G (§3.0.2 callback isolation) (2022.3.22f1, checked by disassembling with `monodis`):

| String reflected in code | Kind | Location / structure |
|---|---|---|
| `update` | `EditorApplication` public static field | Type `EditorApplication/CallbackFunction` (`.field public static class .../CallbackFunction update`) |
| `m_PlayModeStateChangedEvent` | `EditorApplication` private static field | `ldsflda ... m_PlayModeStateChangedEvent` inside `add_/remove_playModeStateChanged` |
| `add_/remove_playModeStateChanged` | public static specialname methods | Accessors of the `playModeStateChanged` event (custom add/remove, **not** a field-like event) |
| `m_Delegate` | private instance field of `EventWithPerformanceTracker<T>` (value type) | Type `DelegateWithHandle<T>` |
| `m_DelegateOrList` | private instance field of `DelegateWithHandle<T>` | Type `EventWithPerformanceTracker/Entry` (value type) |
| `Reference` | internal instance field of `EventWithPerformanceTracker/Entry` | A single delegate, or `Entry[]` when there are multiple subscribers (take `Reference` from each element) |

`AvatarGen.RuntimeProbe._armed`: `工程A/Assets/Editor/AvatarGen/RuntimeProbe.cs:44` (`static bool _armed`).

---

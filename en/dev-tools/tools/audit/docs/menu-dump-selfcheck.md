> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/menu-dump-selfcheck.md)

# T4 menu export · self-check and known limitations <!-- nav -->

> Former name: T4 (originally `审查/README_T4.md`) §6–§8. § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous page: [T4 menu export · output fields](menu-dump-output.md) <!-- nav -->

## 6. Self-check 1: SDK / Unity symbols used via reflection (each one verified)

| Symbol used | Source (path on this machine) | How it is read |
|---|---|---|
| `VRCAvatarDescriptor.expressionsMenu` / `.expressionParameters` / `.baseAnimationLayers` | `Packages/com.vrchat.avatars/Runtime/VRCSDK/Plugins/VRCSDK3A.dll` (field names verified with strings) | Reflected field |
| `VRCExpressionsMenu.controls` | Same as above | Reflected field |
| `Control.name/.type/.parameter/.value/.subParameters/.labels/.subMenu` | Same as above | Reflected field |
| `Control.Parameter.name` | Same as above (the `Control`'s value lives in `Control.value`; Parameter only has name) | Reflected field |
| `Control.ControlType` (Button/Toggle/SubMenu/TwoAxis/FourAxis/RadialPuppet) | The switch in `Editor/.../ExpressionsControlOptions.cs:200-370` | Enum reflected via `FieldType` → `ToString()` + `Convert.ToInt32` |
| `VRCExpressionParameters.parameters` | dll + `VRCExpressionParametersEditor.cs` | Reflected field |
| `Parameter.name/.valueType/.defaultValue/.saved/.networkSynced` | `Editor/.../ExpressionParameter/ExpressionParameterField.cs:78` (networkSynced) etc. | Reflected field |
| `Parameter.ValueType` (Int/Float/Bool) | `VRCExpressionParametersEditor.cs:187-203` | Same as above |
| `CustomAnimLayer.type/.isDefault/.animatorController` | `Editor/.../VRCAvatarDescriptorEditor3AnimLayerInit.cs:85-196` | Reflected field |
| `AnimatorController.parameters` → `AnimatorControllerParameter.name/.type` | `Managed/UnityEditor.dll` (`get_parameters` symbol) + `Managed/UnityEngine/UnityEngine.AnimationModule.dll` | Reflected property/field |
| AuditIO shared parts | Current `AuditIO.cs` | `AuditAvatar.Resolve` / `AuditAvatar.FindDescriptor` / `AuditJson.WriteFile` / `JsonObject` / `AuditStatus` / `AuditUtil` / `AuditContext.Warn` |

**Enum integers are not hard-coded**: `type` / `valueType` / `layer_type` all take the name and
`Convert.ToInt32` from the enum instance obtained via SDK reflection. That way, even if the SDK changes enum values, the tool's judgment isn't thrown off (the output shows the real values).

---

## 7. Known limitations / explicitly not done

1. **Only reads `baseAnimationLayers`**, not `specialAnimationLayers` (dedicated layers such as sitting/TPose).
   If needed, add a section in `ReadDescriptor`; the interface is already in place.
2. **Each submenu is expanded only once**: globally deduplicated by instance ID (this is also the cycle-prevention mechanism). When the same submenu asset is shared by multiple controls,
   only the first path appears in the output; later occurrences log a warning. **This misses paths where "the same submenu hangs under two parent menus"**;
   to list them all, change "cycle prevention" to "only prevent cycles on the current recursion stack".
3. **`params_not_in_menu` includes many VRChat/GM built-in parameters** (GestureLeft, Grounded…).
   They are already flagged with `likely_builtin`; don't report defects based on them.
4. **`menu_values` is empty for continuous Radial/axis parameters** (they have no discrete values); for T1 candidates look at `suggested_values`.
5. **Build timing**: relies on `warmup_frames` to wait for the NDMF build to land. If it reads before the build has finished, it gets the edit-time menu
   (fewer controls, no MA-injected items). How to tell: when `menu.control_count` doesn't match the number of items visibly present in the menu,
   increase `warmup_frames` and rerun. The tool itself cannot automatically determine "NDMF has finished".
6. **Controller type**: `AnimatorController.parameters` only exists on `UnityEditor.Animations.AnimatorController`;
   if at runtime some other `RuntimeAnimatorController` subclass is obtained, that layer's parameters log a warning and are left empty.
   `AnimatorOverrideController` is only unwrapped one level down.
7. **Face tracking clones**: if two same-named active roots appear after entering Play, `AuditAvatar.Resolve` **errors** just like T1,
   and one must be turned off manually; not guessing is deliberate.
8. **Side effects of writing files**: only writes the 3 files under the `out` directory and AuditIO's `status.json`/`audit.log`;
   it does not change the scene, parameters, or Animator, so `Cleanup` is a no-op.

---

## 8. Self-check 2: done / not done this round

**Done (reproducible)**: offline compile with 0 errors / 0 warnings. Using the command from README.md §0.2 (temporary script
`_长程任务_20260918/派工/tmp/compile_audit_L.sh`, log `L_compile_full.log`):

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
# → exit 0, no errors / warnings at all
```

**Not done (don't treat as verified)**: this round did not open Unity, did not enter Play, and did not run on a real built avatar, therefore:

1. That "after NDMF Apply on Play, the descriptor's `expressionsMenu`/`expressionParameters` really are replaced with
   the build output" **is supported only by the design document and plugin source code, with no actual run evidence**;
2. The actual value shapes of fields such as `Control.subMenu` / `Control.value` in the **build output** have not been measured;
3. Whether `baseAnimationLayers` after the Play build points to an `AnimatorController` (so `parameters` can be read) has not been measured;
4. The layout of `menu_tree.md` and whether the `suggested_values` steps are useful need to be fine-tuned by Claude after the first run, based on how T1 uses them.

**Key things for Claude to check on the first run** (run Project A's `{"tool":"menu",...}` once):
- Whether `status.json` is `done`, and whether `warnings` contains "cannot read field / cannot find type";
- Whether `menu.control_count` is clearly larger than the items visible at edit time (proving MA injections were read);
- Whether `expression_parameters.count` matches the VRChat SDK panel;
- Whether `params_not_in_menu` only has built-in parameters left (if all are built-in, the set-difference basis is correct);
- Whether `menu_params_undeclared` is non-empty (common in real projects, worth noting).

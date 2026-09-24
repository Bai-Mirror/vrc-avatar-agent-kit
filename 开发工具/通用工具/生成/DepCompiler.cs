// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】依赖编译器 · 执行层（T-06，Unity 编辑器）
//
// 适用素体：无关（读 <工程>/_感知/decl.json 的 writer: gen|ours_legacy 条目）。
// 用途：把 DepPlan 编译出的计划落成两种写者：
//   · sc   后端：在覆盖件物体上 Undo.AddComponent<ModularAvatarShapeChanger>()
//                （Shapes=[{Object, ShapeName, ChangeType=Set, Value}]；
//                 条件由 MA 从该物体的 activeSelf 派生 —— 一个 vis 项挂一件，
//                 多项的“或”就是各处各挂一件，同值 Set 由 MA 合并）
//   · clip 后端：在我方 FX 控制器里生成 `Decl: <dep_id>` 层（两态都显式写值，
//                常量切线；层序插在部位层之后、压制层之前）
//
// 幂等（2026-09-19 返工）：层名/资产名在 DepPlan 里就把 `.` 等非法字符映射成 `_`，
//   gen_writers.json 记**实际写进控制器的层名**（回读 layer.name，不是请求名）。
//   重跑先按「规范化后的层名 + 记录」删本工具自产的 clip 层与 `Decl_*.anim`，再重建；
//   sc 按 component_fingerprint 校验，不符就保留不删。跑 N 次层数/过渡数/条目数不变。
//
// 性能（2026-09-19 返工）：所有 clip 资产写在 AssetDatabase.StartAssetEditing() /
//   StopAssetEditing() 之间，结尾一次 SaveAssets()；AJ 版每个 clip 一次 CreateAsset/DeleteAsset
//   → 46 次资产刷新 / 一轮 4 分钟，超过 MCP 超时被重发 4 次。目标整轮 < 10 s。
//
// 菜单异步（2026-09-19 返工）：MenuItem 只读 <工程>/Library/AvatarGen/depcompiler_request.json
//   并 EditorApplication.delayCall 排队，立刻返回；执行结果写 depcompiler_status.json
//   （state=running|done|error、计划/结果、层数/过渡数/SC 数/耗时）。触发方式：
//     execute_menu_item("Tools/AvatarGen/DepCompiler/Apply") → 轮询 status.json。
//   ⚠ Run(dir, dryRun) 平时只供菜单内部调用；别从 execute_code 直接调 apply ——
//     MCP 超时会把同一段代码重发，非幂等的长操作必须走「菜单 + 请求文件」。
//     例外：MenuGenA2.Run() 末尾会**同步**调 Run(DefaultDeclDir(), false) 做生成顺序收口
//     （见下条），它是同步菜单、不经 execute_code，且一轮 <1 s，不触发重发坑。
//
// 生成顺序（B-T07a 收口）：MenuGenA2.Run() 开头 `DeleteAsset(Assets/_Work/Gen)` 会把本工具
//   落的 `Decl:` 层与 `Decl_*.anim` 一起删掉（2026-09-19 实测）。为免「跑生成器 → 声明层消失」，
//   MenuGenA2 末尾自动调本工具 Apply；因此正常流程**只跑一次 MenuGenA2 菜单即可**，
//   不必再手动 `DepCompiler/Apply`（手动再跑一次也幂等，不会叠层）。两边注释同改。
//
// ⚠ 引用 MA 程序集，离线编不了：本文件必须在 Unity 里编译。
//   计划逻辑在 DepPlan.cs（离线可跑，见 _长程任务_20260918/派工/tmp/al/）。
// ══════════════════════════════════════════════════════════════════
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using nadena.dev.modular_avatar.core;
using AvatarAudit;

namespace AvatarGen
{
    public static class DepCompiler
    {
        const string GEN = "Assets/_Work/Gen";
        const string CONTROLLER_PATH = GEN + "/A2_FX.controller";
        const string CLIP_DIR = GEN + "/Clip";
        const string AVATAR_FALLBACK = "Kaguya-工程A";

        const string LIB_DIR = "Library/AvatarGen";
        const string REQUEST_FILE = "depcompiler_request.json";
        const string STATUS_FILE = "depcompiler_status.json";

        static bool s_scheduled, s_running;

        // ───────────────────────── 菜单入口（异步） ─────────────────────────

        [MenuItem("Tools/AvatarGen/DepCompiler/Dry Run")]
        public static void MenuDryRun() { Schedule("dry_run"); }

        [MenuItem("Tools/AvatarGen/DepCompiler/Apply")]
        public static void MenuApply() { Schedule("apply"); }

        /// <summary>把一次执行排到 EditorApplication.delayCall，菜单调用立刻返回。</summary>
        static void Schedule(string defaultMode)
        {
            if (s_running || s_scheduled)
            {
                Debug.LogWarning("[DepCompiler] 已有一次执行在排队/进行中，忽略本次请求（防重发叠加）");
                return;
            }
            s_scheduled = true;
            // 立刻写一份 running，调用方（execute_menu_item 后轮询）不会看到上一次的旧状态
            try
            {
                WriteStatus(Path.Combine(ProjectRoot(), LIB_DIR + "/" + STATUS_FILE),
                            "running", defaultMode, "", 0, null, "");
            }
            catch (Exception e) { Debug.LogWarning("[DepCompiler] 写 status(running) 失败：" + e.Message); }
            EditorApplication.delayCall += delegate { RunFromRequest(defaultMode); };
            Debug.Log("[DepCompiler] 已排队：" + defaultMode + "（读 " + LIB_DIR + "/" + REQUEST_FILE + "）");
        }

        static void RunFromRequest(string defaultMode)
        {
            s_scheduled = false;
            s_running = true;
            var proj = ProjectRoot();
            var reqPath = Path.Combine(proj, LIB_DIR + "/" + REQUEST_FILE);
            var statusPath = Path.Combine(proj, LIB_DIR + "/" + STATUS_FILE);

            string mode = defaultMode;
            string declDir = DefaultDeclDir();
            try
            {
                if (File.Exists(reqPath))
                {
                    var req = AuditJson.Parse(File.ReadAllText(reqPath)) as JsonObject;
                    var m = AuditJson.Str(req, "mode", null);
                    if (!string.IsNullOrEmpty(m)) mode = m;
                    var dd = AuditJson.Str(req, "decl_dir", null);
                    if (!string.IsNullOrEmpty(dd)) declDir = dd;
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning("[DepCompiler] 读请求文件失败（用菜单默认）：" + e.Message);
            }

            var sw = System.Diagnostics.Stopwatch.StartNew();
            WriteStatus(statusPath, "running", mode, declDir, 0, null, "");
            try
            {
                var o = Execute(declDir, mode != "apply");
                sw.Stop();
                WriteStatus(statusPath, "done", mode, declDir, sw.ElapsedMilliseconds, o, "");
                Debug.Log("[DepCompiler] " + mode + " 完成 " + sw.ElapsedMilliseconds + " ms\n" + o.ResultText);
            }
            catch (Exception e)
            {
                sw.Stop();
                WriteStatus(statusPath, "error", mode, declDir, sw.ElapsedMilliseconds, null, e.ToString());
                Debug.LogError("[DepCompiler] 异常：" + e);
            }
            finally
            {
                s_running = false;
            }
        }

        public static string DefaultDeclDir()
        {
            var proj = Directory.GetParent(Application.dataPath).FullName;
            return Path.Combine(proj, "_感知");
        }

        static string ProjectRoot() { return Directory.GetParent(Application.dataPath).FullName; }

        // ───────────────────────── 主入口 ─────────────────────────

        /// <summary>
        /// ⚠ 只供菜单内部调用（RunFromRequest）。别从 execute_code 直接调 apply：
        ///   MCP 超时会重发同一段代码，而 apply 不是幂等操作（AJ 事故：4 次 → 38 MB 控制器）。
        /// </summary>
        public static string Run(string projectDeclDir, bool dryRun)
        {
            var o = Execute(projectDeclDir, dryRun);
            return o.PlanText + Environment.NewLine + o.ResultText;
        }

        public sealed class RunOutcome
        {
            public bool DryRun;
            public string PlanText = "", ResultText = "";
            public int Layers = -1, ActualTransitions = -1, ExpectedTransitions = -1, ScCount = -1, ClipCount = -1;
            public bool TransitionMismatch;
        }

        /// <summary>projectDeclDir = &lt;工程&gt;/_感知（内含 decl.json 与 out/inventory.json）或 decl.json 本身。</summary>
        static RunOutcome Execute(string projectDeclDir, bool dryRun)
        {
            var o = new RunOutcome { DryRun = dryRun };
            string declPath = projectDeclDir;
            if (Directory.Exists(declPath)) declPath = Path.Combine(projectDeclDir, "decl.json");
            if (!File.Exists(declPath))
            {
                o.ResultText = "[DepCompiler] 找不到 decl.json：" + declPath;
                return o;
            }
            var declDir = Path.GetDirectoryName(declPath);
            var invPath = Path.Combine(declDir, "out/inventory.json");
            var writersPath = Path.Combine(declDir, "gen_writers.json");

            var doc = DeclDoc.LoadFile(declPath);
            var sha = DepPlan.Sha256(File.ReadAllText(declPath));
            var inv = InventoryIndex.Load(invPath);

            var ctrl = AssetDatabase.LoadAssetAtPath<AnimatorController>(CONTROLLER_PATH);
            string[] layerNames = null;
            if (ctrl != null)
            {
                var ls = ctrl.layers;
                layerNames = new string[ls.Length];
                for (int i = 0; i < ls.Length; i++) layerNames[i] = ls[i].name;
            }
            var plan = DepPlan.Build(doc, declPath, sha, inv, layerNames, CONTROLLER_PATH);

            o.PlanText = plan.Render();
            o.ExpectedTransitions = plan.TotalTransitions;
            o.ClipCount = plan.Clip.Count;
            o.ScCount = 0;
            for (int i = 0; i < plan.Sc.Count; i++) o.ScCount += plan.Sc[i].HostPaths.Count;
            if (ctrl != null) o.Layers = ctrl.layers.Length;

            if (dryRun)
            {
                o.ResultText = "(dry-run：未改动场景/控制器)";
                o.ActualTransitions = plan.TotalTransitions;
                return o;
            }

            var sb = new StringBuilder();
            if (ctrl == null)
            {
                sb.AppendLine();
                sb.AppendLine("!! 找不到控制器 " + CONTROLLER_PATH + "：只做 sc 后端，clip 全部跳过");
            }
            var avatarRoot = ResolveAvatarRoot(doc.Avatar.Root);
            if (avatarRoot == null)
            {
                sb.AppendLine();
                sb.AppendLine("!! 场景里找不到头像根 " + doc.Avatar.Root + "：中止 apply");
                o.ResultText = sb.ToString();
                return o;
            }

            var log = new StringBuilder();
            var existing = LoadEntries(writersPath);
            var recordedClipLayers = new List<string>();
            foreach (var e in existing)
                if (e.Backend == "clip" && !string.IsNullOrEmpty(e.Layer)) recordedClipLayers.Add(e.Layer);

            int scCreated = 0, scReused = 0, scDeleted = 0, scMismatch = 0, clipLayers = 0;
            int removedLayers = 0, deletedClips = 0, purgedSm = 0;
            List<JsonObject> newEntries;
            List<ModularAvatarShapeChanger> scComps;

            AssetDatabase.StartAssetEditing();
            try
            {
                // 1) 先按规范化层名对账，删掉本工具自产的旧 clip 层（含历史 `.`/`_` 变体）
                if (ctrl != null) removedLayers = RemoveOurLayers(ctrl, plan, recordedClipLayers);
                // 2) 删掉本工具自产的旧 clip 资产（含重命名前的孤儿）
                deletedClips = DeleteOurClipAssets();
                // 3) sc：按指纹复用/重建
                newEntries = ApplySc(plan, existing, avatarRoot, log,
                                     out scCreated, out scReused, out scDeleted, out scMismatch, out scComps);
                // 4) clip：全部重建
                if (ctrl != null)
                {
                    foreach (var w in plan.Clip)
                    {
                        var layer = CreateClipLayer(ctrl, w, avatarRoot, log);
                        newEntries.Add(ClipEntry(w, layer, avatarRoot));
                        clipLayers++;
                    }
                    EnsureParameters(ctrl, plan);
                    EditorUtility.SetDirty(ctrl);
                }
            }
            finally
            {
                AssetDatabase.StopAssetEditing();
            }
            AssetDatabase.SaveAssets();

            // StopAssetEditing 之后才能可靠回读新资产，确认真落盘
            if (ctrl != null) VerifyClipAssets(plan, avatarRoot, log);

            // 5) 清掉 RemoveLayer 可能留下的孤儿状态机子资产（不然控制器文件只涨不缩）
            if (ctrl != null) purgedSm = PurgeOrphanStateMachines();
            if (purgedSm > 0) AssetDatabase.SaveAssets();

            // 6) 回读实际层数/过渡数，与计划比对
            if (ctrl != null)
            {
                o.Layers = ctrl.layers.Length;
                o.ActualTransitions = CountTransitions(ctrl);
                if (o.ActualTransitions != o.ExpectedTransitions)
                {
                    o.TransitionMismatch = true;
                    log.AppendLine("  !! 过渡数不符：计划 " + o.ExpectedTransitions + " 实际 " + o.ActualTransitions
                                   + "（DepCompiler 与 DepPlan 的转移算法不一致，禁止把该控制器当验收通过）");
                }
            }
            o.ScCount = 0;
            for (int i = 0; i < newEntries.Count; i++)
                if (AuditJson.Str(newEntries[i], "backend", "") == "sc") o.ScCount++;

            // 7) SC 改了场景 → 存场景（AJ 版只在内存里，重开就没了）
            if (scCreated + scDeleted > 0)
            {
                var scene = SceneManager.GetActiveScene();
                if (scene.IsValid() && !string.IsNullOrEmpty(scene.path))
                {
                    EditorSceneManager.MarkSceneDirty(scene);
                    EditorSceneManager.SaveScene(scene);
                    log.AppendLine("  scene saved: " + scene.path);
                }
            }

            // 8) 场景存盘后再取一次 GlobalObjectId（新对象在存盘前可能还没有最终 fileID），
            //    这样 gen_writers.json 里的 id 与下一轮解析到的必然一致。
            for (int i = 0; i < scComps.Count && i < newEntries.Count; i++)
                newEntries[i].Set("global_object_id", GlobalObjectId.GetGlobalObjectIdSlow(scComps[i]).ToString());

            newEntries.Sort(delegate (JsonObject a, JsonObject b)
            {
                return string.CompareOrdinal(EntrySortKey(a), EntrySortKey(b));
            });
            WriteEntries(writersPath, sha, newEntries);

            log.AppendLine("  sc: created=" + scCreated + " reused=" + scReused + " deleted=" + scDeleted
                           + " fingerprint_mismatch=" + scMismatch);
            log.AppendLine("  clip layers: " + clipLayers + " (removed old=" + removedLayers + ", deleted clip assets=" + deletedClips + ")");
            log.AppendLine("  transitions: 计划=" + o.ExpectedTransitions + " 实际=" + o.ActualTransitions
                           + (o.TransitionMismatch ? "  ✗" : "  ✓"));
            log.AppendLine("  controller layers: " + o.Layers);

            sb.AppendLine();
            sb.AppendLine("---- apply ----");
            sb.AppendLine(log.ToString().TrimEnd());
            sb.AppendLine("gen_writers.json -> " + writersPath + "  (" + newEntries.Count + " entries)");
            o.ResultText = sb.ToString();
            return o;
        }

        // ───────────────────────── ShapeChanger（sc 后端） ─────────────────────────

        static List<JsonObject> ApplySc(DepPlanResult plan, List<ExistingEntry> existing,
                                        GameObject avatarRoot, StringBuilder log,
                                        out int created, out int reused, out int deleted, out int mismatched,
                                        out List<ModularAvatarShapeChanger> comps)
        {
            var outEntries = new List<JsonObject>();
            comps = new List<ModularAvatarShapeChanger>();
            created = 0; reused = 0; deleted = 0; mismatched = 0;

            var scByKey = new Dictionary<string, ExistingEntry>(StringComparer.Ordinal);
            foreach (var e in existing)
                if (e.Backend == "sc")
                    scByKey[e.DepId + "\u0001" + e.HostPath] = e;

            foreach (var w in plan.Sc)
            {
                for (int h = 0; h < w.HostPaths.Count; h++)
                {
                    var hostPath = w.HostPaths[h];
                    var key = w.DepId + "\u0001" + hostPath;
                    ExistingEntry ex;
                    ModularAvatarShapeChanger comp = null;
                    bool keep = false;
                    string compFp = "";

                    if (scByKey.TryGetValue(key, out ex))
                    {
                        var obj = ResolveGlobalObject(ex.GlobalObjectId);
                        var old = obj as ModularAvatarShapeChanger;
                        if (old != null)
                        {
                            compFp = ComponentFingerprint(old, avatarRoot);
                            if (compFp != ex.ComponentFingerprint)
                            {
                                // 外部改过这个自产 SC：按规矩不删，只报
                                mismatched++;
                                log.AppendLine("  ! " + w.DepId + "@" + hostPath + "：组件指纹不符（期望 "
                                               + Short(ex.ComponentFingerprint) + " 实为 " + Short(compFp) + "），保留不动");
                                comp = old; keep = true;
                            }
                            else if (ex.Fingerprint == w.Fingerprint)
                            {
                                comp = old; keep = true; reused++;
                            }
                            else
                            {
                                Undo.DestroyObjectImmediate(old);
                                deleted++;
                            }
                        }
                    }

                    var go = Find(avatarRoot, hostPath);
                    if (go == null)
                    {
                        log.AppendLine("  ! 找不到宿主 " + hostPath + "（" + w.DepId + "）");
                        continue;
                    }
                    if (!keep || comp == null)
                    {
                        comp = CreateSc(go, w, avatarRoot, log);
                        created++;
                    }
                    var fp = ComponentFingerprint(comp, avatarRoot);
                    outEntries.Add(ScEntry(w, hostPath, comp, fp, avatarRoot));
                    comps.Add(comp);
                }
            }
            return outEntries;
        }

        static string EntrySortKey(JsonObject e)
        {
            return AuditJson.Str(e, "backend", "") + "|" + AuditJson.Str(e, "dep_id", "") + "|"
                   + AuditJson.Str(e, "host_path", AuditJson.Str(e, "layer", ""));
        }

        static string Short(string s) { return string.IsNullOrEmpty(s) || s.Length < 8 ? s : s.Substring(0, 8); }

        static ModularAvatarShapeChanger CreateSc(GameObject host, ScWriter w, GameObject root, StringBuilder log)
        {
            var comp = Undo.AddComponent<ModularAvatarShapeChanger>(host);
            var shapes = new List<ChangedShape>();
            foreach (var t in w.Targets)
            {
                var go = Find(root, t.Path);
                if (go == null) { log.AppendLine("  ! SC 目标找不到 " + t.Path + "（" + w.DepId + "）"); continue; }
                var shapeName = t.Property.StartsWith("blendShape.", StringComparison.Ordinal)
                    ? t.Property.Substring("blendShape.".Length) : t.Property;
                shapes.Add(new ChangedShape
                {
                    Object = new AvatarObjectReference(go),
                    ShapeName = shapeName,
                    ChangeType = ShapeChangeType.Set,
                    Value = t.On
                });
            }
            comp.Shapes = shapes;
            EditorUtility.SetDirty(comp);
            Undo.SetCurrentGroupName("DepCompiler: " + w.DepId);
            return comp;
        }

        static string ComponentFingerprint(ModularAvatarShapeChanger comp, GameObject root)
        {
            var lines = new List<string>();
            var shapes = comp.Shapes;
            if (shapes != null)
                foreach (var s in shapes)
                {
                    string p = "?";
                    if (s.Object != null)
                    {
                        var go = s.Object.Get(comp);
                        if (go != null) p = Rel(root.transform, go.transform);
                    }
                    lines.Add(p + "|" + s.ShapeName + "|" + (int)s.ChangeType + "|"
                              + s.Value.ToString("0.######", CultureInfo.InvariantCulture));
                }
            lines.Sort(StringComparer.Ordinal);
            return DepPlan.Sha256(string.Join("\n", lines.ToArray()));
        }

        static object ResolveGlobalObject(string id)
        {
            if (string.IsNullOrEmpty(id)) return null;
            GlobalObjectId gid;
            if (!GlobalObjectId.TryParse(id, out gid)) return null;
            return GlobalObjectId.GlobalObjectIdentifierToObjectSlow(gid);
        }

        // ───────────────────────── clip 后端 ─────────────────────────

        static AnimatorControllerLayer CreateClipLayer(AnimatorController ctrl, ClipWriter w, GameObject root, StringBuilder log)
        {
            var off = BuildClip(w, false, root);
            var on = BuildClip(w, true, root);
            SaveClipAsset(off, ClipPath(w, "Off"), log);
            SaveClipAsset(on, ClipPath(w, "On"), log);

            ctrl.AddLayer(w.LayerName);
            var arr = ctrl.layers;
            var layer = arr[arr.Length - 1];
            layer.defaultWeight = 1f;
            int idx = arr.Length - 1;
            if (w.LayerIndexHint >= 0 && w.LayerIndexHint < arr.Length) idx = w.LayerIndexHint;
            if (idx != arr.Length - 1)
            {
                for (int i = arr.Length - 1; i > idx; i--) arr[i] = arr[i - 1];
                arr[idx] = layer;
            }
            ctrl.layers = arr;

            var sm = layer.stateMachine;
            var sOff = sm.AddState("Off"); sOff.motion = off; sOff.writeDefaultValues = false;
            var sOn = sm.AddState("On"); sOn.motion = on; sOn.writeDefaultValues = false;
            sm.defaultState = w.DefaultOn ? sOn : sOff;

            AddTransitions(sOff, sOn, w.OffToOn);
            AddTransitions(sOn, sOff, w.OnToOff);
            log.AppendLine("  [clip] " + layer.name + "  off→on=" + w.OffToOn.Count + " on→off=" + w.OnToOff.Count
                           + " total=" + w.ExpectedTransitions
                           + "  default=" + (w.DefaultOn ? "On" : "Off")
                           + "  targets=" + w.Targets.Count);
            return layer;
        }

        static void AddTransitions(AnimatorState from, AnimatorState to, List<List<Cond>> clauses)
        {
            for (int i = 0; i < clauses.Count; i++)
            {
                var cl = clauses[i];
                if (cl.Count == 0) continue; // 永真不建（由默认状态承担）
                var t = from.AddTransition(to);
                t.hasExitTime = false;
                t.duration = 0f;
                for (int j = 0; j < cl.Count; j++)
                    t.AddCondition(ToAnimatorMode(cl[j].Mode), cl[j].Threshold, cl[j].Param);
            }
        }

        static AnimatorConditionMode ToAnimatorMode(CondMode m)
        {
            switch (m)
            {
                case CondMode.IfNot: return AnimatorConditionMode.IfNot;
                case CondMode.Greater: return AnimatorConditionMode.Greater;
                case CondMode.Less: return AnimatorConditionMode.Less;
                default: return AnimatorConditionMode.If;
            }
        }

        static AnimationClip BuildClip(ClipWriter w, bool onState, GameObject root)
        {
            var clip = new AnimationClip { name = w.FileStem + (onState ? "_On" : "_Off"), frameRate = 60f };
            foreach (var t in w.Targets)
            {
                // 显隐件：Off 态必须**什么都不写**（WD=OFF 透传给下层），否则会把部位开关压死。
                // 这正是 SOP 层序与压制.md「配饰关闭时那个状态必须什么都不写」的写法。
                if (!onState && t.ActiveSelf) continue;
                float v = onState ? t.On : t.Off;
                var realPath = ResolveRel(root, t.Path) ?? t.Path;
                var type = CurveType(t, root);
                AnimationUtility.SetEditorCurve(clip,
                    EditorCurveBinding.FloatCurve(realPath, type, t.Property), Step(v));
            }
            return clip;
        }

        static Type CurveType(WriterTarget t, GameObject root)
        {
            if (t.Property.StartsWith("blendShape.", StringComparison.Ordinal)) return typeof(SkinnedMeshRenderer);
            if (t.Property == "m_Enabled")
            {
                var go = Find(root, t.Path);
                if (go != null)
                {
                    var smr = go.GetComponent<SkinnedMeshRenderer>();
                    if (smr != null) return typeof(SkinnedMeshRenderer);
                    var r = go.GetComponent<Renderer>();
                    if (r != null) return r.GetType();
                }
                return typeof(SkinnedMeshRenderer);
            }
            return typeof(GameObject);
        }

        static AnimationCurve Step(float v)
        {
            var c = new AnimationCurve();
            c.AddKey(new Keyframe(0f, v, float.PositiveInfinity, float.PositiveInfinity));
            c.AddKey(new Keyframe(1f / 60f, v, float.PositiveInfinity, float.PositiveInfinity));
            return c;
        }

        static void SaveClipAsset(AnimationClip clip, string path, StringBuilder log)
        {
            int want = AnimationUtility.GetCurveBindings(clip).Length;
            var dir = Path.GetDirectoryName(path);
            if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);
            if (AssetDatabase.LoadAssetAtPath<AnimationClip>(path) != null) AssetDatabase.DeleteAsset(path);
            AssetDatabase.CreateAsset(clip, path);
            // 批处理期间 LoadAssetAtPath 可能看不到新资产；回读校验放到 StopAssetEditing 之后
            // （见 Execute 末尾的 VerifyClipAssets）。
            if (want == 0) log.AppendLine("  ! clip 无曲线 " + path);
        }

        /// <summary>StopAssetEditing 之后逐 clip 回读曲线条数，确认真的落盘（不在批处理里读）。</summary>
        static void VerifyClipAssets(DepPlanResult plan, GameObject root, StringBuilder log)
        {
            for (int i = 0; i < plan.Clip.Count; i++)
            {
                var w = plan.Clip[i];
                for (int k = 0; k < 2; k++)
                {
                    bool on = k == 1;
                    var path = ClipPath(w, on ? "On" : "Off");
                    var back = AssetDatabase.LoadAssetAtPath<AnimationClip>(path);
                    if (back == null) { log.AppendLine("  ! clip 未落盘 " + path); continue; }
                    var want = BuildClip(w, on, root);
                    int wantN = AnimationUtility.GetCurveBindings(want).Length;
                    int gotN = AnimationUtility.GetCurveBindings(back).Length;
                    if (wantN != gotN)
                        log.AppendLine("  ! clip 落盘回读条数不符 " + path + " want=" + wantN + " got=" + gotN);
                }
            }
        }

        static string ClipPath(ClipWriter w, string state)
        {
            return CLIP_DIR + "/" + w.FileStem + "_" + state + ".anim";
        }

        static void EnsureParameters(AnimatorController ctrl, DepPlanResult plan)
        {
            var need = new Dictionary<string, AnimatorControllerParameterType>();
            foreach (var w in plan.Clip)
            {
                var d = w.OnExpr.Normalized();
                foreach (var cl in d.Clauses)
                    foreach (var c in cl)
                    {
                        var type = (c.Mode == CondMode.Greater || c.Mode == CondMode.Less)
                            ? AnimatorControllerParameterType.Float : AnimatorControllerParameterType.Bool;
                        if (!need.ContainsKey(c.Param)) need[c.Param] = type;
                    }
            }
            foreach (var kv in need)
            {
                if (ctrl.parameters.Any(p => p.name == kv.Key)) continue;
                ctrl.AddParameter(kv.Key, kv.Value);
            }
        }

        // ───────────────────────── 幂等：删旧层 / 旧资产 / 孤儿 ─────────────────────────

        /// <summary>按「规范化层名 + gen_writers 记录」删本工具自产的 clip 层（含历史 `.`→`_` 变体）。</summary>
        static int RemoveOurLayers(AnimatorController ctrl, DepPlanResult plan, List<string> recordedClipLayers)
        {
            var wanted = new HashSet<string>(StringComparer.Ordinal);
            for (int i = 0; i < plan.Clip.Count; i++) wanted.Add(DepPlan.SafeBody(plan.Clip[i].DepId));
            for (int i = 0; i < recordedClipLayers.Count; i++)
            {
                var n = recordedClipLayers[i] ?? "";
                if (n.StartsWith(DepPlan.LayerPrefix, StringComparison.Ordinal))
                    n = n.Substring(DepPlan.LayerPrefix.Length);
                wanted.Add(DepPlan.SafeBody(n));
            }
            if (wanted.Count == 0) return 0;

            int removed = 0;
            var arr = ctrl.layers;
            for (int i = arr.Length - 1; i >= 0; i--)
            {
                var name = arr[i].name ?? "";
                if (!name.StartsWith(DepPlan.LayerPrefix, StringComparison.Ordinal)) continue;
                var body = name.Substring(DepPlan.LayerPrefix.Length);
                if (wanted.Contains(body) || wanted.Contains(DepPlan.SafeBody(body)))
                {
                    ctrl.RemoveLayer(i);
                    removed++;
                }
            }
            return removed;
        }

        static int DeleteOurClipAssets()
        {
            if (!AssetDatabase.IsValidFolder(CLIP_DIR)) return 0;
            int n = 0;
            var guids = AssetDatabase.FindAssets("t:AnimationClip", new[] { CLIP_DIR });
            for (int i = 0; i < guids.Length; i++)
            {
                var p = AssetDatabase.GUIDToAssetPath(guids[i]);
                if (Path.GetFileName(p).StartsWith("Decl_", StringComparison.Ordinal))
                {
                    AssetDatabase.DeleteAsset(p);
                    n++;
                }
            }
            return n;
        }

        /// <summary>
        /// RemoveLayer 在部分 Unity 版本会把状态机子资产留在 .controller 里（文件只涨不缩），这里清孤儿。
        /// 只清「未挂到任何层」且「名字属于本工具 Decl: 前缀」的状态机 —— 绝不碰其它工具的层。
        /// </summary>
        static int PurgeOrphanStateMachines()
        {
            var ctrl = AssetDatabase.LoadAssetAtPath<AnimatorController>(CONTROLLER_PATH);
            if (ctrl == null) return 0;
            var live = new HashSet<int>();
            var layers = ctrl.layers;
            for (int i = 0; i < layers.Length; i++) MarkStateMachine(layers[i].stateMachine, live);

            int purged = 0;
            var all = AssetDatabase.LoadAllAssetsAtPath(CONTROLLER_PATH);
            for (int i = 0; i < all.Length; i++)
            {
                var sm = all[i] as AnimatorStateMachine;
                if (sm == null) continue;
                if (live.Contains(sm.GetInstanceID())) continue;
                if (string.IsNullOrEmpty(sm.name) || !sm.name.StartsWith(DepPlan.LayerPrefix, StringComparison.Ordinal)) continue;
                UnityEngine.Object.DestroyImmediate(sm, true);
                purged++;
            }
            return purged;
        }

        static void MarkStateMachine(AnimatorStateMachine sm, HashSet<int> live)
        {
            if (sm == null || !live.Add(sm.GetInstanceID())) return;
            var states = sm.states;
            for (int i = 0; i < states.Length; i++)
                if (states[i].state != null) live.Add(states[i].state.GetInstanceID());
            var subs = sm.stateMachines;
            for (int i = 0; i < subs.Length; i++) MarkStateMachine(subs[i].stateMachine, live);
        }

        static int CountTransitions(AnimatorController ctrl)
        {
            int n = 0;
            var layers = ctrl.layers;
            for (int i = 0; i < layers.Length; i++)
            {
                var name = layers[i].name ?? "";
                if (!name.StartsWith(DepPlan.LayerPrefix, StringComparison.Ordinal)) continue;
                var sm = layers[i].stateMachine;
                if (sm == null) continue;
                var states = sm.states;
                for (int j = 0; j < states.Length; j++)
                {
                    var st = states[j].state;
                    if (st == null) continue;
                    n += st.transitions != null ? st.transitions.Length : 0;
                }
            }
            return n;
        }

        // ───────────────────────── 场景解析 ─────────────────────────

        static GameObject ResolveAvatarRoot(string name)
        {
            var roots = SceneManager.GetActiveScene().GetRootGameObjects();
            GameObject fb = null;
            foreach (var g in roots)
            {
                if (!string.IsNullOrEmpty(name) && g.name == name) return g;
                if (fb == null && g.name == AVATAR_FALLBACK) fb = g;
            }
            if (fb != null) return fb;
            foreach (var g in roots)
            {
                if (g.GetComponentInChildren<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>(true) != null) return g;
            }
            return null;
        }

        static GameObject Find(GameObject root, string path)
        {
            if (root == null) return null;
            if (string.IsNullOrEmpty(path) || path == ".") return root;
            var t = root.transform.Find(path);
            if (t != null) return t.gameObject;
            // mesh: 字段可能是「名字」而不是相对路径（如 Body_b）——按名字在子树里找唯一者
            if (path.IndexOf('/') < 0)
            {
                var all = root.GetComponentsInChildren<Transform>(true);
                GameObject hit = null;
                foreach (var c in all)
                {
                    if (c.name != path) continue;
                    if (hit != null) return null; // 重名不猜
                    hit = c.gameObject;
                }
                return hit;
            }
            return null;
        }

        /// <summary>把声明里的逻辑路径/名字解析成 Animator 曲线相对头像根的真实路径。</summary>
        static string ResolveRel(GameObject root, string logical)
        {
            var go = Find(root, logical);
            return go != null ? Rel(root.transform, go.transform) : null;
        }

        static string Rel(Transform root, Transform t)
        {
            if (t == null) return "?";
            if (t == root) return ".";
            var stack = new List<string>();
            var cur = t;
            while (cur != null && cur != root) { stack.Add(cur.name); cur = cur.parent; }
            if (cur == null) return t.name;
            stack.Reverse();
            return string.Join("/", stack.ToArray());
        }

        // ───────────────────────── gen_writers.json ─────────────────────────

        sealed class ExistingEntry
        {
            public string DepId, Backend, HostPath, Layer, GlobalObjectId, ComponentFingerprint, Fingerprint;
        }

        static List<ExistingEntry> LoadEntries(string path)
        {
            var res = new List<ExistingEntry>();
            if (!File.Exists(path)) return res;
            try
            {
                var root = AuditJson.Parse(File.ReadAllText(path)) as JsonObject;
                var arr = AuditJson.Arr(root, "entries");
                foreach (var v in arr)
                {
                    var o = v as JsonObject;
                    if (o == null) continue;
                    res.Add(new ExistingEntry
                    {
                        DepId = AuditJson.Str(o, "dep_id", ""),
                        Backend = AuditJson.Str(o, "backend", ""),
                        HostPath = AuditJson.Str(o, "host_path", ""),
                        Layer = AuditJson.Str(o, "layer", ""),
                        GlobalObjectId = AuditJson.Str(o, "global_object_id", ""),
                        ComponentFingerprint = AuditJson.Str(o, "component_fingerprint", ""),
                        Fingerprint = AuditJson.Str(o, "fingerprint", "")
                    });
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning("[DepCompiler] gen_writers.json 解析失败（当作无旧产物）：" + e.Message);
            }
            return res;
        }

        static JsonObject ScEntry(ScWriter w, string hostPath, ModularAvatarShapeChanger comp, string compFp, GameObject root)
        {
            var e = new JsonObject();
            e.Set("dep_id", w.DepId);
            e.Set("backend", "sc");
            e.Set("host_path", hostPath);
            e.Set("global_object_id", GlobalObjectId.GetGlobalObjectIdSlow(comp).ToString());
            e.Set("component_fingerprint", compFp);
            e.Set("fingerprint", w.Fingerprint);
            e.Set("targets", TargetJson(w.Targets, root));
            return e;
        }

        static JsonObject ClipEntry(ClipWriter w, AnimatorControllerLayer layer, GameObject root)
        {
            var e = new JsonObject();
            e.Set("dep_id", w.DepId);
            e.Set("backend", "clip");
            // 记实际写进控制器的层名（layer.name 回读），不是请求名 —— 对账只认它
            e.Set("layer", layer != null ? layer.name : w.LayerName);
            e.Set("default_state", w.DefaultOn ? "On" : "Off");
            e.Set("on_expr", w.OnExprText);
            e.Set("transitions", w.ExpectedTransitions);
            e.Set("fingerprint", w.Fingerprint);
            e.Set("targets", TargetJson(w.Targets, root));
            return e;
        }

        static List<object> TargetJson(List<WriterTarget> ts, GameObject root)
        {
            var list = new List<object>();
            foreach (var t in ts)
            {
                var o = new JsonObject();
                o.Set("path", t.Path);
                o.Set("resolved_path", ResolveRel(root, t.Path) ?? t.Path);
                o.Set("property", t.Property);
                o.Set("on", t.On);
                o.Set("off", t.Off);
                list.Add(o);
            }
            return list;
        }

        static void WriteEntries(string path, string declSha, List<JsonObject> entries)
        {
            var root = new JsonObject();
            root.Set("tool", "dep_compiler");
            root.Set("decl_sha256", declSha);
            root.Set("controller", CONTROLLER_PATH);
            var list = new List<object>();
            foreach (var e in entries) list.Add(e);
            root.Set("entries", list);
            AuditJson.WriteFile(path, root);
        }

        // ───────────────────────── 状态文件 ─────────────────────────

        static void WriteStatus(string path, string state, string mode, string declDir,
                                long elapsedMs, RunOutcome o, string error)
        {
            var root = new JsonObject();
            root.Set("state", state);
            root.Set("mode", mode);
            root.Set("decl_dir", declDir);
            root.Set("elapsed_ms", elapsedMs);
            root.Set("layers", o != null ? o.Layers : -1);
            root.Set("transitions", o != null ? o.ActualTransitions : -1);
            root.Set("transitions_expected", o != null ? o.ExpectedTransitions : -1);
            root.Set("sc", o != null ? o.ScCount : -1);
            root.Set("clip", o != null ? o.ClipCount : -1);
            root.Set("transition_mismatch", o != null && o.TransitionMismatch);
            root.Set("plan", o != null ? o.PlanText : "");
            root.Set("result", o != null ? o.ResultText : "");
            root.Set("error", error ?? "");
            AuditJson.WriteFile(path, root);
        }
    }
}

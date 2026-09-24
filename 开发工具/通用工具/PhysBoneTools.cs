// ══════════════════════════════════════════════════════════════════
// 【开发工具】通用工具
// 适用素体：任意
// 相关素材：AAO (Avatar Optimizer，可选) / AvatarPoseSystem
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4 / AAO 1.9.x
// 可复用性：★★★ 自动识别头像，换单直接能用（ShedPhysBones 需改开头目标表）
// 用途　　：PhysBone 工具合集：审计（清点/Dump）、查删重复、挂 AAO MergePhysBone（同父组/精确点名）、编辑期硬合并、压到 256 上限内
// ══════════════════════════════════════════════════════════════════
// 2026-09-25 由 7 个文件合并（kit-prep 整理）：DedupePhysBones / HardMergePhysBones /
// MergePhysBoneExplicit / MergePhysBoneGroups / ShedPhysBones / PhysBoneCensus / DumpPhysBones。
// 每个原文件是下面一个独立的 namespace 块，using 留在块内，**原类名、公开方法、菜单路径与优先级全部不变**，
// 所以 `-executeMethod AvatarGen.DumpPhysBones.Dump` 之类的旧调用、工程里 `AvatarGen.PhysBoneCensus.Run()`
// 的直接调用照常可用。新增的只有门面类 PhysBoneTools（统一入口 + 「审计」菜单）。
// FixAaoMergePhysBone.cs 保持独立（它是构建前体检，不是 PhysBone 操作）。
//
// ⚠ 拷进工程时：本文件与旧的 7 个单文件**二选一**，同时存在会因类名重复编译失败。
//
// 菜单（均在 Tools/AvatarGen/ 下）            → 静态入口（可 -executeMethod）
//   Perf - PhysBone 审计（清点+Dump）  339    → AvatarGen.PhysBoneTools.Audit        （新增：依次跑下两项）
//   Perf - PhysBone 清点                339    → AvatarGen.PhysBoneCensus.Run
//   Perf - Dump PhysBone                326    → AvatarGen.DumpPhysBones.Dump
//   Perf - 检查重复 PhysBone            327    → AvatarGen.DedupePhysBones.Check
//   Perf - 清理重复 PhysBone            328    → AvatarGen.DedupePhysBones.Apply
//   Perf - 清理重复 PhysBone（改预制体资产）329 → AvatarGen.DedupePhysBones.ApplyToPrefabAsset
//   Perf - 分析可合并 PhysBone          334    → AvatarGen.MergePhysBoneGroups.Analyze
//   Perf - 挂 AAO MergePhysBone         335    → AvatarGen.MergePhysBoneGroups.Apply
//   Perf - 精确合并 PhysBone            337    → AvatarGen.MergePhysBoneExplicit.Apply
//   Perf - 压 PhysBone 到上限内         338    → AvatarGen.ShedPhysBones.Run
//   Perf - 硬合并 PhysBone（分析）      342    → AvatarGen.HardMergePhysBones.Analyze
//   Perf - 硬合并 PhysBone（执行）      343    → AvatarGen.HardMergePhysBones.Apply
//   门面 AvatarGen.PhysBoneTools.<同名方法> 与上表一一转发，二者等价。

namespace AvatarGen
{
    /// <summary>PhysBone 工具合集的统一入口：只做转发，实现在下面各原类里。</summary>
    public static class PhysBoneTools
    {
        [UnityEditor.MenuItem("Tools/AvatarGen/Perf - PhysBone 审计（清点+Dump）", false, 339)]
        public static void Audit()
        {
            PhysBoneCensus.Run();   // 按顶层子物体分组清点，结果 Captures/physbone_census.txt
            DumpPhysBones.Dump();   // 每根 PB 的影响骨骼数 × 碰撞体数
        }
        public static void Census() => PhysBoneCensus.Run();
        public static void Dump() => DumpPhysBones.Dump();
        public static void DedupeCheck() => DedupePhysBones.Check();
        public static void DedupeApply() => DedupePhysBones.Apply();
        public static void DedupeApplyToPrefabAsset() => DedupePhysBones.ApplyToPrefabAsset();
        public static void MergeGroupsAnalyze() => MergePhysBoneGroups.Analyze();
        public static void MergeGroupsApply() => MergePhysBoneGroups.Apply();
        public static void MergeExplicitApply() => MergePhysBoneExplicit.Apply();
        public static void Shed() => ShedPhysBones.Run();
        public static void HardMergeAnalyze() => HardMergePhysBones.Analyze();
        public static void HardMergeApply() => HardMergePhysBones.Apply();
    }
}

// ────────────────────────────────────────────────────────────────
// 以下原 PhysBoneCensus.cs（2026-09-25 并入 PhysBoneTools.cs；类名、方法、菜单路径不变）
// ────────────────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════
// 【开发工具】通用工具
// 适用素体：任意
// 相关素材：AvatarPoseSystem / AAO
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4
// 可复用性：★★★ 自动识别头像，换单直接能用
// 用途　　：把编辑期 PhysBone 按顶层子物体分组清点，找出压到 256 上限内的下手点
// ══════════════════════════════════════════════════════════════════
// 插件（如 APS）会在自己的 NDMF pass 里按**编辑期**数量判上限，
// AAO 的事后优化救不了。所以要先知道数量堆在哪儿。
namespace AvatarGen
{
    using System.Collections.Generic;
    using System.Linq;
    using System.Text;
    using UnityEngine;
    using UnityEditor;
    using VRC.SDK3.Dynamics.PhysBone.Components;

    public static class PhysBoneCensus
    {
        static GameObject FindAvatar()
        {
            var sel = Selection.activeGameObject;
            if (sel != null)
            {
                var d0 = sel.GetComponentInParent<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
                if (d0 != null) return d0.gameObject;
            }
            var all = Object.FindObjectsOfType<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
            foreach (var d in all) if (d.gameObject.activeInHierarchy) return d.gameObject;
            return all.Length > 0 ? all[0].gameObject : null;
        }

        [MenuItem("Tools/AvatarGen/Perf - PhysBone 清点", false, 339)]
        public static void Run()
        {
            var go = FindAvatar();
            if (go == null) { Debug.LogError("[Census] 找不到头像"); return; }
            var pbs = go.GetComponentsInChildren<VRCPhysBone>(true);
            var sb = new StringBuilder();
            sb.AppendLine($"[Census] 头像 {go.name}   编辑期 PhysBone 合计 {pbs.Length} 个");
            sb.AppendLine($"  APS 判定式：编辑期数 + APS 生成数 ≤ 256");
            sb.AppendLine();

            // 按「头像根下的第一层子物体」归类
            var byTop = new Dictionary<string, List<VRCPhysBone>>();
            foreach (var pb in pbs)
            {
                var t = pb.transform;
                while (t.parent != null && t.parent != go.transform) t = t.parent;
                var k = t == go.transform ? "(直接挂在根上)" : t.name;
                if (!byTop.TryGetValue(k, out var l)) byTop[k] = l = new List<VRCPhysBone>();
                l.Add(pb);
            }

            sb.AppendLine("=== 按顶层子物体分布 ===");
            foreach (var kv in byTop.OrderByDescending(k => k.Value.Count))
            {
                var top = go.transform.Find(kv.Key);
                var act = top != null && top.gameObject.activeSelf ? "●启用" : "○停用";
                sb.AppendLine($"  {kv.Value.Count,4} 个  {act}  {kv.Key}");
            }

            // 同父同设置的可合并组（含只有 2 根的）
            sb.AppendLine();
            sb.AppendLine("=== 同父兄弟组（硬合并后每组只留 1 根）===");
            var groups = pbs.Where(p => p.transform.parent != null)
                            .GroupBy(p => p.transform.parent)
                            .Where(g => g.Count() >= 2)
                            .OrderByDescending(g => g.Count()).ToList();
            int potential = 0;
            foreach (var g in groups.Take(20))
            {
                var path = AnimationUtility.CalculateTransformPath(g.Key, go.transform);
                int nonPbChildren = g.Key.Cast<Transform>().Count(c => c.GetComponent<VRCPhysBone>() == null);
                sb.AppendLine($"  {g.Count(),3} 根 → 1（省 {g.Count() - 1,2}）  父下无PB的子物体 {nonPbChildren} 个   {path}");
                potential += g.Count() - 1;
            }
            sb.AppendLine($"  这些组硬合并合计可省 {potential} 个 → {pbs.Length - potential} 个");

            var dir = System.IO.Path.Combine(System.IO.Directory.GetCurrentDirectory(), "Captures");
            System.IO.Directory.CreateDirectory(dir);
            System.IO.File.WriteAllText(System.IO.Path.Combine(dir, "physbone_census.txt"), sb.ToString());
            Debug.Log("[Census] 明细见 Captures/physbone_census.txt\n" + sb);
        }
    }
}

// ────────────────────────────────────────────────────────────────
// 以下原 DumpPhysBones.cs（2026-09-25 并入 PhysBoneTools.cs；类名、方法、菜单路径不变）
// ────────────────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】通用工具
// 适用素体：任意
// 相关素材：无
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4
// 可复用性：★★★ 自动识别场景里的头像，换单直接能用
// 用途　　：列出每个 VRCPhysBone 的影响骨骼数与碰撞体列表，定位「碰撞检查次数」的来源
// ══════════════════════════════════════════════════════════════════
// VRChat 的 PhysBone Collision Check Count ≈ Σ(每根 PhysBone 的受影响 transform 数 × 它的碰撞体数)。
// 光看组件数看不出问题在哪 —— 一根挂了 20 个碰撞体的长发，比十根不挂碰撞体的还贵。
namespace AvatarGen
{
    using System.Collections.Generic;
    using System.Linq;
    using System.Text;
    using UnityEngine;
    using UnityEditor;
    using VRC.SDK3.Dynamics.PhysBone.Components;

    public static class DumpPhysBones
    {
        static GameObject Avatar()
        {
            var sel = Selection.activeGameObject;
            if (sel != null)
            {
                var d0 = sel.GetComponentInParent<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
                if (d0 != null) return d0.gameObject;
            }
            var all = Object.FindObjectsOfType<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
            var g = all.FirstOrDefault(d => d.gameObject.activeInHierarchy);
            return g != null ? g.gameObject : (all.Length > 0 ? all[0].gameObject : null);
        }

        static string TopGroup(Transform t, Transform root)
        {
            var cur = t;
            while (cur != null && cur.parent != null && cur.parent != root) cur = cur.parent;
            return cur == null ? "(根)" : cur.name;
        }

        // 受影响 transform 数：从 rootTransform 起的子树，减去被 ignoreTransforms 剪掉的分支
        static int AffectedCount(VRCPhysBone pb)
        {
            var root = pb.rootTransform != null ? pb.rootTransform : pb.transform;
            var ignore = new HashSet<Transform>(pb.ignoreTransforms.Where(x => x != null));
            int n = 0;
            void Walk(Transform t)
            {
                if (ignore.Contains(t)) return;
                n++;
                for (int i = 0; i < t.childCount; i++) Walk(t.GetChild(i));
            }
            Walk(root);
            return Mathf.Max(0, n - 1); // 根自身不算一根骨
        }

        [MenuItem("Tools/AvatarGen/Perf - Dump PhysBone", false, 326)]
        public static void Dump()
        {
            var go = Avatar();
            if (go == null) { Debug.LogError("[PB] 场景里找不到头像"); return; }

            var pbs = go.GetComponentsInChildren<VRCPhysBone>(true);
            var cols = go.GetComponentsInChildren<VRCPhysBoneCollider>(true);

            var rows = new List<(string grp, string path, int bones, int colliders, int checks, bool multi)>();
            var perObj = new Dictionary<Transform, int>();
            foreach (var pb in pbs)
                perObj[pb.transform] = perObj.TryGetValue(pb.transform, out var c) ? c + 1 : 1;

            foreach (var pb in pbs)
            {
                int bones = AffectedCount(pb);
                int nc = pb.colliders != null ? pb.colliders.Count(x => x != null) : 0;
                var path = AnimationUtility.CalculateTransformPath(pb.transform, go.transform);
                rows.Add((TopGroup(pb.transform, go.transform), path, bones, nc, bones * nc,
                          perObj[pb.transform] > 1));
            }

            var sb = new StringBuilder();
            sb.AppendLine($"[PB] PhysBone {pbs.Length} 个 · 碰撞体 {cols.Length} 个 · 估算碰撞检查 {rows.Sum(r => r.checks):N0}");
            sb.AppendLine();
            sb.AppendLine("=== 按顶层分组 ===");
            foreach (var g in rows.GroupBy(r => r.grp).OrderByDescending(g => g.Sum(r => r.checks)))
                sb.AppendLine($"  {g.Sum(r => r.checks),7:N0} 检查   {g.Count(),3} 根 PB   {g.Sum(r => r.bones),5} 骨   {g.Key}");

            sb.AppendLine();
            sb.AppendLine("=== 检查次数最高的 30 根 ===");
            sb.AppendLine("   检查     骨  碰撞体  路径");
            foreach (var r in rows.OrderByDescending(r => r.checks).Take(30))
                sb.AppendLine($"  {r.checks,6:N0}  {r.bones,5}  {r.colliders,5}   {r.path}{(r.multi ? "   ★同物体多个PB" : "")}");

            sb.AppendLine();
            sb.AppendLine("=== 碰撞体分布（按顶层分组）===");
            foreach (var g in cols.GroupBy(c => TopGroup(c.transform, go.transform)).OrderByDescending(g => g.Count()))
                sb.AppendLine($"  {g.Count(),3} 个   {g.Key}");

            int noCol = rows.Count(r => r.colliders == 0);
            sb.AppendLine();
            sb.AppendLine($"不挂任何碰撞体的 PhysBone：{noCol} / {rows.Count}（这些不产生碰撞检查开销）");

            var dir = System.IO.Path.Combine(System.IO.Directory.GetCurrentDirectory(), "Captures");
            System.IO.Directory.CreateDirectory(dir);
            System.IO.File.WriteAllText(System.IO.Path.Combine(dir, "physbones.txt"), sb.ToString());
            Debug.Log("[PB] 已写入 Captures/physbones.txt\n" + sb.ToString().Substring(0, Mathf.Min(600, sb.Length)));
        }
    }
}

// ────────────────────────────────────────────────────────────────
// 以下原 DedupePhysBones.cs（2026-09-25 并入 PhysBoneTools.cs；类名、方法、菜单路径不变）
// ────────────────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】通用工具
// 适用素体：任意
// 相关素材：无
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4
// 可复用性：★★★ 自动识别头像，换单直接能用
// 用途　　：找出同一物体上重复的 VRCPhysBone，逐字段比对确认冗余后再删
// ══════════════════════════════════════════════════════════════════
// 同一物体挂多个 PhysBone 是常见的复制粘贴事故：VRChat 两个都算进统计，
// 而实际只有第一个的动画绑定有效（AAO 会报 "Animation targeting non-first
// component of the type VRCPhysBone … Skipping this binding"）。
//
// 但「同物体多个 PB」不等于「冗余」—— 也可能 rootTransform 指向不同的骨链。
// 所以判定必须逐字段比对，只有**除碰撞体列表外全部相同**、且一方的碰撞体
// 是另一方的子集（含空引用）时，才认定为冗余副本。
namespace AvatarGen
{
    using System.Collections.Generic;
    using System.Linq;
    using System.Text;
    using UnityEngine;
    using UnityEditor;
    using VRC.SDK3.Dynamics.PhysBone.Components;

    public static class DedupePhysBones
    {
        // 比对时跳过的字段：运行时状态、编辑器折叠状态、以及单独处理的碰撞体列表
        static readonly HashSet<string> Skip = new HashSet<string>{
            "colliders", "m_ObjectHideFlags", "m_CorrespondingSourceObject",
            "m_PrefabInstance", "m_PrefabAsset", "m_GameObject", "m_EditorHideFlags",
            "m_Script", "m_Name", "m_EditorClassIdentifier", "bones", "chainId",
            "collisionRecords", "maxBoneChainIndex", "configHasUpdated", "collidersHaveUpdated",
        };

        static string Fingerprint(VRCPhysBone pb)
        {
            var so = new SerializedObject(pb);
            var it = so.GetIterator();
            var sb = new StringBuilder();
            bool enter = true;
            while (it.NextVisible(enter))
            {
                enter = false;
                if (Skip.Contains(it.name)) continue;
                if (it.propertyPath.StartsWith("foldout")) continue;
                sb.Append(it.propertyPath).Append('=');
                switch (it.propertyType)
                {
                    case SerializedPropertyType.ObjectReference:
                        sb.Append(it.objectReferenceValue != null ? it.objectReferenceValue.name : "null"); break;
                    case SerializedPropertyType.Float:   sb.Append(it.floatValue.ToString("R")); break;
                    case SerializedPropertyType.Integer: sb.Append(it.intValue); break;
                    case SerializedPropertyType.Boolean: sb.Append(it.boolValue); break;
                    case SerializedPropertyType.Vector3: sb.Append(it.vector3Value); break;
                    case SerializedPropertyType.Enum:    sb.Append(it.enumValueIndex); break;
                    default: sb.Append(it.propertyType); break;
                }
                sb.Append(';');
            }
            return sb.ToString();
        }

        static List<Transform> Cols(VRCPhysBone pb) =>
            pb.colliders == null ? new List<Transform>()
            : pb.colliders.Where(c => c != null).Select(c => c.transform).ToList();

        static GameObject Avatar()
        {
            var sel = Selection.activeGameObject;
            if (sel != null)
            {
                var d0 = sel.GetComponentInParent<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
                if (d0 != null) return d0.gameObject;
            }
            var all = Object.FindObjectsOfType<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
            var g = all.FirstOrDefault(d => d.gameObject.activeInHierarchy);
            return g != null ? g.gameObject : (all.Length > 0 ? all[0].gameObject : null);
        }

        static void Run(bool apply)
        {
            var go = Avatar();
            if (go == null) { Debug.LogError("[PBDedup] 找不到头像"); return; }

            var groups = go.GetComponentsInChildren<VRCPhysBone>(true)
                           .GroupBy(p => p.gameObject)
                           .Where(g => g.Count() > 1).ToList();

            var sb = new StringBuilder();
            sb.AppendLine($"[PBDedup] 同物体挂多个 PhysBone 的物体：{groups.Count} 个（{(apply ? "执行清理" : "仅检查")}）");
            sb.AppendLine();

            int removed = 0, kept = 0;
            var toRemove = new List<VRCPhysBone>();

            foreach (var g in groups)
            {
                var list = g.ToList();
                var path = AnimationUtility.CalculateTransformPath(g.Key.transform, go.transform);
                sb.AppendLine($"● {path}   （{list.Count} 个）");

                // 按碰撞体有效数降序：保留最完整的那个
                var ordered = list.OrderByDescending(p => Cols(p).Count).ToList();
                var keep = ordered[0];
                var keepFp = Fingerprint(keep);
                var keepCols = new HashSet<Transform>(Cols(keep));
                sb.AppendLine($"    保留：碰撞体 {keepCols.Count} 个");

                foreach (var other in ordered.Skip(1))
                {
                    var oc = Cols(other);
                    bool sameSettings = Fingerprint(other) == keepFp;
                    bool colSubset = oc.All(c => keepCols.Contains(c));
                    int nulls = (other.colliders?.Count ?? 0) - oc.Count;

                    if (sameSettings && colSubset)
                    {
                        sb.AppendLine($"    冗余：碰撞体 {oc.Count} 个（含空引用 {nulls}），其余设置逐字段相同 → 删除");
                        toRemove.Add(other); removed++;
                    }
                    else
                    {
                        sb.AppendLine($"    ★保留：设置{(sameSettings ? "相同" : "不同")}、碰撞体{(colSubset ? "是子集" : "有独有项")} → 不动，需人工判断");
                        kept++;
                    }
                }
                sb.AppendLine();
            }

            sb.AppendLine($"判定冗余 {removed} 个 · 需人工判断 {kept} 个");
            if (apply)
            {
                foreach (var c in toRemove) Undo.DestroyObjectImmediate(c);
                sb.AppendLine($"已删除 {toRemove.Count} 个组件。");
            }

            var dir = System.IO.Path.Combine(System.IO.Directory.GetCurrentDirectory(), "Captures");
            System.IO.Directory.CreateDirectory(dir);
            System.IO.File.WriteAllText(System.IO.Path.Combine(dir, "physbone_dedupe.txt"), sb.ToString());
            Debug.Log("[PBDedup] 明细见 Captures/physbone_dedupe.txt\n" + sb.ToString().Substring(0, Mathf.Min(700, sb.Length)));
        }

        [MenuItem("Tools/AvatarGen/Perf - 检查重复 PhysBone", false, 327)]
        public static void Check() => Run(false);

        [MenuItem("Tools/AvatarGen/Perf - 清理重复 PhysBone", false, 328)]
        public static void Apply() => Run(true);

        // 直接改预制体资产。走 LoadPrefabContents/SaveAsPrefabAsset，
        // 不经过预制体舞台、也不经过场景实例 —— 舞台保存失败、
        // 改动落成实例覆盖这两个坑都能绕开。
        [MenuItem("Tools/AvatarGen/Perf - 清理重复 PhysBone（改预制体资产）", false, 329)]
        public static void ApplyToPrefabAsset()
        {
            var sceneGo = Avatar();
            var path = sceneGo == null ? null
                : PrefabUtility.GetCorrespondingObjectFromSource(sceneGo) is GameObject src
                    ? AssetDatabase.GetAssetPath(src) : null;
            if (string.IsNullOrEmpty(path)) { Debug.LogError("[PBDedup] 场景里的头像不是预制体实例，取不到资产路径"); return; }
            var root = PrefabUtility.LoadPrefabContents(path);
            if (root == null) { Debug.LogError("[PBDedup] 打不开 " + path); return; }
            try
            {
                var groups = root.GetComponentsInChildren<VRCPhysBone>(true)
                                 .GroupBy(p => p.gameObject)
                                 .Where(g => g.Count() > 1).ToList();
                var sb = new StringBuilder();
                sb.AppendLine($"[PBDedup·资产] {path}");
                sb.AppendLine($"同物体多个 PhysBone：{groups.Count} 个物体");
                sb.AppendLine();
                int removed = 0, manual = 0;
                foreach (var g in groups)
                {
                    var ordered = g.OrderByDescending(p => Cols(p).Count).ToList();
                    var keep = ordered[0];
                    var keepFp = Fingerprint(keep);
                    var keepCols = new HashSet<Transform>(Cols(keep));
                    var p2 = AnimationUtility.CalculateTransformPath(g.Key.transform, root.transform);
                    foreach (var other in ordered.Skip(1))
                    {
                        var oc = Cols(other);
                        if (Fingerprint(other) == keepFp && oc.All(c => keepCols.Contains(c)))
                        {
                            sb.AppendLine($"  删  {p2}   （保留碰撞体 {keepCols.Count} 个 / 删除的有 {oc.Count} 个）");
                            Object.DestroyImmediate(other, true); removed++;
                        }
                        else { sb.AppendLine($"  ★留 {p2}   设置或碰撞体不同，需人工判断"); manual++; }
                    }
                }
                sb.AppendLine();
                sb.AppendLine($"已删除 {removed} 个 · 需人工判断 {manual} 个");
                bool ok;
                PrefabUtility.SaveAsPrefabAsset(root, path, out ok);
                sb.AppendLine($"SaveAsPrefabAsset 返回：{(ok ? "成功" : "失败")}");
                if (!ok)
                {
                    var stage = UnityEditor.SceneManagement.PrefabStageUtility.GetCurrentPrefabStage();
                    sb.AppendLine($"  当前预制体舞台：{(stage == null ? "无" : stage.assetPath)}");
                    var fi = new System.IO.FileInfo(path);
                    sb.AppendLine($"  文件存在={fi.Exists} 只读={(fi.Exists && fi.IsReadOnly)} 大小={(fi.Exists ? fi.Length : 0)}");
                }
                AssetDatabase.Refresh();
                var dir = System.IO.Path.Combine(System.IO.Directory.GetCurrentDirectory(), "Captures");
                System.IO.Directory.CreateDirectory(dir);
                System.IO.File.WriteAllText(System.IO.Path.Combine(dir, "physbone_dedupe_asset.txt"), sb.ToString());
                Debug.Log("[PBDedup·资产] 已保存。明细见 Captures/physbone_dedupe_asset.txt\n" + sb);
            }
            finally { PrefabUtility.UnloadPrefabContents(root); }
        }
    }
}

// ────────────────────────────────────────────────────────────────
// 以下原 MergePhysBoneGroups.cs（2026-09-25 并入 PhysBoneTools.cs；类名、方法、菜单路径不变）
// ────────────────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════
// 【开发工具】通用工具
// 适用素体：任意
// 相关素材：AAO (Avatar Optimizer)
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4 / AAO 1.9.16
// 可复用性：★★★ 自动识别头像，换单直接能用
// 用途　　：找出同一父物体下设置相同的兄弟 PhysBone 组，挂 AAO MergePhysBone 把它们合并
// ══════════════════════════════════════════════════════════════════
// VRChat 的 PhysBone 组件数硬上限是 256，超了直接上传失败（不是警告）。
// 服装包里常见一排设置完全相同的物理骨（羽織、裙摆、飘带），每根一个组件，
// 很容易把总数顶上去。
//
// AAO 自带的「Auto Merge Compatible PhysBone」很保守，很多能合的它不合；
// 显式挂 MergePhysBone 组件可以强制合并 —— 合并后是一个组件驱动多条骨链，
// 物理表现一致（AAO 会校验设置兼容性，不兼容会在构建时报错）。
//
// AAO 运行时程序集没开 Auto Referenced，直接 using 编不过，所以走反射。
// ⚠ 踩过的坑（2026-08 工程G之后、300 的 Milfy 工程）：
//   AAO 校验的是每个目标 PhysBone **有效根**（rootTransform 为空时才是组件自身）
//   的父对象，且要求它等于 MergePhysBone 所在的 GameObject。
//   很多服装是「PB 文件夹」写法：PhysBone 挂在空物体上、rootTransform 指向真骨骼。
//   这时按组件位置分组看着完全合理，AAO 构建期却会报
//   「合并目标的 PhysBone 父对象不同」并**中止整条 NDMF 链**，
//   表现为 VRCSDK 弹「Preprocess Callback Failed」，且不告诉你是哪个组件。
//   → 挂完一定要跑 FixAaoMergePhysBone 体检一遍，别等构建时才发现。
namespace AvatarGen
{
    using System.Collections.Generic;
    using System.Linq;
    using System.Text;
    using UnityEngine;
    using UnityEditor;
    using VRC.SDK3.Dynamics.PhysBone.Components;

    public static class MergePhysBoneGroups
    {
        const int MinGroup = 3;   // 少于这个数量不值得合并

        static readonly HashSet<string> Skip = new HashSet<string>{
            "m_ObjectHideFlags","m_CorrespondingSourceObject","m_PrefabInstance","m_PrefabAsset",
            "m_GameObject","m_EditorHideFlags","m_Script","m_Name","m_EditorClassIdentifier",
            "bones","chainId","collisionRecords","maxBoneChainIndex","configHasUpdated",
            "collidersHaveUpdated","rootTransform",
        };

        static string Fingerprint(VRCPhysBone pb)
        {
            var so = new SerializedObject(pb);
            var it = so.GetIterator();
            var sb = new StringBuilder();
            bool enter = true;
            while (it.NextVisible(enter))
            {
                enter = false;
                if (Skip.Contains(it.name) || it.propertyPath.StartsWith("foldout")) continue;
                sb.Append(it.propertyPath).Append('=');
                switch (it.propertyType)
                {
                    case SerializedPropertyType.ObjectReference:
                        sb.Append(it.objectReferenceValue != null ? it.objectReferenceValue.name : "null"); break;
                    case SerializedPropertyType.Float: sb.Append(it.floatValue.ToString("R")); break;
                    case SerializedPropertyType.Integer: sb.Append(it.intValue); break;
                    case SerializedPropertyType.Boolean: sb.Append(it.boolValue); break;
                    case SerializedPropertyType.Vector3: sb.Append(it.vector3Value); break;
                    case SerializedPropertyType.Enum: sb.Append(it.enumValueIndex); break;
                    default: sb.Append(it.propertyType); break;
                }
                sb.Append(';');
            }
            return sb.ToString();
        }

        static GameObject FindAvatar()
        {
            var sel = Selection.activeGameObject;
            if (sel != null)
            {
                var d0 = sel.GetComponentInParent<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
                if (d0 != null) return d0.gameObject;
            }
            var all = Object.FindObjectsOfType<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
            foreach (var d in all) if (d.gameObject.activeInHierarchy) return d.gameObject;
            return all.Length > 0 ? all[0].gameObject : null;
        }

        static System.Type MergeType() =>
            System.AppDomain.CurrentDomain.GetAssemblies()
                .SelectMany(a => { try { return a.GetTypes(); } catch { return new System.Type[0]; } })
                .FirstOrDefault(t => t.FullName == "Anatawa12.AvatarOptimizer.MergePhysBone");

        static void Run(bool apply)
        {
            var go = FindAvatar();
            if (go == null) { Debug.LogError("[MergePB] 找不到头像"); return; }
            var type = MergeType();
            if (apply && type == null) { Debug.LogError("[MergePB] 找不到 AAO 的 MergePhysBone 类型，AAO 没装？"); return; }

            // 按「父物体 + 设置指纹」分组：同一父下、设置相同的兄弟才可合并
            var groups = go.GetComponentsInChildren<VRCPhysBone>(true)
                .Where(pb => pb.transform.parent != null)
                .GroupBy(pb => (parent: pb.transform.parent, fp: Fingerprint(pb)))
                .Where(g => g.Count() >= MinGroup)
                .OrderByDescending(g => g.Count())
                .ToList();

            var sb = new StringBuilder();
            int total = go.GetComponentsInChildren<VRCPhysBone>(true).Length;
            int save = groups.Sum(g => g.Count() - 1);
            sb.AppendLine($"[MergePB] 当前 PhysBone {total} 个（编辑期）");
            sb.AppendLine($"  可合并的兄弟组：{groups.Count} 组，合并后可省 {save} 个组件 → {total - save} 个");
            sb.AppendLine($"  （{(apply ? "执行挂载" : "仅分析")}，每组要求 ≥{MinGroup} 根、同父、设置逐字段相同）");
            sb.AppendLine();

            int done = 0;
            foreach (var g in groups)
            {
                var parent = g.Key.parent;
                var path = AnimationUtility.CalculateTransformPath(parent, go.transform);
                sb.AppendLine($"  {g.Count(),3} 根 → 1   父物体: {path}");
                foreach (var pb in g.Take(3)) sb.AppendLine($"           {pb.name}");
                if (g.Count() > 3) sb.AppendLine($"           …还有 {g.Count() - 3} 根");

                // AAO 的 MergePhysBone 合并的是「组件所在物体的直接子物体」上的 PhysBone。
                // 所以直接挂到现有父物体上就行 —— 千万别新建中间物体再搬 PhysBone 进去，
                // 那会改变层级路径，把所有按路径引用这些骨头的动画全部打断。
                //
                // 但必须先确认：该父物体下**带 PhysBone 的直接子物体**全都属于同一指纹组。
                // 只要混进一根设置不同的，AAO 构建时会因不兼容而报错。
                var allPbChildren = parent.Cast<Transform>()
                    .SelectMany(c => c.GetComponents<VRCPhysBone>()).ToList();
                bool uniform = allPbChildren.Count == g.Count()
                               && allPbChildren.All(pb => Fingerprint(pb) == g.Key.fp);
                if (!uniform)
                {
                    sb.AppendLine($"           ✗ 跳过：该父物体下共有 {allPbChildren.Count} 根子 PhysBone，" +
                                  $"不全属同一组，直接挂会不兼容");
                    continue;
                }
                if (parent.GetComponent(type) != null)
                {
                    sb.AppendLine("           ○ 已挂过 MergePhysBone，跳过");
                    continue;
                }
                if (apply)
                {
                    Undo.AddComponent(parent.gameObject, type);
                    sb.AppendLine("           ✓ 已挂 MergePhysBone");
                    done++;
                }
            }

            if (apply) sb.AppendLine($"\n已挂 {done} 个 MergePhysBone。构建时若设置不兼容 AAO 会报错。");

            var dir = System.IO.Path.Combine(System.IO.Directory.GetCurrentDirectory(), "Captures");
            System.IO.Directory.CreateDirectory(dir);
            System.IO.File.WriteAllText(System.IO.Path.Combine(dir, "merge_physbone.txt"), sb.ToString());
            Debug.Log("[MergePB] 明细见 Captures/merge_physbone.txt\n" + sb.ToString().Substring(0, Mathf.Min(900, sb.Length)));
        }

        [MenuItem("Tools/AvatarGen/Perf - 分析可合并 PhysBone", false, 334)]
        public static void Analyze() => Run(false);

        [MenuItem("Tools/AvatarGen/Perf - 挂 AAO MergePhysBone", false, 335)]
        public static void Apply() => Run(true);
    }
}

// ────────────────────────────────────────────────────────────────
// 以下原 MergePhysBoneExplicit.cs（2026-09-25 并入 PhysBoneTools.cs；类名、方法、菜单路径不变）
// ────────────────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════
// 【开发工具】通用工具
// 适用素体：任意
// 相关素材：AAO (Avatar Optimizer) 1.9.x
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4
// 可复用性：★★★ 自动识别头像，换单直接能用
// 用途　　：用 MergePhysBone.componentsSet 精确指定要合并的 PhysBone，绕开「同父全部合并」的限制
// ══════════════════════════════════════════════════════════════════
// 背景：VRChat PhysBone 组件数硬上限 256，超了上传失败。
// AvatarPoseSystem 之类的插件会在**自己的 NDMF pass 里**统计并报错，
// 而那个 pass 跑在 AAO 之前 —— 所以光靠 AAO 事后优化不够，
// **构建前的编辑期数量**也必须压到 256 以下。
//
// AAO 的 MergePhysBone 默认合并「组件所在物体的直接子物体」上的全部 PhysBone，
// 父物体下混着设置不同的就用不了。但它有 componentsSet（PrefabSafeSet），
// 可以精确点名要合并哪几根 —— 用这个就不必新建中间物体搬层级
// （搬层级会打断按路径引用的动画）。
// ⚠ 踩过的坑（2026-08 工程G之后、300 的 Milfy 工程）：
//   AAO 校验的是每个目标 PhysBone **有效根**（rootTransform 为空时才是组件自身）
//   的父对象，且要求它等于 MergePhysBone 所在的 GameObject。
//   很多服装是「PB 文件夹」写法：PhysBone 挂在空物体上、rootTransform 指向真骨骼。
//   这时按组件位置分组看着完全合理，AAO 构建期却会报
//   「合并目标的 PhysBone 父对象不同」并**中止整条 NDMF 链**，
//   表现为 VRCSDK 弹「Preprocess Callback Failed」，且不告诉你是哪个组件。
//   → 挂完一定要跑 FixAaoMergePhysBone 体检一遍，别等构建时才发现。
namespace AvatarGen
{
    using System.Collections.Generic;
    using System.Linq;
    using System.Text;
    using UnityEngine;
    using UnityEditor;
    using VRC.SDK3.Dynamics.PhysBone.Components;

    public static class MergePhysBoneExplicit
    {
        const int MinGroup = 2;

        static readonly HashSet<string> Skip = new HashSet<string>{
            "m_ObjectHideFlags","m_CorrespondingSourceObject","m_PrefabInstance","m_PrefabAsset",
            "m_GameObject","m_EditorHideFlags","m_Script","m_Name","m_EditorClassIdentifier",
            "bones","chainId","collisionRecords","maxBoneChainIndex","configHasUpdated",
            "collidersHaveUpdated","rootTransform",
        };

        static string Fingerprint(VRCPhysBone pb)
        {
            var so = new SerializedObject(pb);
            var it = so.GetIterator();
            var sb = new StringBuilder();
            bool enter = true;
            while (it.NextVisible(enter))
            {
                enter = false;
                if (Skip.Contains(it.name) || it.propertyPath.StartsWith("foldout")) continue;
                sb.Append(it.propertyPath).Append('=');
                switch (it.propertyType)
                {
                    case SerializedPropertyType.ObjectReference:
                        sb.Append(it.objectReferenceValue != null ? it.objectReferenceValue.name : "null"); break;
                    case SerializedPropertyType.Float: sb.Append(it.floatValue.ToString("R")); break;
                    case SerializedPropertyType.Integer: sb.Append(it.intValue); break;
                    case SerializedPropertyType.Boolean: sb.Append(it.boolValue); break;
                    case SerializedPropertyType.Vector3: sb.Append(it.vector3Value); break;
                    case SerializedPropertyType.Enum: sb.Append(it.enumValueIndex); break;
                    default: sb.Append(it.propertyType); break;
                }
                sb.Append(';');
            }
            return sb.ToString();
        }

        static GameObject FindAvatar()
        {
            var sel = Selection.activeGameObject;
            if (sel != null)
            {
                var d0 = sel.GetComponentInParent<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
                if (d0 != null) return d0.gameObject;
            }
            var all = Object.FindObjectsOfType<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
            foreach (var d in all) if (d.gameObject.activeInHierarchy) return d.gameObject;
            return all.Length > 0 ? all[0].gameObject : null;
        }

        static System.Type MergeType() =>
            System.AppDomain.CurrentDomain.GetAssemblies()
                .SelectMany(a => { try { return a.GetTypes(); } catch { return new System.Type[0]; } })
                .FirstOrDefault(t => t.FullName == "Anatawa12.AvatarOptimizer.MergePhysBone");

        [MenuItem("Tools/AvatarGen/Perf - 精确合并 PhysBone", false, 337)]
        public static void Apply()
        {
            var go = FindAvatar();
            if (go == null) { Debug.LogError("[MergeEx] 找不到头像"); return; }
            var type = MergeType();
            if (type == null) { Debug.LogError("[MergeEx] 找不到 AAO MergePhysBone 类型"); return; }

            var pbs = go.GetComponentsInChildren<VRCPhysBone>(true);
            // 已经被现有 MergePhysBone 管着的不要重复纳入
            var claimed = new HashSet<VRCPhysBone>();
            foreach (var mc in go.GetComponentsInChildren(type, true))
                foreach (Transform c in ((Component)mc).transform)
                    foreach (var pb in c.GetComponents<VRCPhysBone>()) claimed.Add(pb);

            var groups = pbs.Where(p => !claimed.Contains(p) && p.transform.parent != null)
                            .GroupBy(p => (parent: p.transform.parent, fp: Fingerprint(p)))
                            .Where(g => g.Count() >= MinGroup)
                            .OrderByDescending(g => g.Count()).ToList();

            var sb = new StringBuilder();
            sb.AppendLine($"[MergeEx] 编辑期 PhysBone {pbs.Length} 个（其中 {claimed.Count} 个已被现有 MergePhysBone 接管）");
            sb.AppendLine($"  新可合并组 {groups.Count} 个，可再省 {groups.Sum(g => g.Count() - 1)} 个");
            sb.AppendLine();

            int done = 0, saved = 0;
            foreach (var g in groups)
            {
                var parent = g.Key.parent;
                var list = g.ToList();
                var path = AnimationUtility.CalculateTransformPath(parent, go.transform);

                var holder = Undo.AddComponent(parent.gameObject, type);
                var so = new SerializedObject(holder);
                var setProp = so.FindProperty("componentsSet");
                var mainSet = setProp?.FindPropertyRelative("mainSet");
                if (mainSet == null)
                {
                    sb.AppendLine($"  ✗ {path}：找不到 componentsSet.mainSet，撤销");
                    Undo.DestroyObjectImmediate(holder);
                    continue;
                }
                mainSet.arraySize = list.Count;
                for (int i = 0; i < list.Count; i++)
                    mainSet.GetArrayElementAtIndex(i).objectReferenceValue = list[i];
                so.ApplyModifiedPropertiesWithoutUndo();
                EditorUtility.SetDirty(holder);

                sb.AppendLine($"  ✓ {list.Count} 根 → 1   {path}");
                foreach (var pb in list.Take(4)) sb.AppendLine($"        {pb.name}");
                if (list.Count > 4) sb.AppendLine($"        …还有 {list.Count - 4} 根");
                done++; saved += list.Count - 1;
            }

            sb.AppendLine();
            sb.AppendLine($"已挂 {done} 个 MergePhysBone（精确点名），预计省 {saved} 个组件");
            sb.AppendLine($"编辑期预计：{pbs.Length} → {pbs.Length - saved}");

            UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(go.scene);
            var dir = System.IO.Path.Combine(System.IO.Directory.GetCurrentDirectory(), "Captures");
            System.IO.Directory.CreateDirectory(dir);
            System.IO.File.WriteAllText(System.IO.Path.Combine(dir, "merge_explicit.txt"), sb.ToString());
            Debug.Log("[MergeEx] 明细见 Captures/merge_explicit.txt\n" + sb.ToString().Substring(0, Mathf.Min(900, sb.Length)));
        }
    }
}

// ────────────────────────────────────────────────────────────────
// 以下原 HardMergePhysBones.cs（2026-09-25 并入 PhysBoneTools.cs；类名、方法、菜单路径不变）
// ────────────────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════
// 【开发工具】通用工具
// 适用素体：任意
// 相关素材：AAO (可选) / AvatarPoseSystem
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4
// 可复用性：★★★ 自动识别头像，换单直接能用
// 用途　　：把「同父、设置相同」的一组兄弟 PhysBone 在**编辑期**真正合并成一个组件
// ══════════════════════════════════════════════════════════════════
// 为什么不能只靠 AAO 的 MergePhysBone：
//   AAO 在 NDMF 的 Optimizing 阶段才合并，而 AvatarPoseSystem 这类插件在
//   Transforming 阶段**开头**就 root.GetComponentsInChildren<VRCPhysBone>() 数一遍，
//   超过 256 直接 Report 错误。AAO 事后优化到多少都救不回来。
//
// 为什么把组件挪到父物体是等价的（跟 AAO MergePhysBone 同一套原理）：
//   VRCPhysBone 的 rootTransform 是链的锚点，锚点自身不参与模拟，它的子孙才动。
//   原状：PB 挂在 Skirt_00 上、root 为空（即自己）→ Skirt_00 静止，其子孙摆动。
//   合并：PB 挂到父物体上、root 为空（即父物体）、multiChildType=Ignore
//         → 父物体有多个子物体，Ignore 表示父本身不作为骨骼，每个子物体各起一条链，
//           于是 Skirt_00..19 仍各自是自己那条链的静止锚点，子孙摆动。行为一致。
//
// 安全闸门（任一不满足就跳过该组，绝不侥幸）：
//   1. 父物体自己没有 PhysBone
//   2. 父物体下没有不带 PhysBone 的子物体（否则它们会被拉进模拟）
//   3. 组内每个物体只有 1 个 PhysBone，且 rootTransform 为空或指向自己
//   4. 组内所有 PhysBone 逐字段设置相同（rootTransform/bones 等运行时字段除外）
//   5. 没有任何动画曲线绑定这些路径上的 VRCPhysBone 组件属性
//      （只挪组件不挪物体，所以 Transform 曲线不受影响，只需查组件属性曲线）
namespace AvatarGen
{
    using System.Collections.Generic;
    using System.Linq;
    using System.Text;
    using UnityEngine;
    using UnityEditor;
    using UnityEditor.Animations;
    using UnityEditorInternal;
    using VRC.SDK3.Dynamics.PhysBone.Components;

    public static class HardMergePhysBones
    {
        // 只处理达到这个规模的组，避免为省 1 个就改动一堆地方
        const int MinGroup = 6;

        static readonly HashSet<string> Skip = new HashSet<string>{
            "m_ObjectHideFlags","m_CorrespondingSourceObject","m_PrefabInstance","m_PrefabAsset",
            "m_GameObject","m_EditorHideFlags","m_Script","m_Name","m_EditorClassIdentifier",
            "bones","chainId","collisionRecords","maxBoneChainIndex","configHasUpdated",
            "collidersHaveUpdated","rootTransform",
        };

        static string Fingerprint(VRCPhysBone pb)
        {
            var so = new SerializedObject(pb);
            var it = so.GetIterator();
            var sb = new StringBuilder();
            bool enter = true;
            while (it.NextVisible(enter))
            {
                enter = false;
                if (Skip.Contains(it.name) || it.propertyPath.StartsWith("foldout")) continue;
                sb.Append(it.propertyPath).Append('=');
                switch (it.propertyType)
                {
                    case SerializedPropertyType.ObjectReference:
                        var o = it.objectReferenceValue;
                        sb.Append(o != null ? o.GetInstanceID().ToString() : "null"); break;
                    case SerializedPropertyType.Float: sb.Append(it.floatValue.ToString("R")); break;
                    case SerializedPropertyType.Integer: sb.Append(it.intValue); break;
                    case SerializedPropertyType.Boolean: sb.Append(it.boolValue); break;
                    case SerializedPropertyType.Vector3: sb.Append(it.vector3Value); break;
                    case SerializedPropertyType.Enum: sb.Append(it.enumValueIndex); break;
                    case SerializedPropertyType.AnimationCurve: sb.Append(it.animationCurveValue.length); break;
                    default: sb.Append(it.propertyType); break;
                }
                sb.Append(';');
            }
            return sb.ToString();
        }

        static GameObject FindAvatar()
        {
            var sel = Selection.activeGameObject;
            if (sel != null)
            {
                var d0 = sel.GetComponentInParent<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
                if (d0 != null) return d0.gameObject;
            }
            var all = Object.FindObjectsOfType<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
            foreach (var d in all) if (d.gameObject.activeInHierarchy) return d.gameObject;
            return all.Length > 0 ? all[0].gameObject : null;
        }

        static IEnumerable<AnimationClip> AllClips(VRC.SDK3.Avatars.Components.VRCAvatarDescriptor d)
        {
            var seen = new HashSet<AnimationClip>();
            foreach (var l in d.baseAnimationLayers.Concat(d.specialAnimationLayers))
            {
                if (!(l.animatorController is UnityEditor.Animations.AnimatorController ac)) continue;
                foreach (var c in ac.animationClips) if (c != null && seen.Add(c)) yield return c;
            }
            foreach (var ac in Object.FindObjectsOfType<Animator>(true)
                     .Select(a => a.runtimeAnimatorController as UnityEditor.Animations.AnimatorController).Where(x => x != null))
                foreach (var c in ac.animationClips) if (c != null && seen.Add(c)) yield return c;
        }

        static System.Type AaoMergeType() =>
            System.AppDomain.CurrentDomain.GetAssemblies()
                .SelectMany(a => { try { return a.GetTypes(); } catch { return new System.Type[0]; } })
                .FirstOrDefault(t => t.FullName == "Anatawa12.AvatarOptimizer.MergePhysBone");

        static void Run(bool apply)
        {
            var go = FindAvatar();
            if (go == null) { Debug.LogError("[HardMerge] 找不到头像"); return; }
            var desc = go.GetComponent<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
            var sb = new StringBuilder();
            int before = go.GetComponentsInChildren<VRCPhysBone>(true).Length;
            sb.AppendLine($"[HardMerge] {(apply ? "执行" : "仅分析")}   编辑期 PhysBone {before} 个   组规模下限 {MinGroup}");
            sb.AppendLine();

            // 先把所有动画里绑定了 VRCPhysBone 组件属性的路径收集起来
            var animPbPaths = new HashSet<string>();
            int clipCount = 0;
            foreach (var clip in AllClips(desc))
            {
                clipCount++;
                foreach (var b in AnimationUtility.GetCurveBindings(clip)
                         .Concat(AnimationUtility.GetObjectReferenceCurveBindings(clip)))
                    if (b.type != null && typeof(VRC.Dynamics.VRCPhysBoneBase).IsAssignableFrom(b.type))
                        animPbPaths.Add(b.path);
            }
            sb.AppendLine($"扫描了 {clipCount} 个动画片段，其中 {animPbPaths.Count} 条路径的 PhysBone 组件属性被动画驱动");
            sb.AppendLine();

            var aaoType = AaoMergeType();
            var groups = go.GetComponentsInChildren<VRCPhysBone>(true)
                .Where(p => p.transform.parent != null)
                .GroupBy(p => p.transform.parent)
                .Where(g => g.Count() >= MinGroup)
                .OrderByDescending(g => g.Count()).ToList();

            int doneGroups = 0, saved = 0;
            foreach (var g in groups)
            {
                var parent = g.Key;
                var list = g.ToList();
                var path = AnimationUtility.CalculateTransformPath(parent, go.transform);
                sb.AppendLine($"── {list.Count} 根   {path}");

                string reject = null;
                int strays = parent.Cast<Transform>().Count(c => c.GetComponent<VRCPhysBone>() == null);
                if (parent.GetComponent<VRCPhysBone>() != null) reject = "父物体自己带 PhysBone";
                else if (strays > 0) reject = $"父物体下有 {strays} 个不带 PhysBone 的子物体，合并会把它们拉进模拟";
                else if (list.Any(p => p.GetComponents<VRCPhysBone>().Length != 1)) reject = "有物体挂了不止一个 PhysBone";
                else if (list.Any(p => p.rootTransform != null && p.rootTransform != p.transform)) reject = "有 PhysBone 的 rootTransform 指向别处";
                else
                {
                    var fp0 = Fingerprint(list[0]);
                    if (list.Any(p => Fingerprint(p) != fp0)) reject = "组内设置不完全相同";
                }
                if (reject == null)
                {
                    var hit = list.Select(p => AnimationUtility.CalculateTransformPath(p.transform, go.transform))
                                  .Where(pp => animPbPaths.Contains(pp)).ToList();
                    if (hit.Count > 0) reject = $"有 {hit.Count} 条路径的 PhysBone 属性被动画驱动（如 {hit[0]}）";
                }

                if (reject != null) { sb.AppendLine($"     ✗ 跳过：{reject}"); continue; }
                sb.AppendLine($"     ✓ 五道闸门全过 → 省 {list.Count - 1}");
                if (!apply) { doneGroups++; saved += list.Count - 1; continue; }

                // 用模板复制一份到父物体上，再删掉原来那一组
                var template = list[0];
                ComponentUtility.CopyComponent(template);
                ComponentUtility.PasteComponentAsNew(parent.gameObject);
                var merged = parent.GetComponents<VRCPhysBone>().Last();
                Undo.RegisterCreatedObjectUndo(merged, "hard merge physbone");
                merged.rootTransform = null;   // 用父物体自己当锚点
                merged.multiChildType = VRC.Dynamics.VRCPhysBoneBase.MultiChildType.Ignore;
                EditorUtility.SetDirty(merged);

                foreach (var pb in list) Undo.DestroyObjectImmediate(pb);

                // 父物体上如果挂着 AAO 的 MergePhysBone，已经没意义了，一并摘掉
                if (aaoType != null)
                    foreach (var mc in parent.GetComponents(aaoType))
                    {
                        Undo.DestroyObjectImmediate(mc);
                        sb.AppendLine("     · 顺手摘掉父物体上已失效的 AAO MergePhysBone");
                    }

                doneGroups++; saved += list.Count - 1;
            }

            int after = go.GetComponentsInChildren<VRCPhysBone>(true).Length;
            sb.AppendLine();
            sb.AppendLine(apply
                ? $"已合并 {doneGroups} 组，编辑期 PhysBone：{before} → {after}（实删 {before - after}）"
                : $"可合并 {doneGroups} 组，预计 {before} → {before - saved}（省 {saved}）");

            if (apply) UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(go.scene);
            var dir = System.IO.Path.Combine(System.IO.Directory.GetCurrentDirectory(), "Captures");
            System.IO.Directory.CreateDirectory(dir);
            System.IO.File.WriteAllText(System.IO.Path.Combine(dir, "hard_merge.txt"), sb.ToString());
            Debug.Log("[HardMerge] 明细见 Captures/hard_merge.txt\n" + sb.ToString().Substring(0, Mathf.Min(1200, sb.Length)));
        }

        [MenuItem("Tools/AvatarGen/Perf - 硬合并 PhysBone（分析）", false, 342)]
        public static void Analyze() => Run(false);

        [MenuItem("Tools/AvatarGen/Perf - 硬合并 PhysBone（执行）", false, 343)]
        public static void Apply() => Run(true);
    }
}

// ────────────────────────────────────────────────────────────────
// 以下原 ShedPhysBones.cs（2026-09-25 并入 PhysBoneTools.cs；类名、方法、菜单路径不变）
// ────────────────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════
// 【开发工具】通用工具
// 适用素体：任意（目标表按工程改）
// 相关素材：AAO (Avatar Optimizer)
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4
// 可复用性：★★ 改开头的目标表就能用
// 用途　　：为压到 VRChat 的 256 根 PhysBone 硬上限，做两件事：
//           A 把一组设置相同的兄弟 PhysBone 收进中间物体合并（改层级前先验动画引用）
//           B 摘掉指定挂件上的 PhysBone（保留挂件本体）
// ══════════════════════════════════════════════════════════════════
// 为什么必须压**编辑期**的数量：像 AvatarPoseSystem 这类插件会在自己的 NDMF pass
// 里统计 PhysBone 并在超限时报 Error，而那个 pass 跑在 AAO 之前 —— AAO 事后
// 优化到 246 也没用，NDMF 已经因为 APS 报的 259 中止了构建。
//
// A 的风险在于「新建中间物体 + 把 PhysBone 移进去」会改变层级路径，
// 打断所有按路径引用这些骨头的动画。所以先全量扫描动画片段，
// **有任何一条引用就整个放弃**，不做侥幸。
namespace AvatarGen
{
    using System.Collections.Generic;
    using System.Linq;
    using System.Text;
    using UnityEngine;
    using UnityEditor;
    using UnityEditor.Animations;
    using VRC.SDK3.Dynamics.PhysBone.Components;

    public static class ShedPhysBones
    {
        // A：要合并的一组（同父、设置相同）
        const string MergeParentPath = "双马尾/Armature.1/Hips/Spine/Chest/Neck/Head/Hair_root";
        static readonly string[] MergeChildren = { "Bang", "Bang.002", "Bang.004", "Bang.006" };

        // B：要摘掉 PhysBone 的挂件（挂件本体保留）
        const string StripPhysBoneOn =
            "Armature/Hips/Spine/Chest/Shoulder.L/Upper_arm.L/Lower_arm.L/Hand.L/SmartPhone/Armature/SmartPhone_Root/SmartPhone";

        static GameObject FindAvatar()
        {
            var sel = Selection.activeGameObject;
            if (sel != null)
            {
                var d0 = sel.GetComponentInParent<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
                if (d0 != null) return d0.gameObject;
            }
            var all = Object.FindObjectsOfType<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
            foreach (var d in all) if (d.gameObject.activeInHierarchy) return d.gameObject;
            return all.Length > 0 ? all[0].gameObject : null;
        }

        static IEnumerable<AnimationClip> AllClips(VRC.SDK3.Avatars.Components.VRCAvatarDescriptor d)
        {
            var seen = new HashSet<AnimationClip>();
            foreach (var l in d.baseAnimationLayers.Concat(d.specialAnimationLayers))
            {
                if (!(l.animatorController is AnimatorController ac)) continue;
                foreach (var c in ac.animationClips) if (c != null && seen.Add(c)) yield return c;
            }
        }

        [MenuItem("Tools/AvatarGen/Perf - 压 PhysBone 到上限内", false, 338)]
        public static void Run()
        {
            var go = FindAvatar();
            if (go == null) { Debug.LogError("[Shed] 找不到头像"); return; }
            var d = go.GetComponent<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
            var sb = new StringBuilder();
            int before = go.GetComponentsInChildren<VRCPhysBone>(true).Length;
            sb.AppendLine($"[Shed] 编辑期 PhysBone：{before} 个");
            sb.AppendLine();

            // ── A ──
            sb.AppendLine("── A：合并刘海物理骨 ──");
            var parent = go.transform.Find(MergeParentPath);
            int mergedSaved = 0;
            if (parent == null) sb.AppendLine($"  ✗ 找不到 {MergeParentPath}");
            else
            {
                var targets = MergeChildren.Select(n => parent.Find(n))
                                           .Where(t => t != null && t.GetComponent<VRCPhysBone>() != null).ToList();
                sb.AppendLine($"  目标 {targets.Count} 根：{string.Join(", ", targets.Select(t => t.name))}");

                // 先验动画引用：这些骨头及其子孙的路径，只要被任何一条曲线绑定就放弃
                var guard = new HashSet<string>();
                foreach (var t in targets)
                    foreach (var sub in t.GetComponentsInChildren<Transform>(true))
                        guard.Add(AnimationUtility.CalculateTransformPath(sub, go.transform));

                var hits = new List<string>();
                int clipCount = 0;
                foreach (var clip in AllClips(d))
                {
                    clipCount++;
                    foreach (var b in AnimationUtility.GetCurveBindings(clip)
                             .Concat(AnimationUtility.GetObjectReferenceCurveBindings(clip)))
                        if (guard.Contains(b.path)) hits.Add($"{clip.name} → {b.path} ({b.propertyName})");
                }
                sb.AppendLine($"  扫了 {clipCount} 个动画片段，覆盖 {guard.Count} 条路径");

                if (hits.Count > 0)
                {
                    sb.AppendLine($"  ✗ 放弃：有 {hits.Count} 条动画曲线引用这些路径，改层级会打断它们");
                    foreach (var h in hits.Take(5)) sb.AppendLine($"      {h}");
                }
                else if (targets.Count < 2) sb.AppendLine("  ✗ 目标不足 2 根，无需合并");
                else
                {
                    var type = System.AppDomain.CurrentDomain.GetAssemblies()
                        .SelectMany(a => { try { return a.GetTypes(); } catch { return new System.Type[0]; } })
                        .FirstOrDefault(t => t.FullName == "Anatawa12.AvatarOptimizer.MergePhysBone");
                    if (type == null) sb.AppendLine("  ✗ 找不到 AAO MergePhysBone 类型");
                    else
                    {
                        sb.AppendLine("  ✓ 零引用，可以安全改层级");
                        var holder = new GameObject("AAO_MergedBangs");
                        Undo.RegisterCreatedObjectUndo(holder, "shed physbone");
                        holder.transform.SetParent(parent, false);
                        foreach (var t in targets) Undo.SetTransformParent(t, holder.transform, "shed physbone");
                        var comp = Undo.AddComponent(holder, type);
                        sb.AppendLine(comp != null
                            ? $"  ✓ 已建 AAO_MergedBangs 并挂 MergePhysBone，{targets.Count} 根 → 1（省 {targets.Count - 1}）"
                            : "  ✗ AddComponent 返回 null");
                        if (comp != null) mergedSaved = targets.Count - 1;
                    }
                }
            }

            // ── B ──
            sb.AppendLine();
            sb.AppendLine("── B：摘掉挂件上的 PhysBone（挂件本体保留）──");
            int stripped = 0;
            var phone = go.transform.Find(StripPhysBoneOn);
            if (phone == null) sb.AppendLine($"  ✗ 找不到 {StripPhysBoneOn}");
            else
            {
                foreach (var pb in phone.GetComponents<VRCPhysBone>())
                {
                    int nCol = pb.colliders?.Count(c => c != null) ?? 0;
                    sb.AppendLine($"  ✓ 摘掉 {phone.name} 上的 VRCPhysBone（碰撞体 {nCol} 个）—— 挂件本体与菜单开关不受影响");
                    Undo.DestroyObjectImmediate(pb);
                    stripped++;
                }
                if (stripped == 0) sb.AppendLine("  ○ 该物体上没有 PhysBone");
            }

            int after = go.GetComponentsInChildren<VRCPhysBone>(true).Length;
            sb.AppendLine();
            sb.AppendLine($"编辑期 PhysBone：{before} → {after}（实删 {before - after}）");
            sb.AppendLine($"构建期预计：259 → {259 - (before - after) - mergedSaved}（AAO 合并再省 {mergedSaved}）  上限 256");

            UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(go.scene);
            var dir = System.IO.Path.Combine(System.IO.Directory.GetCurrentDirectory(), "Captures");
            System.IO.Directory.CreateDirectory(dir);
            System.IO.File.WriteAllText(System.IO.Path.Combine(dir, "shed_physbone.txt"), sb.ToString());
            Debug.Log("[Shed]\n" + sb);
        }
    }
}

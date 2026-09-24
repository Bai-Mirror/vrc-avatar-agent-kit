// ══════════════════════════════════════════════════════════════════
// 【开发工具】通用工具
// 适用素体：任意
// 相关素材：Modular Avatar / VRChat PhysBone
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4
// 可复用性：★★★ 自动识别头像，换单直接能用
// 用途　　：找出会中止 NDMF 构建的配置问题，以及可安全回收的空转 PhysBone
// ══════════════════════════════════════════════════════════════════
// 「Preprocess Callback Failed / BuildFrameworkOptimizeHook reported a failure」
// 这个弹窗只是说 NDMF 报了错，不说是哪条。NDMF 的严重度分级里
// NonFatal 不会中止构建，Error 才会 —— 所以别被最显眼的那条警告带偏。
//
// 扫两类东西：
//   A. Modular Avatar 的 MergeAnimator 没指定 Animator（MA-1300，会中止构建）
//   B. 空转 PhysBone：链上没有可模拟的骨骼、或多个 PhysBone 指向同一个根
//      这类删掉不改变任何表现，是压 256 上限时最干净的余量来源
using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEngine;
using UnityEditor;
using VRC.SDK3.Dynamics.PhysBone.Components;

namespace AvatarGen
{
    public static class BuildBlockerScan
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

        // 数一条 PhysBone 链上真正会被模拟的骨骼：根不算，根的子孙才算
        static int ChainBoneCount(VRCPhysBone pb)
        {
            var root = pb.rootTransform != null ? pb.rootTransform : pb.transform;
            var ignore = new HashSet<Transform>(pb.ignoreTransforms.Where(t => t != null));
            int n = 0;
            void Walk(Transform t)
            {
                foreach (Transform c in t)
                {
                    if (ignore.Contains(c)) continue;
                    n++;
                    Walk(c);
                }
            }
            Walk(root);
            return n;
        }

        // 完整指纹：只有连 ignoreTransforms 在内的每个字段都一样，才敢认定是纯冗余
        static readonly HashSet<string> SkipFp = new HashSet<string>{
            "m_ObjectHideFlags","m_CorrespondingSourceObject","m_PrefabInstance","m_PrefabAsset",
            "m_GameObject","m_EditorHideFlags","m_Script","m_Name","m_EditorClassIdentifier",
            "bones","chainId","collisionRecords","maxBoneChainIndex","configHasUpdated","collidersHaveUpdated",
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
                if (SkipFp.Contains(it.name) || it.propertyPath.StartsWith("foldout")) continue;
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

        static void Run(bool apply)
        {
            var go = FindAvatar();
            if (go == null) { Debug.LogError("[BlockerScan] 找不到头像"); return; }
            var sb = new StringBuilder();
            sb.AppendLine($"[BlockerScan] {(apply ? "执行清理" : "仅扫描")}   头像 {go.name}");
            sb.AppendLine();

            // ── A：Modular Avatar MergeAnimator 缺 Animator ──
            sb.AppendLine("=== A. Modular Avatar MergeAnimator 配置检查（MA-1300 会中止构建）===");
            var maType = System.AppDomain.CurrentDomain.GetAssemblies()
                .SelectMany(a => { try { return a.GetTypes(); } catch { return new System.Type[0]; } })
                .FirstOrDefault(t => t.FullName == "nadena.dev.modular_avatar.core.ModularAvatarMergeAnimator");
            int badMerge = 0;
            if (maType == null) sb.AppendLine("  (没装 Modular Avatar 或类型名对不上)");
            else
            {
                foreach (var c in go.GetComponentsInChildren(maType, true))
                {
                    var so = new SerializedObject(c);
                    var p = so.FindProperty("animator");
                    var path = AnimationUtility.CalculateTransformPath(((Component)c).transform, go.transform);
                    bool empty = p == null || p.objectReferenceValue == null;
                    sb.AppendLine($"  {(empty ? "✗ 空" : "○ 有")}  {path}");
                    if (!empty) continue;
                    badMerge++;
                    if (apply)
                    {
                        Undo.DestroyObjectImmediate((Object)c);
                        sb.AppendLine("       → 已删除（没指定 Animator 的 MergeAnimator 不产生任何效果）");
                    }
                }
                sb.AppendLine($"  合计 {badMerge} 个未指定 Animator");
            }

            // ── B：空转 PhysBone ──
            sb.AppendLine();
            sb.AppendLine("=== B. 空转 / 重复 PhysBone ===");
            var pbs = go.GetComponentsInChildren<VRCPhysBone>(true).ToList();
            sb.AppendLine($"  编辑期合计 {pbs.Count} 个");

            var dead = pbs.Where(p => ChainBoneCount(p) == 0).ToList();
            sb.AppendLine($"  · 链上没有任何可模拟骨骼：{dead.Count} 个");
            foreach (var p in dead.Take(20))
                sb.AppendLine($"       {AnimationUtility.CalculateTransformPath(p.transform, go.transform)}");

            var sameRoot = pbs.GroupBy(p => p.rootTransform != null ? p.rootTransform : p.transform)
                              .Where(g => g.Count() > 1).ToList();
            // 同根但设置不同的（例如 ignoreTransforms 分工不同）不能当冗余删，单独列出来
            var mixed = sameRoot.Where(g => g.Select(Fingerprint).Distinct().Count() > 1).ToList();
            var dupRoot = sameRoot.Where(g => g.Select(Fingerprint).Distinct().Count() == 1).ToList();
            foreach (var g in mixed)
            {
                sb.AppendLine($"  ! 同根但设置不同，不动：{AnimationUtility.CalculateTransformPath(g.Key, go.transform)}  ← {g.Count()} 个");
                foreach (var p in g) sb.AppendLine($"       {AnimationUtility.CalculateTransformPath(p.transform, go.transform)}");
            }
            int dupSave = dupRoot.Sum(g => g.Count() - 1);
            sb.AppendLine($"  · 多个 PhysBone 指向同一个根：{dupRoot.Count} 组，可省 {dupSave} 个");
            foreach (var g in dupRoot.Take(20))
            {
                sb.AppendLine($"       根 {AnimationUtility.CalculateTransformPath(g.Key, go.transform)}  ← {g.Count()} 个");
                foreach (var p in g) sb.AppendLine($"          {AnimationUtility.CalculateTransformPath(p.transform, go.transform)}");
            }

            // 「链上没有可模拟骨骼」的只报告不删：VRChat 的 endpointPosition 会补一根虚拟末端骨，
            // 判定它们完全没作用需要更强的证据，而且这次并不需要靠它们腾余量。
            if (apply)
            {
                int killed = 0;
                foreach (var g in dupRoot)
                    foreach (var p in g.Skip(1)) { Undo.DestroyObjectImmediate(p); killed++; }
                int after = go.GetComponentsInChildren<VRCPhysBone>(true).Length;
                sb.AppendLine();
                sb.AppendLine($"  已删除 {killed} 个同根同设置的冗余 PhysBone：{pbs.Count} → {after}");
                UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(go.scene);
            }
            else
            {
                sb.AppendLine();
                sb.AppendLine($"  执行后预计：{pbs.Count} → {pbs.Count - dupSave}（只删同根同设置的冗余，空转的保留）");
            }

            var dir = System.IO.Path.Combine(System.IO.Directory.GetCurrentDirectory(), "Captures");
            System.IO.Directory.CreateDirectory(dir);
            System.IO.File.WriteAllText(System.IO.Path.Combine(dir, "blocker_scan.txt"), sb.ToString());
            Debug.Log("[BlockerScan] 明细见 Captures/blocker_scan.txt\n" + sb.ToString().Substring(0, Mathf.Min(1200, sb.Length)));
        }

        [MenuItem("Tools/AvatarGen/Fix - 构建阻塞扫描（分析）", false, 344)]
        public static void Analyze() => Run(false);

        [MenuItem("Tools/AvatarGen/Fix - 构建阻塞扫描（执行）", false, 345)]
        public static void Apply() => Run(true);
    }
}

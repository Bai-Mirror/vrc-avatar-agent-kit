// ══════════════════════════════════════════════════════════════════
// 【开发工具】通用工具
// 适用素体：任意
// 相关素材：AAO (Avatar Optimizer)
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4 / AAO 1.9.16
// 可复用性：★★★ 自动识别头像，换单直接能用
// 用途　　：体检头像上的 AAO MergePhysBone，删掉配置无效、会中止构建的那些
// ══════════════════════════════════════════════════════════════════
// AAO 的 MergePhysBone 配置不对时会在构建期报 Error（不是警告），直接中止整条
// NDMF 链，表现为 VRCSDK 弹「Preprocess Callback Failed」。常见两种：
//   · 没有指定用于合并的目标 PhysBone —— 挂上去了但底下一个 PhysBone 都没有
//   · 合并目标的 PhysBone 父对象不同 —— 用 componentsSet 点名了非兄弟的组件
// 这两种都不产生任何优化效果，删掉即可。
using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEngine;
using UnityEditor;
using VRC.SDK3.Dynamics.PhysBone.Components;

namespace AvatarGen
{
    public static class FixAaoMergePhysBone
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

        static System.Type MergeType() =>
            System.AppDomain.CurrentDomain.GetAssemblies()
                .SelectMany(a => { try { return a.GetTypes(); } catch { return new System.Type[0]; } })
                .FirstOrDefault(t => t.FullName == "Anatawa12.AvatarOptimizer.MergePhysBone");

        // componentsSet 里点名的目标；为空则退回「直接子物体上的 PhysBone」
        static List<VRCPhysBone> Targets(Component mc, out bool explicitSet)
        {
            explicitSet = false;
            var list = new List<VRCPhysBone>();
            var so = new SerializedObject(mc);
            var mainSet = so.FindProperty("componentsSet")?.FindPropertyRelative("mainSet");
            if (mainSet != null && mainSet.arraySize > 0)
            {
                explicitSet = true;
                for (int i = 0; i < mainSet.arraySize; i++)
                    if (mainSet.GetArrayElementAtIndex(i).objectReferenceValue is VRCPhysBone pb) list.Add(pb);
                return list;
            }
            foreach (Transform c in mc.transform)
                list.AddRange(c.GetComponents<VRCPhysBone>());
            return list;
        }

        static void Run(bool apply)
        {
            var go = FindAvatar();
            if (go == null) { Debug.LogError("[FixMPB] 找不到头像"); return; }
            var type = MergeType();
            if (type == null) { Debug.LogError("[FixMPB] 找不到 AAO MergePhysBone 类型"); return; }

            var sb = new StringBuilder();
            var comps = go.GetComponentsInChildren(type, true).Cast<Component>().ToList();
            sb.AppendLine($"[FixMPB] {(apply ? "执行" : "仅分析")}   头像上共 {comps.Count} 个 AAO MergePhysBone");
            sb.AppendLine();

            int bad = 0;
            foreach (var mc in comps)
            {
                var path = AnimationUtility.CalculateTransformPath(mc.transform, go.transform);
                var targets = Targets(mc, out bool explicitSet);
                string why = null;
                if (targets.Count == 0) why = "没有任何目标 PhysBone";
                else if (targets.Count < 2) why = $"只有 {targets.Count} 个目标，合并没有意义";
                else
                {
                    // ★ AAO 比的是每个 PhysBone **有效根**（rootTransform 为空时是自身）的父对象，
                    //    不是组件所在物体的父对象。很多服装把 PhysBone 挂在空的 PB 文件夹物体上、
                    //    rootTransform 指向真正的骨骼，这时按组件位置判会全部误判为「正常」。
                    var roots = targets.Select(t => t.rootTransform != null ? t.rootTransform : t.transform).ToList();
                    var parents = roots.Select(r => r.parent).Distinct().ToList();
                    if (parents.Count > 1) why = $"目标的根分属 {parents.Count} 个不同父对象，AAO 会报错中止构建";
                    else if (parents.Count == 1 && parents[0] != mc.transform)
                        why = $"目标的根挂在 {(parents[0] == null ? "(无父对象)" : parents[0].name)} 下，" +
                              $"而 MergePhysBone 挂在 {mc.transform.name} 上，AAO 要求两者一致";
                }

                sb.AppendLine($"{(why == null ? "○ 正常" : "✗ 无效")}  {path}");
                sb.AppendLine($"     目标 {targets.Count} 个（{(explicitSet ? "componentsSet 点名" : "取直接子物体")}）");
                if (why == null) continue;
                sb.AppendLine($"     原因：{why}");
                bad++;
                if (apply)
                {
                    Undo.DestroyObjectImmediate(mc);
                    sb.AppendLine("     → 已删除");
                }
            }

            sb.AppendLine();
            sb.AppendLine(apply ? $"已删除 {bad} 个无效的 MergePhysBone。" : $"发现 {bad} 个无效，执行后会删掉。");

            if (apply) UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(go.scene);
            var dir = System.IO.Path.Combine(System.IO.Directory.GetCurrentDirectory(), "Captures");
            System.IO.Directory.CreateDirectory(dir);
            System.IO.File.WriteAllText(System.IO.Path.Combine(dir, "fix_mergephysbone.txt"), sb.ToString());
            Debug.Log("[FixMPB] 明细见 Captures/fix_mergephysbone.txt\n" + sb.ToString().Substring(0, Mathf.Min(1200, sb.Length)));
        }

        [MenuItem("Tools/AvatarGen/Fix - 体检 AAO MergePhysBone（分析）", false, 346)]
        public static void Analyze() => Run(false);

        [MenuItem("Tools/AvatarGen/Fix - 体检 AAO MergePhysBone（执行）", false, 347)]
        public static void Apply() => Run(true);
    }
}

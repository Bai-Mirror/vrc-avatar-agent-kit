// ══════════════════════════════════════════════════════════════════
// 【开发工具】通用工具
// 适用素体：任意
// 相关素材：AvatarPoseSystem (ZeroFactory)
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4
// 可复用性：★★ 改开头的目标物体名就能用于其他把 localBounds 撑大的插件
// 用途　　：把 AvatarPoseSystem 抓取手柄故意撑到 9.6 米的 localBounds 改回网格真实包围盒，修 AABB 超限。
// ══════════════════════════════════════════════════════════════════
// VRChat 按所有渲染器（含非激活）的合并包围盒判定 AABB，上限 5×6×6 米，超了验证失败。
//
// APS 的抓取手柄故意把 SkinnedMeshRenderer 的 localBounds 撑成 7 米高
// （中心 y=-1.5、尺寸 1.9×7×2），配合 updateWhenOffscreen=false，
// 目的是手柄被抓到远处时不被视锥剔除。副作用是整台头像 AABB 被顶到 9.6 米。
//
// 这里把 localBounds 改回网格自身的真实包围盒。代价：手柄移到很远时可能被剔除
// （看不见但功能仍在）。对贴身使用的姿势系统可以接受。
using System.Linq;
using System.Text;
using UnityEngine;
using UnityEditor;

namespace AvatarGen
{
    public static class FixAPSBounds
    {
        const string TargetRoot = "AvatarPoseSystem";

        [MenuItem("Tools/AvatarGen/Perf - 修正 APS 手柄包围盒", false, 336)]
        public static void Fix()
        {
            var all = Object.FindObjectsOfType<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
            var av = all.FirstOrDefault(d => d.gameObject.activeInHierarchy) ?? all.FirstOrDefault();
            if (av == null) { Debug.LogError("[APSBounds] 找不到头像"); return; }

            var root = av.transform.Find(TargetRoot);
            if (root == null) { Debug.LogError($"[APSBounds] 头像下没有 {TargetRoot}"); return; }

            var sb = new StringBuilder();
            sb.AppendLine($"[APSBounds] 处理 {TargetRoot} 下的 SkinnedMeshRenderer");
            sb.AppendLine();

            int fixedCount = 0, skipped = 0;
            foreach (var smr in root.GetComponentsInChildren<SkinnedMeshRenderer>(true))
            {
                var before = smr.localBounds;

                // ★ 不要用 sharedMesh.bounds ★
                // 这些手柄共用同一个 FBX 里的网格，sharedMesh.bounds 覆盖的是整个导入网格，
                // 不是这个渲染器那一部分 —— 实测会把 Z 轴撑到 279 米，比原问题更糟。
                //
                // 正确做法：只钳制明显异常的（某轴超过 2.5 米，或中心偏离原点超过 1 米），
                // 统一改成以原点为中心的 2×2×2 —— 足够罩住贴身使用的手柄，
                // 又不会把头像 AABB 顶出上限。本来就正常的不动。
                const float MaxAxis = 2.5f, MaxOffset = 1.0f;
                bool oversized = before.size.x > MaxAxis || before.size.y > MaxAxis || before.size.z > MaxAxis
                                 || Mathf.Abs(before.center.x) > MaxOffset
                                 || Mathf.Abs(before.center.y) > MaxOffset
                                 || Mathf.Abs(before.center.z) > MaxOffset;
                if (!oversized) { skipped++; continue; }
                var want = new Bounds(Vector3.zero, new Vector3(2f, 2f, 2f));

                Undo.RecordObject(smr, "fix APS bounds");
                smr.localBounds = want;
                PrefabUtility.RecordPrefabInstancePropertyModifications(smr);
                EditorUtility.SetDirty(smr);

                var path = AnimationUtility.CalculateTransformPath(smr.transform, av.transform);
                sb.AppendLine($"  {path}");
                sb.AppendLine($"     尺寸 ({before.size.x:F2},{before.size.y:F2},{before.size.z:F2})" +
                              $" → ({want.size.x:F2},{want.size.y:F2},{want.size.z:F2})" +
                              $"   中心 y {before.center.y:F2} → {want.center.y:F2}");
                fixedCount++;
            }

            // ── 第二步：把「缩放归零 + 挪到远处」的骨骼挪回原点 ──
            // APS 藏手柄用了双保险：scale=(0,0,0) 且 localPosition 沿局部轴 8 米。
            // 缩放为零已经完全不可见，那 8 米是多余的，却让蒙皮渲染器的世界包围盒
            // 跟着根骨骼跑到 y=8.76，把整台头像 AABB 顶到 9.6 米（上限 6 米）。
            // 归零后仍然不可见；APS 运行时是靠动画驱动位置的，静置值不影响功能。
            int moved = 0;
            sb.AppendLine();
            sb.AppendLine("── 挪回原点的「零缩放远置」骨骼 ──");
            foreach (var t in root.GetComponentsInChildren<Transform>(true))
            {
                var ls = t.localScale;
                bool zeroScale = Mathf.Abs(ls.x) < 1e-4f && Mathf.Abs(ls.y) < 1e-4f && Mathf.Abs(ls.z) < 1e-4f;
                if (!zeroScale) continue;
                if (t.localPosition.magnitude < 2f) continue;

                var p = AnimationUtility.CalculateTransformPath(t, av.transform);
                sb.AppendLine($"  {p}");
                sb.AppendLine($"     localPosition {t.localPosition} → (0,0,0)   （scale 已是 0，不影响可见性）");
                Undo.RecordObject(t, "zero parked bone");
                t.localPosition = Vector3.zero;
                PrefabUtility.RecordPrefabInstancePropertyModifications(t);
                EditorUtility.SetDirty(t);
                moved++;
            }
            if (moved == 0) sb.AppendLine("  （无）");

            sb.AppendLine();
            sb.AppendLine($"已修正包围盒 {fixedCount} 个，跳过 {skipped} 个；挪回原点 {moved} 个骨骼");

            UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(av.gameObject.scene);
            var dir = System.IO.Path.Combine(System.IO.Directory.GetCurrentDirectory(), "Captures");
            System.IO.Directory.CreateDirectory(dir);
            System.IO.File.WriteAllText(System.IO.Path.Combine(dir, "aps_bounds.txt"), sb.ToString());
            Debug.Log("[APSBounds]\n" + sb);
        }
    }
}

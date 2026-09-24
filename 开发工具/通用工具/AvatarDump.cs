// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】通用工具
// 适用素体：任意
// 相关素材：无
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4
// 可复用性：★★★ 自动识别头像，换单直接能用
// 用途　　：头像只读导出合集：BlendShape 名与权重、渲染器包围盒（找撑大 AABB 的元凶）、渲染器材质槽与主贴图
// ══════════════════════════════════════════════════════════════════
// 2026-09-25 由 DumpBlendShapes / DumpBounds / DumpRenderers 三个文件合并（kit-prep 整理）。
// 每个原文件是下面一个独立的 namespace 块，using 留在块内，**原类名、公开方法、菜单路径与优先级全部不变**，
// `-executeMethod AvatarGen.DumpBounds.Dump` 等旧调用照常可用；门面类 AvatarDump 只做转发。
// ⚠ 拷进工程时：本文件与旧的 3 个单文件二选一，同时存在会因类名重复编译失败。
//
// 菜单（Tools/AvatarGen/ 下）          → 静态入口（可 -executeMethod）
//   Dump BlendShapes          100      → AvatarGen.DumpBlendShapes.Dump  ＝ AvatarGen.AvatarDump.BlendShapes
//   Perf - Dump 包围盒        333      → AvatarGen.DumpBounds.Dump       ＝ AvatarGen.AvatarDump.Bounds
//   Dump 渲染器与材质槽       300      → AvatarGen.DumpRenderers.Dump    ＝ AvatarGen.AvatarDump.Renderers

namespace AvatarGen
{
    /// <summary>头像只读导出的统一入口：只做转发，实现在下面各原类里。</summary>
    public static class AvatarDump
    {
        public static void BlendShapes() => DumpBlendShapes.Dump();
        public static void Bounds() => DumpBounds.Dump();
        public static void Renderers() => DumpRenderers.Dump();
    }
}

// ────────────────────────────────────────────────────────────────
// 以下原 DumpBlendShapes.cs（2026-09-25 并入 AvatarDump.cs；类名、方法、菜单路径不变）
// ────────────────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】通用工具
// 适用素体：任意
// 相关素材：无
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4 / Modular Avatar 1.17.1 / NDMF 1.14.1 / AAO 1.9.16 / lilToon 2.3.4
// 可复用性：★★★ 换个单子直接能用
// 用途　　：导出网格的全部 BlendShape 名与当前权重
// ══════════════════════════════════════════════════════════════════
// 导出素体 BlendShape 清单
// 捏脸前先看素体自带多少可用的「顔調整/体型調整」形状键。
// 能用形状键完成的捏脸，就不必替换 FBX——零穿模风险、完全可逆、不影响已绑好的服装。
namespace AvatarGen
{
    using System.Linq;
    using UnityEngine;
    using UnityEditor;
    using System.IO;
    using System.Text;

    public static class DumpBlendShapes
    {
        // 自动识别场景里的头像：优先当前选中的那台，否则取场景里激活的
        // 第一个 VRCAvatarDescriptor。运行模式下 NDMF/MA 生成的 "(Clone)"
        // 一样带着 descriptor，不需要按名字硬匹配。
        static GameObject FindAvatar()
        {
            var sel = UnityEditor.Selection.activeGameObject;
            if (sel != null)
            {
                var d0 = sel.GetComponentInParent<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
                if (d0 != null) return d0.gameObject;
            }
            var all = Object.FindObjectsOfType<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
            foreach (var d in all) if (d.gameObject.activeInHierarchy) return d.gameObject;
            return all.Length > 0 ? all[0].gameObject : null;
        }
        const string OutPath    = "Captures/blendshapes.txt";

        [MenuItem("Tools/AvatarGen/Dump BlendShapes", false, 100)]
        public static void Dump()
        {
            GameObject root = FindAvatar();
            if (root == null) { Debug.LogError("[AvatarGen] avatar not found"); return; }
            var sb = new StringBuilder();
            int total = 0;
            foreach (SkinnedMeshRenderer smr in root.GetComponentsInChildren<SkinnedMeshRenderer>(true))
            {
                Mesh m = smr.sharedMesh;
                if (m == null || m.blendShapeCount == 0) continue;
                sb.AppendLine("=== " + smr.name + "  (" + m.blendShapeCount + " shapes) ===");
                for (int i = 0; i < m.blendShapeCount; i++)
                {
                    float w = smr.GetBlendShapeWeight(i);
                    sb.AppendLine(string.Format("{0,4}  {1,-46} w={2}", i, m.GetBlendShapeName(i), w));
                }
                total += m.blendShapeCount;
                sb.AppendLine();
            }
            string full = Path.Combine(Directory.GetCurrentDirectory(), OutPath);
            Directory.CreateDirectory(Path.GetDirectoryName(full));
            File.WriteAllText(full, sb.ToString(), new UTF8Encoding(false));
            Debug.Log("[AvatarGen] BlendShapes dumped: " + total + " total -> " + OutPath);
        }
    }
}

// ────────────────────────────────────────────────────────────────
// 以下原 DumpBounds.cs（2026-09-25 并入 AvatarDump.cs；类名、方法、菜单路径不变）
// ────────────────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════
// 【开发工具】通用工具
// 适用素体：任意
// 相关素材：无
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4
// 可复用性：★★★ 自动识别头像，换单直接能用
// 用途　　：找出把头像包围盒(AABB)撑大的元凶。VRChat 上限 5×6×6 米，超了会验证失败
// ══════════════════════════════════════════════════════════════════
// VRChat 按所有渲染器的合并包围盒判定，粒子系统尤其容易超 —— 它的 bounds 是
// 模拟范围而不是当前粒子位置，静止时看不出来。
// 逐个渲染器算它相对头像根的世界包围盒，按"超出主体的程度"排序。
namespace AvatarGen
{
    using System.Linq;
    using System.Text;
    using UnityEngine;
    using UnityEditor;

    public static class DumpBounds
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

        [MenuItem("Tools/AvatarGen/Perf - Dump 包围盒", false, 333)]
        public static void Dump()
        {
            var go = FindAvatar();
            if (go == null) { Debug.LogError("[Bounds] 找不到头像"); return; }
            var origin = go.transform.position;

            var rends = go.GetComponentsInChildren<Renderer>(true);
            var sb = new StringBuilder();

            Bounds all = new Bounds(origin, Vector3.zero);
            bool first = true;
            var rows = rends.Select(r =>
            {
                var b = r.bounds;
                return (r, b, ext: Mathf.Max(
                    Mathf.Abs(b.max.y - origin.y), Mathf.Abs(b.min.y - origin.y),
                    Mathf.Abs(b.max.x - origin.x), Mathf.Abs(b.min.x - origin.x),
                    Mathf.Abs(b.max.z - origin.z), Mathf.Abs(b.min.z - origin.z)));
            }).ToList();

            foreach (var (r, b, _) in rows)
            {
                if (first) { all = b; first = false; }
                else all.Encapsulate(b);
            }

            sb.AppendLine($"[Bounds] {go.name}   渲染器 {rends.Length} 个");
            sb.AppendLine($"  合并包围盒 尺寸 = ({all.size.x:F2}, {all.size.y:F2}, {all.size.z:F2})   VRChat 上限 (5.00, 6.00, 6.00)");
            sb.AppendLine($"  中心 {all.center}   最低 y={all.min.y:F2}  最高 y={all.max.y:F2}   （头像根 y={origin.y:F2}）");
            sb.AppendLine();
            sb.AppendLine("=== 离头像根最远的 20 个渲染器 ===");
            sb.AppendLine("  最远距离  类型                 尺寸(x,y,z)              y范围            路径");
            foreach (var (r, b, ext) in rows.OrderByDescending(x => x.ext).Take(20))
            {
                var path = AnimationUtility.CalculateTransformPath(r.transform, go.transform);
                sb.AppendLine($"  {ext,8:F2}  {r.GetType().Name,-20} ({b.size.x,5:F2},{b.size.y,6:F2},{b.size.z,5:F2})  " +
                              $"[{b.min.y,6:F2}, {b.max.y,6:F2}]  {(r.gameObject.activeInHierarchy ? "●" : "○")} {path}");
            }

            var ps = go.GetComponentsInChildren<ParticleSystem>(true);
            sb.AppendLine();
            sb.AppendLine($"=== 粒子系统 {ps.Length} 个（bounds 是模拟范围，静止时看不出来）===");
            foreach (var p in ps.Take(12))
            {
                var pr = p.GetComponent<ParticleSystemRenderer>();
                var path = AnimationUtility.CalculateTransformPath(p.transform, go.transform);
                sb.AppendLine($"  {(p.gameObject.activeInHierarchy ? "●" : "○")} y=[{(pr != null ? pr.bounds.min.y : 0),6:F2},{(pr != null ? pr.bounds.max.y : 0),6:F2}]  {path}");
            }

            var dir = System.IO.Path.Combine(System.IO.Directory.GetCurrentDirectory(), "Captures");
            System.IO.Directory.CreateDirectory(dir);
            System.IO.File.WriteAllText(System.IO.Path.Combine(dir, "bounds.txt"), sb.ToString());
            Debug.Log("[Bounds] 明细见 Captures/bounds.txt\n" + sb.ToString().Substring(0, Mathf.Min(700, sb.Length)));
        }
    }
}

// ────────────────────────────────────────────────────────────────
// 以下原 DumpRenderers.cs（2026-09-25 并入 AvatarDump.cs；类名、方法、菜单路径不变）
// ────────────────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】通用工具
// 适用素体：任意
// 相关素材：无
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4 / Modular Avatar 1.17.1 / NDMF 1.14.1 / AAO 1.9.16 / lilToon 2.3.4
// 可复用性：★★★ 换个单子直接能用
// 用途　　：列出头像每个渲染器的材质槽与主贴图。换贴图包之前先跑它，搞清楚哪个槽被几个网格共用
// ══════════════════════════════════════════════════════════════════
// 列出头像每个渲染器的材质槽与主贴图
// 客户素材里的替换贴图要挂到哪个槽，得先知道现在挂的是什么。
namespace AvatarGen
{
    using System.Linq;
    using System.Text;
    using UnityEngine;
    using UnityEditor;

    public static class DumpRenderers
    {
        // 自动识别场景里的头像：优先当前选中的那台，否则取场景里激活的
        // 第一个 VRCAvatarDescriptor。运行模式下 NDMF/MA 生成的 "(Clone)"
        // 一样带着 descriptor，不需要按名字硬匹配。
        static GameObject FindAvatar()
        {
            var sel = UnityEditor.Selection.activeGameObject;
            if (sel != null)
            {
                var d0 = sel.GetComponentInParent<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
                if (d0 != null) return d0.gameObject;
            }
            var all = Object.FindObjectsOfType<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
            foreach (var d in all) if (d.gameObject.activeInHierarchy) return d.gameObject;
            return all.Length > 0 ? all[0].gameObject : null;
        }

        [MenuItem("Tools/AvatarGen/Dump 渲染器与材质槽", false, 300)]
        public static void Dump()
        {
            var root = FindAvatar();
            if (root == null) { Debug.LogError("[AvatarGen] 场景里找不到带 VRCAvatarDescriptor 的头像"); return; }

            var sb = new StringBuilder("[AvatarGen] 渲染器 -> 材质槽 -> 主贴图\n");
            foreach (var r in root.GetComponentsInChildren<Renderer>(true))
            {
                // 只列直接挂在头像下一层的（外挂服装的内部网格太多，按需再展开）
                string path = AnimationUtility.CalculateTransformPath(r.transform, root.transform);
                if (path.Split('/').Length > 2) continue;

                sb.AppendLine(string.Format("  {0}{1}", path, r.gameObject.activeInHierarchy ? "" : "  (未激活)"));
                var mats = r.sharedMaterials;
                for (int i = 0; i < mats.Length; i++)
                {
                    var m = mats[i];
                    if (m == null) { sb.AppendLine("      [" + i + "] (空)"); continue; }
                    string tex = "-";
                    if (m.HasProperty("_MainTex") && m.GetTexture("_MainTex") != null)
                        tex = AssetDatabase.GetAssetPath(m.GetTexture("_MainTex"));
                    sb.AppendLine(string.Format("      [{0}] {1,-34} shader={2}\n           _MainTex = {3}",
                        i, m.name, m.shader != null ? m.shader.name : "?", tex));
                }
            }
            Debug.Log(sb.ToString());
        }
    }
}

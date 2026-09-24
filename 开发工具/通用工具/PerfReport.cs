// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】通用工具
// 适用素体：任意
// 相关素材：无
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4 / Modular Avatar 1.17.1 / NDMF 1.14.1 / AAO 1.9.16 / lilToon 2.3.4
// 可复用性：★★★ 换个单子直接能用
// 用途　　：走 VRChat SDK 的 AvatarPerformance API 出性能报告；含按顶层分组的面数分布。报告同时落盘（Console 会截断多行日志）
// ══════════════════════════════════════════════════════════════════
// 用 VRChat SDK 自己的评级 API 出性能报告
// 优化前后各跑一次才知道改动有没有效果，别凭感觉。
// 在运行模式下跑最准 —— 那时 NDMF/MA/AAO 已经全处理完了。
// 注意 AvatarPerformanceStats 的字段几乎全是可空类型（int? / PhysBoneStats?），
// 直接 .ToString("N0") 会编不过。
using System.Linq;
using System.Text;
using UnityEngine;
using UnityEditor;
using VRC.SDKBase.Validation.Performance;
using VRC.SDKBase.Validation.Performance.Stats;

namespace AvatarGen
{
    public static class PerfReport
    {
        // 自动找场景里的头像：优先当前选中的那台，否则取场景里第一个带 VRCAvatarDescriptor 的。
        // 运行模式下 NDMF/MA 会生成 "(Clone)"，descriptor 一样带着，无需按名字硬匹配。
        static GameObject Target()
        {
            var sel = UnityEditor.Selection.activeGameObject;
            if (sel != null)
            {
                var d0 = sel.GetComponentInParent<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
                if (d0 != null) return d0.gameObject;
            }
            var all = Object.FindObjectsOfType<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
            var act = all.FirstOrDefault(d => d.gameObject.activeInHierarchy);
            return act != null ? act.gameObject : (all.Length > 0 ? all[0].gameObject : null);
        }

        static string N(int? v, string fmt = "N0") => v.HasValue ? v.Value.ToString(fmt) : "-";
        static string N(float? v, string fmt) => v.HasValue ? v.Value.ToString(fmt) : "-";
        static string MB(long? b) => b.HasValue ? (b.Value / 1024f / 1024f).ToString("0.00") + " MB" : "-";

        [MenuItem("Tools/AvatarGen/Perf - 性能报告", false, 320)]
        public static void Report()
        {
            var go = Target();
            if (go == null) { Debug.LogError("[Perf] 找不到头像"); return; }

            var stats = new AvatarPerformanceStats(false);
            AvatarPerformance.CalculatePerformanceStats(go.name, go, stats, false);

            var sb = new StringBuilder();
            sb.AppendLine("[Perf] " + go.name + (Application.isPlaying ? "（运行模式 = 构建后）" : "（编辑模式 = 构建前）"));

            var pb = stats.physBone;
            var rows = new (AvatarPerformanceCategory cat, string val)[]{
                (AvatarPerformanceCategory.PolyCount,                 N(stats.polyCount)),
                (AvatarPerformanceCategory.SkinnedMeshCount,          N(stats.skinnedMeshCount)),
                (AvatarPerformanceCategory.MeshCount,                 N(stats.meshCount)),
                (AvatarPerformanceCategory.MaterialCount,             N(stats.materialCount)),
                (AvatarPerformanceCategory.BoneCount,                 N(stats.boneCount)),
                (AvatarPerformanceCategory.TextureMegabytes,          N(stats.textureMegabytes, "0.0") + " MB"),
                (AvatarPerformanceCategory.AnimatorCount,             N(stats.animatorCount)),
                (AvatarPerformanceCategory.PhysBoneComponentCount,    pb.HasValue ? pb.Value.componentCount.ToString() : "-"),
                (AvatarPerformanceCategory.PhysBoneTransformCount,    pb.HasValue ? pb.Value.transformCount.ToString() : "-"),
                (AvatarPerformanceCategory.PhysBoneColliderCount,     pb.HasValue ? pb.Value.colliderCount.ToString() : "-"),
                (AvatarPerformanceCategory.PhysBoneCollisionCheckCount, pb.HasValue ? pb.Value.collisionCheckCount.ToString() : "-"),
                (AvatarPerformanceCategory.ContactCount,              N(stats.contactCount)),
                (AvatarPerformanceCategory.ConstraintsCount,          N(stats.constraintsCount)),
                (AvatarPerformanceCategory.ParticleSystemCount,       N(stats.particleSystemCount)),
                (AvatarPerformanceCategory.AudioSourceCount,          N(stats.audioSourceCount)),
            };

            PerformanceRating worst = PerformanceRating.Excellent;
            foreach (var (cat, val) in rows)
            {
                var r = stats.GetPerformanceRatingForCategory(cat);
                if ((int)r > (int)worst) worst = r;
                sb.AppendLine(string.Format("   {0,-28} {1,-12} {2}",
                    AvatarPerformanceStats.GetPerformanceCategoryDisplayName(cat), val,
                    AvatarPerformanceStats.GetPerformanceRatingDisplayName(r)));
            }
            sb.AppendLine("   " + new string('-', 54));
            sb.AppendLine("   综合评级(取最差)             " + AvatarPerformanceStats.GetPerformanceRatingDisplayName(worst));
            sb.AppendLine("   下载 " + MB(stats.downloadSizeBytes) + "   解压后 " + MB(stats.uncompressedSizeBytes));

            var rends = go.GetComponentsInChildren<Renderer>(true);
            sb.AppendLine();
            sb.AppendLine("   渲染器 " + rends.Length + " 个，材质槽合计 " + rends.Sum(r => r.sharedMaterials.Length)
                          + "，去重后不同材质 " + rends.SelectMany(r => r.sharedMaterials)
                                .Where(m => m != null).Distinct().Count() + " 个");

            // 面数按「顶层分组」归并 —— 想知道哪套衣服/发型最重
            sb.AppendLine();
            sb.AppendLine("   面数分布（按头像下第一层分组）");
            var groups = new System.Collections.Generic.Dictionary<string,int>();
            foreach (var r in rends)
            {
                Mesh mesh = r is SkinnedMeshRenderer smr ? smr.sharedMesh
                          : (r.GetComponent<MeshFilter>() != null ? r.GetComponent<MeshFilter>().sharedMesh : null);
                if (mesh == null) continue;
                int tris = 0;
                for (int i = 0; i < mesh.subMeshCount; i++) tris += (int)(mesh.GetIndexCount(i) / 3);
                var t = r.transform;
                while (t.parent != null && t.parent != go.transform) t = t.parent;
                string key = t == go.transform ? "(根)" : t.name;
                groups[key] = groups.TryGetValue(key, out var v) ? v + tris : tris;
            }
            foreach (var kv in groups.OrderByDescending(k => k.Value))
                sb.AppendLine(string.Format("      {0,-28} {1,9:N0}", kv.Key, kv.Value));
            // Console 会把多行日志截断，报告同时落盘一份
            var dir = System.IO.Path.Combine(System.IO.Directory.GetCurrentDirectory(), "Captures");
            System.IO.Directory.CreateDirectory(dir);
            var f = System.IO.Path.Combine(dir, "perf_report.txt");
            System.IO.File.AppendAllText(f, "\n===== " + System.DateTime.Now.ToString("HH:mm:ss")
                                            + " =====\n" + sb.ToString());
            sb.AppendLine("   （完整报告已写入 Captures/perf_report.txt）");
            Debug.Log(sb.ToString());
        }

        [MenuItem("Tools/AvatarGen/Perf - 贴图清单", false, 321)]
        public static void TextureList()
        {
            var go = Target();
            if (go == null) { Debug.LogError("[Perf] 找不到头像"); return; }

            // 头像实际引用到的贴图（按渲染器->材质->所有贴图槽收集，去重）
            var seen = new System.Collections.Generic.Dictionary<Texture, string>();
            foreach (var r in go.GetComponentsInChildren<Renderer>(true))
                foreach (var m in r.sharedMaterials)
                {
                    if (m == null || m.shader == null) continue;
                    for (int i = 0; i < ShaderUtil.GetPropertyCount(m.shader); i++)
                    {
                        if (ShaderUtil.GetPropertyType(m.shader, i) != ShaderUtil.ShaderPropertyType.TexEnv) continue;
                        string prop = ShaderUtil.GetPropertyName(m.shader, i);
                        var tex = m.GetTexture(prop);
                        if (tex == null || seen.ContainsKey(tex)) continue;
                        seen[tex] = m.name + " . " + prop;
                    }
                }

            var rows = seen.Select(kv => new {
                tex = kv.Key,
                use = kv.Value,
                bytes = UnityEngine.Profiling.Profiler.GetRuntimeMemorySizeLong(kv.Key),
                path = AssetDatabase.GetAssetPath(kv.Key),
            }).OrderByDescending(x => x.bytes).ToList();

            var sb = new StringBuilder();
            sb.AppendLine("[Perf] 贴图清单  共 " + rows.Count + " 张，合计 "
                          + (rows.Sum(x => x.bytes) / 1024f / 1024f).ToString("0.0") + " MB");
            sb.AppendLine(string.Format("   {0,8}  {1,-11} {2,-10} {3}", "MB", "尺寸", "格式", "资产 / 用处"));
            foreach (var x in rows)
            {
                var t2 = x.tex as Texture2D;
                sb.AppendLine(string.Format("   {0,8}  {1,-11} {2,-10} {3}",
                    (x.bytes / 1024f / 1024f).ToString("0.00"),
                    x.tex.width + "x" + x.tex.height,
                    t2 != null ? t2.format.ToString() : x.tex.GetType().Name,
                    (string.IsNullOrEmpty(x.path) ? "(生成)" : x.path.Replace("Assets/", "")) + "   <- " + x.use));
            }

            var dir = System.IO.Path.Combine(System.IO.Directory.GetCurrentDirectory(), "Captures");
            System.IO.Directory.CreateDirectory(dir);
            System.IO.File.WriteAllText(System.IO.Path.Combine(dir, "texture_list.txt"), sb.ToString());
            Debug.Log("[Perf] 贴图清单已写入 Captures/texture_list.txt（共 " + rows.Count + " 张，"
                      + (rows.Sum(x => x.bytes) / 1024f / 1024f).ToString("0.0") + " MB）");
        }
    }
}

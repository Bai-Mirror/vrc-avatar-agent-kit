// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】通用工具
// 适用素体：任意
// 相关素材：无
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4 / Modular Avatar 1.17.1 / NDMF 1.14.1 / AAO 1.9.16 / lilToon 2.3.4
// 可复用性：★★★ 换个单子直接能用
// 用途　　：历史参考，仅保留压缩格式处理；贴图分档已由 tex_tier_plan.py / tex_tier_apply.py 取代。
// ══════════════════════════════════════════════════════════════════
// ⚠ 已被 tex_tier_plan.py / tex_tier_apply.py 取代（2026-09-23）：那两个按 shader 属性判辅助图；本文件只保留压缩格式部分可参考。
// 贴图分级与压缩
//
// 基线（构建后实测）：Texture Memory 208.4 MB，VeryPoor。
// 大头是四张 RGBA32 未压缩的 2048²，每张 42.67 MB —— 那是 Light Limit Changer
// 生成的克隆。LLC 的 TextureBaker.GetTextureFormat 是「沿用源贴图的格式」，
// 所以根因在源贴图：客户自备服装的 蓝色.png / 黑色.png 带了个 Standalone 平台覆盖，
// textureFormat 被写死成 4(RGBA32)。把覆盖改回自动，克隆就跟着变 DXT5。
//
// 其余按用途分级：主图集留 2048，遮罩/法线/发光图降 1024 —— 这类图肉眼看不出差别。
using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEngine;
using UnityEditor;

namespace AvatarGen
{
    public static class TexOptimize
    {
        // 判定为「辅助图」的关键词：遮罩、法线、发光、高光、MatCap 之类，降到 1024
        static readonly string[] AuxKeywords = {
            "mask", "normal", "emission", "hightlight", "highlight",
            "matcap", "alpha", "glitter", "reflection", "backlight", "outline",
        };
        // ★★ 档位必须按工程实况定，不能照搬 ★★
        // 先跑「Perf - 贴图清单」看尺寸分布再决定：
        //   工程G：主图多为 2048 → 用 2048 / 1024 / 512
        //   300 的 Milfy：126 张本来就是 1024 → 得用 1024 / 512 / 256，
        //                 照搬 2048/1024 的话辅助图一张都不会降
        const int TierMain = 2048;
        const int TierAux  = 1024;
        const int TierTiny = 512;

        // 单独点名的（尺寸明显过头，或者用途不值这么大）
        static readonly Dictionary<string,int> Explicit = new Dictionary<string,int>{
            // 本工程暂无需要单独点名的贴图
        };

        static GameObject Avatar()
        {
            var sel = UnityEditor.Selection.activeGameObject;
            if (sel != null)
            {
                var d0 = sel.GetComponentInParent<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
                if (d0 != null) return d0.gameObject;
            }
            var all = Object.FindObjectsOfType<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
            var g = all.FirstOrDefault(d => d.gameObject.activeInHierarchy);
            return g != null ? g.gameObject : (all.Length > 0 ? all[0].gameObject : null);
        }

        static IEnumerable<Texture> AvatarTextures()
        {
            var go = Avatar();
            if (go == null) { Debug.LogError("[TexOpt] 场景里找不到带 VRCAvatarDescriptor 的头像"); yield break; }
            var seen = new HashSet<Texture>();
            foreach (var r in go.GetComponentsInChildren<Renderer>(true))
                foreach (var m in r.sharedMaterials)
                {
                    if (m == null || m.shader == null) continue;
                    for (int i = 0; i < ShaderUtil.GetPropertyCount(m.shader); i++)
                    {
                        if (ShaderUtil.GetPropertyType(m.shader, i) != ShaderUtil.ShaderPropertyType.TexEnv) continue;
                        var t = m.GetTexture(ShaderUtil.GetPropertyName(m.shader, i));
                        if (t != null && seen.Add(t)) yield return t;
                    }
                }
        }

        // 未压缩 / 半浮点这些「一个像素好几字节」的格式
        static bool IsUncompressed(TextureImporterFormat f)
        {
            switch (f)
            {
                case TextureImporterFormat.RGBA32:
                case TextureImporterFormat.ARGB32:
                case TextureImporterFormat.RGB24:
                case TextureImporterFormat.RGBA64:
                case TextureImporterFormat.RGBAHalf:
                case TextureImporterFormat.Alpha8:
                case TextureImporterFormat.RGB16:
                case TextureImporterFormat.RGBA16:
                    return true;
                default: return false;
            }
        }

        static int TargetSize(string path)
        {
            foreach (var kv in Explicit)
                if (path.EndsWith(kv.Key)) return kv.Value;
            string low = System.IO.Path.GetFileName(path).ToLowerInvariant();
            if (AuxKeywords.Any(k => low.Contains(k))) return TierAux;
            return TierMain;
        }

        [MenuItem("Tools/AvatarGen/Perf - 贴图分级与压缩", false, 322)]
        public static void Optimize()
        {
            var sb = new StringBuilder("[TexOpt] 贴图分级\n");
            int changed = 0;
            var paths = AvatarTextures().Select(AssetDatabase.GetAssetPath)
                            .Where(p => !string.IsNullOrEmpty(p) && p.StartsWith("Assets/"))
                            .Distinct().OrderBy(p => p).ToList();

            AssetDatabase.StartAssetEditing();
            try
            {
                foreach (var p in paths)
                {
                    var ti = AssetImporter.GetAtPath(p) as TextureImporter;
                    if (ti == null) continue;

                    var before = new List<string>();
                    bool dirty = false;

                    // 1) 干掉「强制未压缩」的格式 —— 这是 208MB 的主因。
                    // 关键是 DefaultTexturePlatform 那一条：LLC 的 TextureBaker 走
                    // source.GetGenerationSettings() 烘贴图，读的就是默认平台的格式，
                    // 所以哪怕 Standalone 覆盖是「自动」，默认平台写死 RGBA32 一样会
                    // 让生成的克隆变成 2048² 未压缩 = 42.67MB 一张。
                    {
                        var s = ti.GetDefaultPlatformTextureSettings();
                        if (IsUncompressed(s.format))
                        {
                            before.Add("默认平台格式 " + s.format + " -> 自动压缩");
                            s.format = TextureImporterFormat.Automatic;
                            s.textureCompression = TextureImporterCompression.Compressed;
                            ti.SetPlatformTextureSettings(s);
                            dirty = true;
                        }
                    }
                    foreach (var plat in new[]{ "Standalone", "Android", "iPhone" })
                    {
                        var s = ti.GetPlatformTextureSettings(plat);
                        if (!s.overridden) continue;
                        if (IsUncompressed(s.format))
                        {
                            before.Add(plat + " 格式 " + s.format + " -> 自动");
                            s.format = TextureImporterFormat.Automatic;
                            s.textureCompression = TextureImporterCompression.Compressed;
                            ti.SetPlatformTextureSettings(s);
                            dirty = true;
                        }
                    }

                    // 2) 尺寸分级（默认与各平台覆盖都要压）
                    int want = TargetSize(p);
                    if (ti.maxTextureSize > want)
                    {
                        before.Add("默认 " + ti.maxTextureSize + " -> " + want);
                        ti.maxTextureSize = want; dirty = true;
                    }
                    foreach (var plat in new[]{ "Standalone", "Android", "iPhone" })
                    {
                        var s = ti.GetPlatformTextureSettings(plat);
                        if (s.overridden && s.maxTextureSize > want)
                        {
                            before.Add(plat + " " + s.maxTextureSize + " -> " + want);
                            s.maxTextureSize = want;
                            ti.SetPlatformTextureSettings(s);
                            dirty = true;
                        }
                    }

                    // 3) 默认压缩打开
                    if (ti.textureCompression == TextureImporterCompression.Uncompressed)
                    {
                        before.Add("默认未压缩 -> 压缩");
                        ti.textureCompression = TextureImporterCompression.Compressed;
                        dirty = true;
                    }

                    // 4) VRChat 强制要求 Mip Streaming
                    if (ti.mipmapEnabled && !ti.streamingMipmaps)
                    {
                        before.Add("开 Mip Streaming");
                        ti.streamingMipmaps = true; dirty = true;
                    }

                    if (dirty)
                    {
                        EditorUtility.SetDirty(ti);
                        ti.SaveAndReimport();
                        changed++;
                        sb.AppendLine("   " + p.Replace("Assets/", "") + "\n        " + string.Join("; ", before));
                    }
                }
            }
            finally { AssetDatabase.StopAssetEditing(); }

            sb.AppendLine("   共扫 " + paths.Count + " 张，改了 " + changed + " 张");
            var dir = System.IO.Path.Combine(System.IO.Directory.GetCurrentDirectory(), "Captures");
            System.IO.Directory.CreateDirectory(dir);
            System.IO.File.WriteAllText(System.IO.Path.Combine(dir, "tex_optimize.txt"), sb.ToString());
            AssetDatabase.Refresh();
            Debug.Log("[TexOpt] 完成：扫 " + paths.Count + " 张，改 " + changed + " 张（明细见 Captures/tex_optimize.txt）");
        }
    }
}

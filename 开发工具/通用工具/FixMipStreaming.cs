// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】通用工具
// 适用素体：任意
// 相关素材：无
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4 / Modular Avatar 1.17.1 / NDMF 1.14.1 / AAO 1.9.16 / lilToon 2.3.4
// 可复用性：★★★ 换个单子直接能用
// 用途　　：批量开启 Mip Streaming（VRChat 强制要求，不开 NDMF 构建会报错）
// ══════════════════════════════════════════════════════════════════
// 批量开启 Mip Streaming
//
// VRChat 强制要求贴图开启 Mip Streaming，NDMF 会在构建时报错。
// 新导入的发型包贴图默认没开，这里统一补上。
// 走 TextureImporter API 而不是直接改 .meta —— 改 .meta 容易漏字段、
// 且 Unity 不会重新导入，改了也不生效。
using UnityEngine;
using UnityEditor;
using System.Linq;

namespace AvatarGen
{
    public static class FixMipStreaming
    {
        static void Run(bool apply)
        {
            var guids = AssetDatabase.FindAssets("t:Texture2D", new[] { "Assets" });
            int need = 0, fixedCount = 0, noMip = 0;
            var sb = new System.Text.StringBuilder();

            foreach (string g in guids)
            {
                string p = AssetDatabase.GUIDToAssetPath(g);
                var ti = AssetImporter.GetAtPath(p) as TextureImporter;
                if (ti == null) continue;
                if (!ti.mipmapEnabled) { noMip++; continue; }   // 没有 mipmap 的（如 UI 精灵）不需要
                if (ti.streamingMipmaps) continue;

                need++;
                if (sb.Length < 1800) sb.AppendLine("    " + p);
                if (!apply) continue;
                ti.streamingMipmaps = true;
                EditorUtility.SetDirty(ti);
                ti.SaveAndReimport();
                fixedCount++;
            }

            Debug.Log("[AvatarGen] Mip Streaming " + (apply ? "修复" : "检查")
                + "\n  需要开启的贴图 = " + need + (apply ? "，已修复 " + fixedCount : "")
                + "\n  无 mipmap 跳过 = " + noMip
                + "\n" + sb);
        }

        [MenuItem("Tools/AvatarGen/Fix - 检查 Mip Streaming", false, 300)]
        public static void Check() { Run(false); }

        [MenuItem("Tools/AvatarGen/Fix - 修复 Mip Streaming", false, 301)]
        public static void Apply() { Run(true); }
    }
}

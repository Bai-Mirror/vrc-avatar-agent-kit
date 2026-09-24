// ══════════════════════════════════════════════════════════════════
// 【开发工具】通用工具
// 适用素体：任意
// 相关素材：NDMF
// 工具链　：Unity 2022.3.22f1 / NDMF 1.14.x
// 可复用性：★★★ 自动识别头像，换单直接能用
// 用途　　：不上传、不进 Play，直接跑一遍 NDMF 手动烘焙来复现构建期错误
// ══════════════════════════════════════════════════════════════════
// 排查「Preprocess Callback Failed」时，靠上传去试一次代价太大，
// 而 Play 模式在 Apply on Play 关掉时根本不跑构建链。
// NDMF 的 Manual bake 会完整跑一遍 Resolving→Optimizing 的所有 pass，
// 插件抛的异常和 Report 的错误都会照常出现在控制台里。
// 注意：它只跑 NDMF 链，VRCFury 自己那套 VRCSDK 钩子不在内。
using System.Linq;
using UnityEngine;
using UnityEditor;

namespace AvatarGen
{
    public static class BakeTest
    {
        [MenuItem("Tools/AvatarGen/Fix - 跑一次 NDMF 手动烘焙", false, 350)]
        public static void Run()
        {
            var all = Object.FindObjectsOfType<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
            var av = all.FirstOrDefault(d => d.gameObject.activeInHierarchy) ?? all.FirstOrDefault();
            if (av == null) { Debug.LogError("[BakeTest] 找不到头像"); return; }

            Selection.activeGameObject = av.gameObject;
            Debug.Log($"[BakeTest] ===== 开始烘焙 {av.name} =====");
            bool ok = EditorApplication.ExecuteMenuItem("Tools/NDM Framework/Manual bake avatar");
            Debug.Log($"[BakeTest] ===== 烘焙调用返回 {ok} =====");
        }
    }
}

// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】通用工具
// 适用素体：任意
// 相关素材：无
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4 / Modular Avatar 1.17.1 / NDMF 1.14.1 / AAO 1.9.16 / lilToon 2.3.4
// 可复用性：★★★ 换个单子直接能用
// 用途　　：动画层逻辑回归测试。里面记了两条走不通的路：animator.SetFloat 够不到 VRC 的 FX 参数（那是 PlayableGraph 挂的）、animator.playableGraph 在 GestureManager 下返回无效图。能走通的是把 controller 单挂临时物体跑
// ══════════════════════════════════════════════════════════════════
// 生成的动画层逻辑回归测试
//
// 走不通的两条路，记下来免得再试：
//   1) animator.SetFloat("SY_Hair", …)  —— VRChat 的 FX 层是 PlayableGraph 挂的，
//      root Animator 的 animator.parameters 里根本没有 SY_* / Outfit_Cap，设了没用。
//   2) animator.playableGraph 遍历      —— GestureManager 运行时这个属性返回无效图。
// 能走通的：把生成的 SY_FX.controller 单独挂到一个临时物体上跑，
// 直接验「给定参数组合，各层停在哪个状态」。层内的转换条件是自洽的，
// 这样测不到跟厂商层合并后的结果，但条件写错能当场抓出来。
using System.Text;
using UnityEngine;
using UnityEditor;
using UnityEditor.Animations;

namespace AvatarGen
{
    public static class PlayTest
    {
        const string CtlPath = "Assets/_SY_Menu/SY_FX.controller";

        [MenuItem("Tools/AvatarGen/PlayTest - 层逻辑（猫耳/帽子/发型）", false, 400)]
        public static void LayerLogic()
        {
            if (!Application.isPlaying) { Debug.LogError("[PlayTest] 要在运行模式下跑"); return; }
            var ctl = AssetDatabase.LoadAssetAtPath<AnimatorController>(CtlPath);
            if (ctl == null) { Debug.LogError("[PlayTest] 找不到 " + CtlPath); return; }

            int earLayer = -1;
            for (int i = 0; i < ctl.layers.Length; i++)
                if (ctl.layers[i].name == "SY CatEar") earLayer = i;
            if (earLayer < 0) { Debug.LogError("[PlayTest] 没有 SY CatEar 层"); return; }

            var go = new GameObject("~PlayTest");
            var an = go.AddComponent<Animator>();
            an.runtimeAnimatorController = ctl;

            var sb = new StringBuilder("[PlayTest] SY CatEar 层逻辑（第 " + earLayer + " 层）\n");
            sb.AppendLine("  发型档: <1/3=原版  1/3~2/3=Sweety  >2/3=Halo");

            void Case(string label, float hair, bool cap)
            {
                an.SetFloat("SY_Hair", hair);
                an.SetBool("Outfit_Cap", cap);
                an.Update(1f / 60f);
                an.Update(1f / 60f);
                var st = an.GetCurrentAnimatorStateInfo(earLayer);
                string name = st.IsName("Show") ? "Show(猫耳开)"
                            : st.IsName("Hide") ? "Hide(猫耳关)" : "?" ;
                sb.AppendLine(string.Format("  {0,-16} SY_Hair={1:0.000} 帽子={2,-2} -> {3}",
                    label, hair, cap ? "开" : "关", name));
            }

            Case("原版 不戴帽",  0.5f / 3f, false);
            Case("切 Sweety",   1.5f / 3f, false);
            Case("切 Halo",     2.5f / 3f, false);
            Case("切回原版",     0.5f / 3f, false);   // ← 用户报的 bug 就在这一步
            Case("原版 戴帽",    0.5f / 3f, true);
            Case("原版 脱帽",    0.5f / 3f, false);
            Case("Sweety 戴帽", 1.5f / 3f, true);

            Object.DestroyImmediate(go);
            sb.Append("  期望：只有「原版 且 不戴帽」是 Show，其余都是 Hide");
            Debug.Log(sb.ToString());
        }
    }
}

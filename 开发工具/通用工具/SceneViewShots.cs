// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】通用工具
// 适用素体：人形素体
// 相关素材：无
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4 / Modular Avatar 1.17.1 / NDMF 1.14.1 / AAO 1.9.16 / lilToon 2.3.4
// 可复用性：★★★ 换个单子直接能用
// 用途　　：按 Head/Foot 骨骼世界坐标定位 Scene View 机位，跨改动可复现的 A/B 对比截图
// ══════════════════════════════════════════════════════════════════
// 固定机位辅助
// A/B 对比必须同机位，否则没有可比性。
// 取景从渲染器包围盒自动推算，不写死数值——素体高矮不同也能用。
using System.Linq;
using UnityEngine;
using UnityEditor;

namespace AvatarGen
{
    public static class SceneViewShots
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

        // 用骨骼算身高：蒙皮网格的 bounds 常年偏大（刚装的服装尤其明显，实测虚报到 2.24m），
        // 而 Head/Foot 骨骼的世界坐标是精确的。
        static bool Measure(out float height, out float footY, out Transform head, out Vector3 center)
        {
            height = 0f; footY = 0f; head = null; center = Vector3.zero;
            GameObject root = FindAvatar();
            if (root == null) { Debug.LogError("[AvatarGen] avatar not found"); return false; }
            Animator an = root.GetComponent<Animator>();
            Transform foot = null;
            if (an != null && an.isHuman)
            {
                head = an.GetBoneTransform(HumanBodyBones.Head);
                foot = an.GetBoneTransform(HumanBodyBones.LeftFoot);
            }
            if (head == null)
                foreach (Transform t in root.GetComponentsInChildren<Transform>(true))
                    if (t.name.ToLower() == "head") { head = t; break; }
            if (head == null) { Debug.LogError("[AvatarGen] head bone not found"); return false; }
            footY = foot != null ? foot.position.y : root.transform.position.y;
            // 头骨在头顶之下，整体身高约为 (head - foot) / 0.87
            height = Mathf.Max(0.2f, (head.position.y - footY) / 0.87f);
            center = new Vector3(root.transform.position.x, footY, root.transform.position.z);
            return true;
        }

        // frac: 取景高度占全身高的比例；anchorTop: 以头顶为基准往下取
        static void Shot(float frac, bool headAnchored, string label)
        {
            float H, footY; Transform head; Vector3 c;
            if (!Measure(out H, out footY, out head, out c)) return;
            SceneView sv = SceneView.lastActiveSceneView;
            if (sv == null) { Debug.LogError("[AvatarGen] no active SceneView"); return; }

            // 经验标定：SceneView.size 不是「取景半高」，实测 0.755m 身高时
            // face 需要 0.16、upper 需要 0.62 才合适，所以系数按身高归一化直接给。
            float size = Mathf.Max(0.05f, H * frac);
            Vector3 pivot = headAnchored
                ? new Vector3(c.x, head.position.y, c.z)
                : new Vector3(c.x, footY + H * 0.5f, c.z);

            // Scene View 的近/远裁剪面默认按视距自动算。这个素体只有 0.755m 高，
            // 自动值会把头的正面裁掉，画面变成模型内壁。必须关掉动态裁剪并显式给值。
            sv.cameraSettings.dynamicClip = false;
            sv.cameraSettings.nearClip = 0.005f;
            sv.cameraSettings.farClip  = 50f;
            sv.orthographic = false;
            // 最后一个参数是 instant。传 false 时相机是平滑动画过去的，
            // 紧接着截图会拍到飞行途中（表现为相机卡在模型内部）。必须 true。
            sv.LookAt(pivot, Quaternion.Euler(0f, 180f, 0f), size, false, true);
            sv.Repaint();
            Debug.Log("[AvatarGen] SceneView -> " + label
                    + "\n  骨骼实测身高 = " + H.ToString("F3") + "m  (head.y=" + head.position.y.ToString("F3") + "  foot.y=" + footY.ToString("F3") + ")"
                    + "\n  pivot = " + pivot.ToString("F3") + "  size = " + size.ToString("F3"));
        }

        [MenuItem("Tools/AvatarGen/Shot - Face closeup", false, 40)] public static void Face()  { Shot(0.21f, true,  "face closeup"); }
        [MenuItem("Tools/AvatarGen/Shot - Head",         false, 41)] public static void Head()  { Shot(0.33f, true,  "head"); }
        [MenuItem("Tools/AvatarGen/Shot - Upper body",   false, 42)] public static void Upper() { Shot(0.62f, true,  "upper body"); }
        [MenuItem("Tools/AvatarGen/Shot - Full body",    false, 43)] public static void Full()  { Shot(1.05f, false, "full body"); }
    }
}

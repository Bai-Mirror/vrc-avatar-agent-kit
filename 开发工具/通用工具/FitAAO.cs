// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】通用工具
// 适用素体：任意
// 相关素材：AAO（Avatar Optimizer）
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4 / Modular Avatar 1.17.1 / NDMF 1.14.1 / AAO 1.9.16 / lilToon 2.3.4
// 可复用性：★★★ 换个单子直接能用
// 用途　　：反射方式挂 TraceAndOptimize 并 dump 它的私有序列化设置。AAO 运行时程序集没开 Auto Referenced，直接 using 编不过
// ══════════════════════════════════════════════════════════════════
// 挂 AAO TraceAndOptimize
//
// AAO 的运行时程序集（com.anatawa12.avatar-optimizer.runtime）没开 Auto Referenced，
// Assembly-CSharp-Editor 里 using Anatawa12.* 编不过。用反射拿类型。
// TraceAndOptimize 的设置全是私有序列化字段，没有公开 API，只能走 SerializedObject。
using System.Linq;
using System.Text;
using UnityEngine;
using UnityEditor;

namespace AvatarGen
{
    public static class FitAAO
    {
        const string TypeName   = "Anatawa12.AvatarOptimizer.TraceAndOptimize";

        static System.Type TAOType()
        {
            var t = System.AppDomain.CurrentDomain.GetAssemblies()
                .Select(a => a.GetType(TypeName)).FirstOrDefault(x => x != null);
            if (t == null) Debug.LogError("[AAO] 找不到类型 " + TypeName + "，AAO 没装？");
            return t;
        }

        static GameObject Avatar()
        {
            // 自动识别：优先当前选中的那台，否则取场景里激活的第一个 VRCAvatarDescriptor
            var sel = UnityEditor.Selection.activeGameObject;
            if (sel != null)
            {
                var d0 = sel.GetComponentInParent<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
                if (d0 != null) return d0.gameObject;
            }
            var all = Object.FindObjectsOfType<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
            var g = all.FirstOrDefault(d => d.gameObject.activeInHierarchy);
            if (g == null && all.Length > 0) g = all[0];
            if (g == null) Debug.LogError("[AAO] 场景里找不到带 VRCAvatarDescriptor 的头像");
            return g != null ? g.gameObject : null;
        }

        [MenuItem("Tools/AvatarGen/Perf - 挂 AAO TraceAndOptimize", false, 323)]
        public static void Fit()
        {
            var root = Avatar(); if (root == null) return;
            var type = TAOType(); if (type == null) return;

            var c = root.GetComponent(type);
            if (c == null)
            {
                c = Undo.AddComponent(root, type);
                Debug.Log("[AAO] 已挂 TraceAndOptimize（默认设置）");
            }
            else Debug.Log("[AAO] TraceAndOptimize 已存在");

            PrefabUtility.RecordPrefabInstancePropertyModifications(c);
            EditorUtility.SetDirty(c);
            UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(root.scene);
            UnityEditor.SceneManagement.EditorSceneManager.SaveScene(root.scene);
            DumpSettings();
        }

        [MenuItem("Tools/AvatarGen/Perf - 查看 AAO 设置", false, 324)]
        public static void DumpSettings()
        {
            var root = Avatar(); if (root == null) return;
            var type = TAOType(); if (type == null) return;
            var c = root.GetComponent(type);
            if (c == null) { Debug.LogError("[AAO] 还没挂 TraceAndOptimize"); return; }

            var sb = new StringBuilder("[AAO] TraceAndOptimize 当前设置\n");
            var so = new SerializedObject(c);
            var it = so.GetIterator();
            bool enter = true;
            while (it.NextVisible(enter))
            {
                enter = false;
                if (it.name == "m_Script") continue;
                string v;
                switch (it.propertyType)
                {
                    case SerializedPropertyType.Boolean: v = it.boolValue ? "开" : "关"; break;
                    case SerializedPropertyType.Float:   v = it.floatValue.ToString(); break;
                    case SerializedPropertyType.Integer: v = it.intValue.ToString(); break;
                    case SerializedPropertyType.Enum:
                        v = it.enumValueIndex >= 0 && it.enumValueIndex < it.enumDisplayNames.Length
                            ? it.enumDisplayNames[it.enumValueIndex] : it.intValue.ToString();
                        break;
                    case SerializedPropertyType.String:  v = it.stringValue; break;
                    default: v = "(" + it.propertyType + ")"; break;
                }
                sb.AppendLine(string.Format("   {0,-46} {1}", it.propertyPath, v));
            }
            var dir = System.IO.Path.Combine(System.IO.Directory.GetCurrentDirectory(), "Captures");
            System.IO.Directory.CreateDirectory(dir);
            System.IO.File.WriteAllText(System.IO.Path.Combine(dir, "aao_settings.txt"), sb.ToString());
            Debug.Log("[AAO] 设置已写入 Captures/aao_settings.txt");
        }

        [MenuItem("Tools/AvatarGen/Perf - 移除 AAO", false, 325)]
        public static void Remove()
        {
            var root = Avatar(); if (root == null) return;
            var type = TAOType(); if (type == null) return;
            var c = root.GetComponent(type);
            if (c != null) Undo.DestroyObjectImmediate(c);
            UnityEditor.SceneManagement.EditorSceneManager.SaveScene(root.scene);
            Debug.Log("[AAO] 已移除");
        }
    }
}

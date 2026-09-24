// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】通用工具
// 适用素体：任意
// 相关素材：无
// 工具链　：Unity 2022.3.22f1
// 可复用性：★★★ 换个单子直接能用
// 用途　　：把空材质槽（渲染成洋红）从**预制体源头**取回材质补上
// ══════════════════════════════════════════════════════════════════
// 空材质槽是最难查的一类问题：
//   · 画面上是一片洋红，看起来像 shader 出错，实际是 material 引用为 null；
//   · `Renderer.sharedMaterials` 里是 null，**shader 清单、材质清单都列不出它**
//     （没有 material 就取不到 shader），所以常规审计脚本一片正常。
// 常见成因：
//   · 材质资产被删了（例如把生成的材质放进了某个会被整目录重建的文件夹）；
//   · .unitypackage 导入时 GUID 撞车，后来者的 GUID 被丢掉，引用它的预制体断链。
//
// 修法：预制体实例的每个渲染器都能用 `PrefabUtility.GetCorrespondingObjectFromSource`
// 找到源预制体里的同一个渲染器，从那里把材质抄回来。源头没有的（场景里新建的对象）
// 修不了，但会点名报出来。
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace AvatarGen
{
    public static class FixNullMaterials
    {
        [MenuItem("Tools/AvatarGen/Fix - 查空材质槽", false, 340)]
        public static void Scan() => Run(false);

        [MenuItem("Tools/AvatarGen/Fix - 修空材质槽（从预制体源头取回）", false, 341)]
        public static void Fix() => Run(true);

        static void Run(bool doFix)
        {
            var sb = new StringBuilder(doFix ? "── 修空材质槽 ──" : "── 查空材质槽 ──");
            sb.AppendLine();
            int bad = 0, fixedN = 0;
            foreach (var d in Object.FindObjectsOfType<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>(true))
            {
                foreach (var r in d.GetComponentsInChildren<Renderer>(true))
                {
                    var mats = r.sharedMaterials;
                    if (mats == null || !mats.Any(m => m == null)) continue;
                    var path = r.name;
                    for (var t = r.transform.parent; t != null && t != d.transform; t = t.parent)
                        path = t.name + "/" + path;
                    bad++;

                    var src = PrefabUtility.GetCorrespondingObjectFromSource(r) as Renderer;
                    if (src == null)
                    {
                        sb.AppendLine($"  ✗ {path}  {mats.Count(m => m == null)}/{mats.Length} 空 —— 源预制体里找不到对应渲染器，修不了");
                        continue;
                    }
                    var sm = src.sharedMaterials;
                    bool changed = false;
                    for (int i = 0; i < mats.Length; i++)
                    {
                        if (mats[i] != null || i >= sm.Length || sm[i] == null) continue;
                        sb.AppendLine($"  ✓ {path}[{i}] ← {sm[i].name}");
                        if (doFix) { mats[i] = sm[i]; changed = true; fixedN++; }
                    }
                    if (changed) { r.sharedMaterials = mats; EditorUtility.SetDirty(r); }
                }
            }
            if (bad == 0) sb.AppendLine("  没有空材质槽");
            else sb.AppendLine($"  {bad} 个渲染器有空槽" + (doFix ? $"，补回 {fixedN} 个" : "（这是扫描，没改）"));
            System.IO.Directory.CreateDirectory("Assets/_Work");
            System.IO.File.WriteAllText("Assets/_Work/空材质槽.md", sb.ToString(), new UTF8Encoding(false));
            if (doFix)
                UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(
                    UnityEngine.SceneManagement.SceneManager.GetActiveScene());
            AssetDatabase.Refresh();
            Debug.Log(sb.ToString());
        }
    }
}

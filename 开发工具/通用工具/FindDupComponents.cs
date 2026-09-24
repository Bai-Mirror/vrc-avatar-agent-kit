// ══════════════════════════════════════════════════════════════════
// 【开发工具】通用工具
// 适用素体：任意
// 相关素材：任意 NDMF 插件
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4
// 可复用性：★★★ 改 TypeNames 就能查别的组件
// 用途　　：按类型全名找出头像上的重复组件，并删除多余的
// ══════════════════════════════════════════════════════════════════
// 很多 NDMF 插件只允许挂一个实例，多了会在自己的 pass 里抛 InvalidOperationException
// 直接中止整条构建链。症状很有迷惑性：
//   · 插件本该生成的东西（骨骼、菜单、参数）全都没生成
//   · 之后 AAO 会抱怨「检测到未知的组件类型 XXX」——因为没人处理它，组件残留了下来
//   · 报错信息可能是日文/被 NDMF 吞进 Error Reported，控制台上不显眼
// 别去猜数量超限之类的次生现象，先查重复组件。
using System.Linq;
using System.Text;
using UnityEngine;
using UnityEditor;

namespace AvatarGen
{
    public static class FindDupComponents
    {
        static readonly string[] TypeNames = {
            "ZeroFactory.AvatarPoseSystem.NDMF.AvatarPoseSystem",
        };

        static System.Collections.Generic.List<System.Type> Types() =>
            System.AppDomain.CurrentDomain.GetAssemblies()
                .SelectMany(a => { try { return a.GetTypes(); } catch { return new System.Type[0]; } })
                .Where(t => TypeNames.Contains(t.FullName)).ToList();

        [MenuItem("Tools/AvatarGen/Fix - 查重复组件", false, 340)]
        public static void Run()
        {
            var sb = new StringBuilder();
            foreach (var d in Object.FindObjectsOfType<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>(true))
            {
                sb.AppendLine($"=== 头像 {d.name}（{(d.gameObject.activeInHierarchy ? "启用" : "停用")}）===");
                foreach (var t in Types())
                {
                    var comps = d.GetComponentsInChildren(t, true);
                    sb.AppendLine($"  {t.Name}：{comps.Length} 个");
                    foreach (var c in comps)
                    {
                        var go = ((Component)c).gameObject;
                        var src = PrefabUtility.GetCorrespondingObjectFromSource(go);
                        sb.AppendLine($"     · {(go.activeInHierarchy ? "●" : "○")} 兄弟序号 {go.transform.GetSiblingIndex()}" +
                                      $"  子物体 {go.transform.childCount} 个  {AnimationUtility.CalculateTransformPath(go.transform, d.transform)}");
                        sb.AppendLine($"       来源：{(src != null ? AssetDatabase.GetAssetPath(src) : "(非预制体实例)")}");
                    }
                }
            }
            var dir = System.IO.Path.Combine(System.IO.Directory.GetCurrentDirectory(), "Captures");
            System.IO.Directory.CreateDirectory(dir);
            System.IO.File.WriteAllText(System.IO.Path.Combine(dir, "dup_components.txt"), sb.ToString());
            Debug.Log("[DupComp]\n" + sb);
        }

        [MenuItem("Tools/AvatarGen/Fix - 删除重复组件（只留第一个）", false, 341)]
        public static void Fix()
        {
            var sb = new StringBuilder();
            int killed = 0;
            foreach (var d in Object.FindObjectsOfType<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>(true))
            {
                foreach (var t in Types())
                {
                    var comps = d.GetComponentsInChildren(t, true).Cast<Component>().ToList();
                    if (comps.Count <= 1) continue;
                    sb.AppendLine($"{d.name} 上有 {comps.Count} 个 {t.Name}：");
                    for (int i = 0; i < comps.Count; i++)
                    {
                        var go = comps[i].gameObject;
                        // 是预制体实例根就整个删掉；只是多挂了组件就只删组件
                        bool whole = PrefabUtility.IsAnyPrefabInstanceRoot(go);
                        sb.AppendLine($"   [{i}] {go.name}  子物体 {go.transform.childCount} 个  " +
                                      $"{(whole ? "预制体实例根" : "普通物体")}  {(i == 0 ? "→ 保留" : "→ 删除")}");
                        if (i == 0) continue;
                        if (whole) Undo.DestroyObjectImmediate(go); else Undo.DestroyObjectImmediate(comps[i]);
                        killed++;
                    }
                    UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(d.gameObject.scene);
                }
            }
            sb.AppendLine(killed == 0 ? "没有重复，未改动。" : $"已删除 {killed} 个多余的。");
            Debug.Log("[DupComp/Fix]\n" + sb);
        }
    }
}

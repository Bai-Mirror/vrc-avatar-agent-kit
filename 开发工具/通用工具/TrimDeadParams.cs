// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】通用工具
// 适用素体：任意（参数名表需按素体改）
// 相关素材：无
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4
// 可复用性：★★ 改开头的参数名表就能用
// 用途　　：把素体自带但已无对应网格的死参数剔掉，腾出同步位
// ══════════════════════════════════════════════════════════════════
// 不直接改厂商的 ExpressionParameters 资产 —— 复制一份到 _Work 再改，
// 然后把头像的 descriptor 指向副本。厂商原件保持不动，随时能切回去。
using System.Linq;
using System.Text;
using UnityEngine;
using UnityEditor;
using VRC.SDK3.Avatars.Components;
using VRC.SDK3.Avatars.ScriptableObjects;

namespace AvatarGen
{
    public static class TrimDeadParams
    {
        // Milfy 素体自带发型与默认服装的控制参数。对应网格已被作者删除，
        // 参数留着空转 —— 已用 TraceParam 逐条追到动画曲线核实：
        // 引用它们的 VRCFury 层全部标着 (NO VALID ANIMATIONS)，
        // AAO 也留下了「对象不存在导致删除了对应键值」的占位绑定。
        static readonly string[] Dead = {
            // 默认发型形状控制（34 位）
            "FHLength",      // 刘海长度
            "TWLength",      // 双马尾长度
            "TWVolume",      // 双马尾蓬松度
            "BLength",       // 后发长度
            "FHSharp",       // 刘海尖锐
            "HairNoSide",    // 隐藏侧发
            // 默认服装部件开关（12 位）
            "Sleeve",        // 袖长
            "Cardigan_OFF",  // 开衫
            "Bottoms_OFF",   // 下装
            "Crown_OFF",     // 王冠
            "Slippers_OFF",  // 拖鞋
        };

        const string CopyPath = "Assets/_Work/EXParameter_Milfy_trimmed.asset";

        [MenuItem("Tools/AvatarGen/Perf - 剔除死参数（发型）", false, 331)]
        public static void Trim()
        {
            var all = Object.FindObjectsOfType<VRCAvatarDescriptor>();
            var d = all.FirstOrDefault(x => x.gameObject.activeInHierarchy) ?? all.FirstOrDefault();
            if (d == null) { Debug.LogError("[Trim] 找不到头像"); return; }
            var src = d.expressionParameters;
            if (src == null) { Debug.LogError("[Trim] 没有 ExpressionParameters"); return; }

            var sb = new StringBuilder();
            sb.AppendLine($"[Trim] 源资产：{AssetDatabase.GetAssetPath(src)}");

            // 复制一份再改，厂商原件不动
            var copy = Object.Instantiate(src);
            var before = copy.parameters.Length;
            var bitsBefore = copy.parameters.Sum(p => !p.networkSynced ? 0
                : p.valueType == VRCExpressionParameters.ValueType.Bool ? 1 : 8);

            var hit = copy.parameters.Where(p => Dead.Contains(p.name)).ToList();
            copy.parameters = copy.parameters.Where(p => !Dead.Contains(p.name)).ToArray();

            var bitsAfter = copy.parameters.Sum(p => !p.networkSynced ? 0
                : p.valueType == VRCExpressionParameters.ValueType.Bool ? 1 : 8);

            sb.AppendLine($"  剔除 {hit.Count} 个：{string.Join(", ", hit.Select(p => p.name))}");
            sb.AppendLine($"  参数 {before} → {copy.parameters.Length}   同步位 {bitsBefore} → {bitsAfter}（省 {bitsBefore - bitsAfter}）");
            var missing = Dead.Where(n => hit.All(p => p.name != n)).ToArray();
            if (missing.Length > 0) sb.AppendLine($"  ★名单里没找到的：{string.Join(", ", missing)}");

            System.IO.Directory.CreateDirectory("Assets/_Work");
            AssetDatabase.CreateAsset(copy, CopyPath);
            AssetDatabase.SaveAssets();
            // 先落盘再回读校验 —— CreateAsset 之后改内容会静默丢失
            var reread = AssetDatabase.LoadAssetAtPath<VRCExpressionParameters>(CopyPath);
            sb.AppendLine($"  回读校验：{(reread == null ? "✗ 读不到" : $"参数 {reread.parameters.Length} 个")}");

            Undo.RecordObject(d, "point to trimmed params");
            d.expressionParameters = reread;
            PrefabUtility.RecordPrefabInstancePropertyModifications(d);
            EditorUtility.SetDirty(d);
            UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(d.gameObject.scene);
            UnityEditor.SceneManagement.EditorSceneManager.SaveScene(d.gameObject.scene);
            sb.AppendLine($"  已把头像指向副本：{CopyPath}，场景已保存");

            var dir = System.IO.Path.Combine(System.IO.Directory.GetCurrentDirectory(), "Captures");
            System.IO.Directory.CreateDirectory(dir);
            System.IO.File.WriteAllText(System.IO.Path.Combine(dir, "trim_params.txt"), sb.ToString());
            Debug.Log("[Trim]\n" + sb);
        }
    }
}

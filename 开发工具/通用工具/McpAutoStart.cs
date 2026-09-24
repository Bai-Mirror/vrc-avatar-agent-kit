// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】通用工具
// 适用素体：无关
// 相关素材：MCP for Unity (CoplayDev) v10.x
// 工具链　：Unity 2022.3.22f1
// 可复用性：★★★ 任何装了 MCP for Unity 的工程都能用
// 用途　　：让 MCP 桥在 Unity 冷启动后自动恢复，免去每次手动点 Transport
// ══════════════════════════════════════════════════════════════════
// 机制（读 v10.1.2 源码得到，不是猜的）：
//   StdioBridgeHost 的静态构造带 [InitializeOnLoad]，冷启动时会调
//   ShouldAutoStartBridge()：
//       bool useHttpTransport = EditorConfigurationCache.Instance.UseHttpTransport;
//       return !useHttpTransport;
//   即 **stdio 模式下本来就会自动起**。
//
//   但 EditorPref "MCPForUnity.UseHttpTransport" 的**默认值是 true**
//   （见 CodexConfigHelper.cs 里的 EditorPrefs.GetBool(..., true)）。
//   只要这个键没被显式写成 false，冷启动就走 HTTP 分支、stdio 不自动起，
//   于是每次都得手动去面板选一次 Transport。
//
//   AutoStartOnLoad 那个开关只管 HTTP（HttpAutoStartHandler.TryBeginAutoStart
//   第一行就是 if (!UseHttpTransport) return true;），stdio 模式下是空转的。
//
// 所以要的就是把 UseHttpTransport 显式写成 false。
using UnityEngine;
using UnityEditor;

namespace AvatarGen
{
    public static class McpAutoStart
    {
        const string KeyHttp     = "MCPForUnity.UseHttpTransport";
        const string KeyAutoLoad = "MCPForUnity.AutoStartOnLoad";
        const string KeyResume   = "MCPForUnity.ResumeStdioAfterReload";
        const string KeyPort     = "MCPForUnity.UnitySocketPort";

        [MenuItem("Tools/AvatarGen/MCP - 查看当前设置", false, 340)]
        public static void Show()
        {
            Debug.Log(
                "[MCP] 当前 EditorPrefs\n" +
                $"   UseHttpTransport      = {EditorPrefs.GetBool(KeyHttp, true)}   （默认 true；stdio 自动启动要求它为 false）\n" +
                $"   AutoStartOnLoad       = {EditorPrefs.GetBool(KeyAutoLoad, false)}   （只对 HTTP 生效）\n" +
                $"   ResumeStdioAfterReload= {EditorPrefs.GetBool(KeyResume, true)}   （管域重载，不管冷启动）\n" +
                $"   UnitySocketPort       = {EditorPrefs.GetInt(KeyPort, 6400)}\n" +
                $"   键存在性: Http={EditorPrefs.HasKey(KeyHttp)} AutoLoad={EditorPrefs.HasKey(KeyAutoLoad)}");
        }

        [MenuItem("Tools/AvatarGen/MCP - 开启冷启动自动恢复", false, 341)]
        public static void Enable()
        {
            EditorPrefs.SetBool(KeyHttp, false);      // 关键：显式写 false，走 stdio 自动启动分支
            EditorPrefs.SetBool(KeyResume, true);     // 域重载后也恢复
            EditorPrefs.SetBool(KeyAutoLoad, true);   // 顺手打开，将来若切 HTTP 也自动起
            Debug.Log(
                "[MCP] 已设置：\n" +
                $"   UseHttpTransport = {EditorPrefs.GetBool(KeyHttp, true)}（显式 false → stdio 冷启动自动起）\n" +
                $"   ResumeStdioAfterReload = {EditorPrefs.GetBool(KeyResume, true)}\n" +
                $"   AutoStartOnLoad = {EditorPrefs.GetBool(KeyAutoLoad, false)}\n" +
                "   重启 Unity 后应当无需手动点 Transport。");
        }
    }
}

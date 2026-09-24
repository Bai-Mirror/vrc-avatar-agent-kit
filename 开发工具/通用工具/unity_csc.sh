#!/usr/bin/env bash
# 【项目沉淀】通用工具
# 适用素体：无关
# 相关素材：Unity 工程 Library/Bee 的 .rsp
# 工具链　：bash + Unity 2022.3.22f1
# 可复用性：★★★ 换个单子直接能用
# 用途　　：用工程自己的 .rsp 离线编译 Unity 程序集，不进 Unity、不触发域重载。
#
# 用「工程自己的 .rsp」离线编译 Unity 程序集，不进 Unity、不触发域重载。
#
# 为什么不手搓 -r 列表：手搓必踩两个坑——
#   CS0433「MenuItem 同时存在于 UnityEditor 和 UnityEditor.CoreModule」（单体 dll 与模块 dll 撞车）
#   CS0518「预定义类型 System.Object 未定义」（mscorlib / netstandard 少给或给重）
# Unity 自己编译时把完整正确的引用集写在 Library/Bee/artifacts/*.dag/<程序集>.rsp 里，直接用它。
#
# 用法：unity_csc.sh <工程根> [程序集名，默认 Assembly-CSharp-Editor]
# 退出码 0 = 编译通过。错误原样打印。
set -u
PROJ="${1:?给工程根目录}"
ASM="${2:-Assembly-CSharp-Editor}"
. "$(dirname "${BASH_SOURCE[0]}")/kit_env.sh"
UNITY=$(kit_unity_data)
[ -d "$UNITY" ] || { echo "找不到 Unity Data 目录: $UNITY（在 kit.env 设 UNITY_DATA 或 UNITY_EDITOR_ROOT/UNITY_VERSION）" >&2; exit 2; }

cd "$PROJ" || exit 2
RSP=$(ls -t Library/Bee/artifacts/*.dag/"$ASM".rsp 2>/dev/null | head -1)
if [ -z "$RSP" ]; then
  echo "找不到 $ASM 的 rsp（Library/Bee/artifacts/*.dag/）——工程至少要被 Unity 成功编译过一次" >&2
  exit 2
fi
OUT=$(mktemp -d)/"$ASM".dll
TMPRSP=$(mktemp --suffix=.rsp)
grep -vE '^-out:|^"?Assets/' "$RSP"  > "$TMPRSP"
echo "-out:$OUT"                    >> "$TMPRSP"
grep -E  '^"?Assets/' "$RSP"        >> "$TMPRSP"

"$UNITY/NetCoreRuntime/dotnet" "$UNITY/DotNetSdkRoslyn/csc.dll" -nostdlib -noconfig -nologo "@$TMPRSP"
rc=$?
rm -f "$TMPRSP"
[ $rc -eq 0 ] && echo "✅ $ASM 编译通过（$RSP）"
exit $rc

#!/bin/bash
# 【项目沉淀】通用工具
# 适用素体：无关          相关素材：无
# 可复用性：★★★ 换个单子直接能用
# 用途　　：Unity 崩溃 / 卡死 / OOM 后的恢复检查与清理。缺省只报告（进程、日志尾、锁、MCP 状态、工程未提交改动）；
#           `--yes` 才清陈旧锁与状态文件，且只在该工程没有活进程时；`--launch` 再用 unity_run.sh 重开。绝不自动存盘、绝不丢改动。
# 为什么（工作流审理 2026-09-23，A6）：41 条豁免里 30 余条是崩溃兜底，每次十几次直调；收成一条命令，同时把「进程还在就不许删锁」写死。
# 用法：unity_recover.sh <工程目录> [--yes] [--launch] [--batch]
set -u
export LC_ALL=C
. "$(dirname "${BASH_SOURCE[0]}")/kit_env.sh"   # W＝工作区根；Unity 路径见 kit.env
PROJ=${1:-}; shift || true
YES=0; LAUNCH=0; BATCH=""
for a in "$@"; do case "$a" in --yes) YES=1;; --launch) LAUNCH=1;; --batch) BATCH=--batch;; esac; done
[ -z "$PROJ" ] && { echo "用法: unity_recover.sh <工程目录> [--yes] [--launch]" >&2; exit 2; }
PROJ=$(cd "$PROJ" 2>/dev/null && pwd) || { echo "工程目录不存在" >&2; exit 2; }
NAME=$(basename "$PROJ")
# 找「正在用 $1 这个工程目录」的 Unity 进程，打印 pid（空＝没有）。
# 2026-09-25 修：原来是 pgrep -f "Editor/Unity.*-projectPath.*$NAME"，$NAME 直接进正则——工程名含 . + ( [ 之类
# 会匹配错（`+` 让字面的 “j+1” 匹配不上），误判「无进程」后 unity_run 会删掉活实例的 Temp/UnityLockfile。
# 现在不拼正则：先用固定模式列出 Unity 相关进程，再逐个读 /proc/<pid>/cmdline 取 -projectPath 的值做字符串比较。
# 保守原则（拿不准就算「有活进程」）：路径解析后相同，或末级目录名相同，或 cmdline 读不到，都算占用；
# pgrep 本身出错（退出码 ≥2）则返回 2，调用方据此拒绝删锁。
unity_pids_for() {
  local proj=$1 name all p a v i found rc
  name=$(basename "$proj")
  all=$(pgrep -f 'Editor/Unity'); rc=$?
  [ $rc -ge 2 ] && return 2
  for p in $all; do
    [ "$p" = "$$" ] && continue
    [ -e "/proc/$p" ] || continue                       # 已退出
    if ! [ -r "/proc/$p/cmdline" ]; then echo "$p"; continue; fi
    local -a args=()
    mapfile -d '' -t args < "/proc/$p/cmdline" 2>/dev/null || { echo "$p"; continue; }
    found=0
    for ((i = 0; i < ${#args[@]} - 1; i++)); do
      a=${args[$i]}
      [ "${a,,}" = "-projectpath" ] || continue
      v=${args[$((i + 1))]}
      v=${v%/}
      if [ "${v:0:1}" != "/" ]; then v="$(readlink "/proc/$p/cwd" 2>/dev/null)/$v"; fi
      if [ "$(realpath -m -- "$v" 2>/dev/null)" = "$proj" ] || [ "$(basename -- "$v")" = "$name" ]; then found=1; fi
    done
    [ $found = 1 ] && echo "$p"
  done
  return 0
}
echo "【Unity 恢复检查 · $NAME · $(date '+%m-%d %H:%M')】"
echo "-- 进程:"
pids=$(unity_pids_for "$PROJ") || { echo "  查不了进程（pgrep 出错）——无法判断，按「有活进程」处理，不清任何锁"; exit 1; }
if [ -n "$pids" ]; then
  for p in $pids; do echo "  pid $p stat $(ps -o stat= -p $p) etime $(ps -o etime= -p $p | tr -d ' ') cpu $(ps -o %cpu= -p $p) rss $(( $(ps -o rss= -p $p) / 1024 ))MB"; done
else echo "  无（该工程没有 Unity 进程）"; fi
echo "-- 日志尾（~/.config/unity3d/Editor.log 与 Editor-prev.log 最后 6 行）:"
for L in "$HOME/.config/unity3d/Editor.log" "$HOME/.config/unity3d/Editor-prev.log"; do
  [ -f "$L" ] && { echo "  [$(basename "$L") $(date -r "$L" '+%m-%d %H:%M')]"; tail -6 "$L" | cut -c1-160 | sed 's/^/    /'; }
done
crash=$(tail -40 "$HOME/.config/unity3d/Editor.log" 2>/dev/null | grep -cE 'Launching bug reporter|Crash!!!|Stacktrace|SIGSEGV|Obtained [0-9]+ stack frames' || true)
[ "$crash" -gt 0 ] && echo "  ⚠ 日志尾有崩溃迹象（$crash 行）"
echo "-- 锁与状态文件:"
[ -f "$PROJ/Temp/UnityLockfile" ] && echo "  Temp/UnityLockfile: 在" || echo "  Temp/UnityLockfile: 无"
if [ -f "$HOME/.dsh/handoff.lock" ]; then h=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d.get('kind'),d.get('holder'),d.get('pid'))" "$HOME/.dsh/handoff.lock" 2>/dev/null); hp=$(echo "$h" | awk '{print $3}'); kill -0 "$hp" 2>/dev/null && echo "  handoff.lock: $h（持有者活）" || echo "  handoff.lock: $h（持有者死，可删）"; else echo "  handoff.lock: 无"; fi
ls "$HOME"/.unity-mcp/unity-mcp-status-*.json 2>/dev/null | sed 's/^/  mcp状态: /'
echo "-- 工程未提交改动:"
cd "$W" || exit 1; n=$(git -c core.quotepath=false status --porcelain -- "$NAME" | wc -l); echo "  $n 个（ProjectSettings: $(git -c core.quotepath=false status --porcelain -- "$NAME/ProjectSettings" | wc -l)）"
git -c core.quotepath=false status --porcelain -- "$NAME" | head -5 | sed 's/^/    /'
echo "-- 判定:"
if [ -n "$pids" ]; then
  echo "  进程仍在。若日志尾是崩溃栈/bug reporter → 是「崩溃未退出」：先 kill 该 pid（自己起的会话可直接结束，用户在用的先问），确认消失后再跑本脚本 --yes。不许删锁、不许同工程另起实例。"
  exit 1
fi
echo "  无活进程。可清：Temp/UnityLockfile、死持有者的 handoff.lock、陈旧 mcp 状态文件。场景无法从外部判 dirty——未提交改动按上面清单自己看，别 checkout。"
if [ $YES = 1 ]; then
  rm -f "$PROJ/Temp/UnityLockfile" && echo "  已删 Temp/UnityLockfile"
  if [ -f "$HOME/.dsh/handoff.lock" ]; then hp=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('pid',''))" "$HOME/.dsh/handoff.lock" 2>/dev/null); kill -0 "$hp" 2>/dev/null || { rm -f "$HOME/.dsh/handoff.lock"; echo "  已删死持有者的 handoff.lock"; }; fi
  if ! pgrep -f 'Editor/Unity( |$)' >/dev/null; then rm -f "$HOME"/.unity-mcp/unity-mcp-status-*.json 2>/dev/null && echo "  已删陈旧 mcp 状态文件（全机无 Unity）"; else echo "  别的 Unity 还在，mcp 状态文件不动"; fi
  find "$W" -maxdepth 3 -path '*_dsh_tmp*' -name '.credentials*' 2>/dev/null | sed 's/^/  ⚠ 影子凭据残留: /'
fi
if [ $LAUNCH = 1 ]; then bash "$W/开发工具/通用工具/unity_run.sh" --project "$PROJ" $BATCH; else echo "  重开：bash 开发工具/通用工具/unity_run.sh --project $NAME $BATCH"; fi

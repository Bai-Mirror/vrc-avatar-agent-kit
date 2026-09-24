#!/bin/bash
# 【项目沉淀】通用工具
# 适用素体：无关          相关素材：无
# 可复用性：★★★ 换个单子直接能用
# 用途　　：统一的 Unity 启动器。交互或批处理都从这里起：一律 -force-vulkan；起前查可用内存；工程已有活的 Unity 就拒绝另起；
#           批处理串行 flock（全机一把锁）；进程挂在 systemd 用户单元里带 MemoryMax，超限只死这个 Unity，不再拖垮整个 Claude 进程组。
# 为什么（工作流审理 2026-09-23，B4/B5）：5 天 10 次崩溃，其中 09-22 20:28 内核 OOM 把 Claude 进程组全灭；4 次同一 Vulkan 交换链栈都来自
#           交互编辑器里跑构建/预处理弹进度条——所以完整构建与 NDMF 预处理改走批处理。
# 用法：
#   unity_run.sh --project <工程目录> [--batch] [--method Ns.Class.Method] [--nographics] [--mem 14G] [--min-gb 8]
#                [--log <文件>] [--extra "<其它 Unity 参数>"] [--no-systemd] [--dry-run]
#   交互：默认 MemoryMax 14G，后台分离，日志走 journalctl --user -u <单元名>；批处理：默认 10G，前台等待并返回 Unity 退出码。
# 退出码：0 起成功/批处理跑完；2 参数错；3 内存不够；4 该工程已有活的 Unity；5 批处理锁被占；其它=Unity 退出码。
set -u
export LC_ALL=C
# 路径全部来自 kit.env / 环境变量（见仓库根 kit.env.example）；W＝工作区根，缺省按本脚本位置推算。
. "$(dirname "${BASH_SOURCE[0]}")/kit_env.sh"
U=$(kit_unity_bin)
DISP=${DISPLAY:-${DISPLAY_FALLBACK:-:0}}
LOCK=${UNITY_BATCH_LOCK:-${XDG_RUNTIME_DIR:-/tmp}/vrc-kit-unity-batch.lock}
usage() { sed -n '9,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; echo "当前：工作区=$W  Unity=$U  DISPLAY=$DISP  锁=$LOCK"; }
PROJ=""; BATCH=0; METHOD=""; NOGFX=0; MEM=""; MINGB=""; LOG=""; EXTRA=""; NOSYSD=0; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --project) PROJ=$2; shift 2;; --batch) BATCH=1; shift;; --method) METHOD=$2; shift 2;; --nographics) NOGFX=1; shift;;
    --mem) MEM=$2; shift 2;; --min-gb) MINGB=$2; shift 2;; --log) LOG=$2; shift 2;; --extra) EXTRA=$2; shift 2;;
    --no-systemd) NOSYSD=1; shift;; --dry-run) DRY=1; shift;; -h|--help) usage; exit 0;; *) echo "未知参数 $1" >&2; exit 2;;
  esac
done
[ -z "$PROJ" ] && { echo "要 --project <工程目录>" >&2; exit 2; }
[ -x "$U" ] || [ $DRY = 1 ] || { echo "找不到 Unity 可执行文件: $U（在 kit.env 设 UNITY_BIN 或 UNITY_EDITOR_ROOT/UNITY_VERSION）" >&2; exit 2; }
PROJ=$(cd "$PROJ" 2>/dev/null && pwd) || { echo "工程目录不存在" >&2; exit 2; }
[ -f "$PROJ/Packages/manifest.json" ] || { echo "不像 Unity 工程（无 Packages/manifest.json）: $PROJ" >&2; exit 2; }
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
[ -z "$MEM" ] && MEM=$([ $BATCH = 1 ] && echo 10G || echo 14G)
[ -z "$MINGB" ] && MINGB=$([ $BATCH = 1 ] && echo 6 || echo 8)
avail=$(free -g | awk '/^Mem:/{print $7}')
[ "$avail" -lt "$MINGB" ] && { echo "可用内存 ${avail}G < ${MINGB}G，不起（SOP 02/内存预算与并发）" >&2; exit 3; }
live=$(unity_pids_for "$PROJ") || { echo "查不了进程（pgrep 出错），不起" >&2; exit 4; }
if [ -n "$live" ]; then
  echo "该工程已有活的 Unity（pid $(echo $live)），不许另起实例（SOP 图形API与原生崩溃 §09-23）" >&2; exit 4
fi
ARGS=(-projectPath "$PROJ" -force-vulkan)
if [ $BATCH = 1 ]; then
  [ -z "$LOG" ] && LOG=/tmp/unity_batch_${NAME}_$(date +%Y%m%d_%H%M%S).log
  ARGS+=(-batchmode -quit -logFile "$LOG"); [ $NOGFX = 1 ] && ARGS+=(-nographics); [ -n "$METHOD" ] && ARGS+=(-executeMethod "$METHOD")
fi
# --extra 按空白切成多个参数，但不做通配展开（原来 ARGS+=($EXTRA) 会把 * ? [ 当 glob 展开）；含空格的单个参数不支持。
if [ -n "$EXTRA" ]; then read -ra EXTRA_ARR <<< "$EXTRA"; ARGS+=("${EXTRA_ARR[@]}"); fi
UNIT=unity-$([ $BATCH = 1 ] && echo batch || echo ui)-$(echo "$NAME" | tr -c 'A-Za-z0-9_\n' '_')-$(date +%H%M%S)
ENVS=(--setenv=DISPLAY=$DISP --setenv=AVATARAUDIT_SUPPRESS_DIALOGS=1); [ -n "${XAUTHORITY:-}" ] && ENVS+=(--setenv=XAUTHORITY=$XAUTHORITY)
have_sysd=0; [ $NOSYSD = 0 ] && systemd-run --user --scope --quiet -p MemoryMax=64M true 2>/dev/null && have_sysd=1
if [ $have_sysd = 1 ]; then
  if [ $BATCH = 1 ]; then CMD=(systemd-run --user --wait --pipe --collect --quiet --unit="$UNIT" -p "MemoryMax=$MEM" -p MemorySwapMax=0 "${ENVS[@]}" "$U" "${ARGS[@]}")
  else CMD=(systemd-run --user --collect --quiet --unit="$UNIT" -p "MemoryMax=$MEM" -p MemorySwapMax=0 "${ENVS[@]}" "$U" "${ARGS[@]}"); fi
else
  CMD=(env DISPLAY=$DISP AVATARAUDIT_SUPPRESS_DIALOGS=1 "$U" "${ARGS[@]}")
fi
echo "[unity_run] $([ $BATCH = 1 ] && echo 批处理 || echo 交互) $NAME  MemoryMax=$MEM  systemd=$have_sysd  单元=$UNIT" >&2
[ -n "$LOG" ] && echo "[unity_run] 日志: $LOG" >&2
if [ $DRY = 1 ]; then printf '%q ' "${CMD[@]}"; echo; exit 0; fi
if [ $BATCH = 1 ]; then
  mkdir -p "$(dirname "$LOCK")"
  exec 9>"$LOCK"; flock -n 9 || { echo "批处理锁被占（$LOCK），另一个批处理 Unity 在跑；不排队叠加" >&2; exit 5; }
  # 拿到锁后再查一次（前面检查到这里之间可能有人起了实例）；拿不准就不删，交给 Unity 自己报锁。
  if live=$(unity_pids_for "$PROJ") && [ -z "$live" ]; then rm -f "$PROJ/Temp/UnityLockfile"
  else echo "[unity_run] 复查到活进程或无法判断（${live:-pgrep 出错}），不删 Temp/UnityLockfile" >&2; fi
  "${CMD[@]}"; rc=$?
  echo "[unity_run] Unity 退出码 $rc；error CS: $(grep -c 'error CS' "$LOG" 2>/dev/null || echo ?)" >&2
  exit $rc
else
  if [ $have_sysd = 1 ]; then "${CMD[@]}"; rc=$?; echo "[unity_run] 已起（journalctl --user -u $UNIT -f 看日志）" >&2; exit $rc
  else setsid nohup "${CMD[@]}" >"/tmp/unity_ui_${NAME}.out" 2>&1 & echo "[unity_run] 已起 pid $!（无 systemd，日志 /tmp/unity_ui_${NAME}.out）" >&2; fi
fi

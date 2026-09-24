# 读取工作区根的 kit.env（KEY=VALUE），环境变量优先。与 kit_env.py / kit_env.js 同口径。用 source 引入：
#   . "$(dirname "${BASH_SOURCE[0]}")/kit_env.sh"   # 之后 $W＝工作区根（VRC_WS，缺省按本文件位置推算），kit.env 的键已导出
# 只解析 KEY=VALUE 行（可带 export 前缀、可加引号），# 开头为注释；值里的 ~ 与 $VAR/${VAR} 会展开。
# 不直接 `set -a; . kit.env`：那样 kit.env 会压过已设的环境变量，也会执行其中的任意命令。
kit_env_load() {
  local f=$1 line k v n name m
  [ -f "$f" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    line=${line%$'\r'}
    [[ "$line" =~ ^[[:space:]]*(export[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=(.*)$ ]] || continue
    k=${BASH_REMATCH[2]}; v=${BASH_REMATCH[3]}
    v="${v#"${v%%[![:space:]]*}"}"; v="${v%"${v##*[![:space:]]}"}"
    if [[ ${#v} -ge 2 && ( ( "${v:0:1}" == '"' && "${v: -1}" == '"' ) || ( "${v:0:1}" == "'" && "${v: -1}" == "'" ) ) ]]; then
      v=${v:1:${#v}-2}
    else
      v=${v%% \#*}; v="${v%"${v##*[![:space:]]}"}"
    fi
    [ -z "$v" ] && continue                           # 空值＝没设，不导出
    [ -n "${!k+x}" ] && continue                      # 环境变量优先
    for n in 1 2 3 4 5 6 7 8; do                      # 展开 $VAR / ${VAR}（只展开已设的变量）
      [[ "$v" =~ \$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*) ]] || break
      name=${BASH_REMATCH[1]:-${BASH_REMATCH[2]}}; m=${BASH_REMATCH[0]}
      [ -n "${!name+x}" ] || break
      v=${v/"$m"/"${!name}"}
    done
    [[ "$v" == "~" || "$v" == "~/"* ]] && v="$HOME${v:1}"
    export "$k=$v"
  done < "$f"
}
_kit_env_here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
_kit_ws_env=${VRC_WS:-}
W=${VRC_WS:-$(cd "$_kit_env_here/../.." && pwd)}
[[ "$W" == "~" || "$W" == "~/"* ]] && W="$HOME${W:1}"
kit_env_load "$W/kit.env"
# kit.env 里写了 VRC_WS：工具仓库与工作区分开放
[ -z "$_kit_ws_env" ] && [ -n "${VRC_WS:-}" ] && W=$VRC_WS
unset _kit_ws_env
unset _kit_env_here
# Unity 可执行文件与 Data 目录的推导（UNITY_BIN / UNITY_DATA 显式给了就用；否则由 UNITY_EDITOR_ROOT + UNITY_VERSION 拼）
kit_unity_bin() {
  if [ -n "${UNITY_BIN:-}" ]; then echo "$UNITY_BIN"; return; fi
  echo "${UNITY_EDITOR_ROOT:-$HOME/Unity/Hub/Editor}/${UNITY_VERSION:-2022.3.22f1}/Editor/Unity"
}
kit_unity_data() {
  if [ -n "${UNITY_DATA:-}" ]; then echo "$UNITY_DATA"; return; fi
  echo "$(dirname "$(kit_unity_bin)")/Data"
}

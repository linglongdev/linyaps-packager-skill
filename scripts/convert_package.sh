#!/usr/bin/env bash
set -euo pipefail

# 脚本版本
SCRIPT_VERSION="2.0.0"

# 全局变量
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Usage:
  convert_package.sh deb <deb-file> [options]
  convert_package.sh appimage <appimage-file> --id <appid> --version <ver> [options]
  convert_package.sh flatpak <app-id> [options]

Deb conversion options:
  --workdir <dir>              Working directory (default: ./pica-work)
  --enable-compact-check       Enable compact check after build (default: true)
  --no-compact-check           Disable compact check
  --compact-check-timeout <s>  Compact check timeout in seconds (default: 30)
  --enable-layer-export        Export layer if build passes (default: true)
  --no-layer-export            Disable layer export
  --final-missing-csv <path>   Path to final-missing CSV file for package info lookup
  --ll-stored-pool <dir>       Directory to store exported layers (default: ./StoredPool)
  --verbose                    Show verbose output
  --quiet                      Show only final results

AppImage conversion options:
  --id <appid>                 Application ID (required)
  --version <ver>              Version (required)
  --name <name>                Application name
  --description <text>         Description
  --workdir <dir>              Working directory
  --build                      Build after conversion

Flatpak conversion options:
  --base <base>                Base package
  --base-version <ver>         Base version
  --version <ver>              Version
  --build                      Build after conversion
  --layer                      Export layer

Common options:
  -h, --help                   Show this help message
EOF
}

emit_and_run() {
  printf 'Running:'
  for arg in "$@"; do
    printf ' %q' "$arg"
  done
  printf '\n'
  "$@"
}

# 检查 ll-pica 是否支持指定的子命令
supports_modern_subcommand() {
  local command_name="$1"
  if ! command -v ll-pica >/dev/null 2>&1; then
    return 1
  fi
  local help_output
  help_output="$(ll-pica --help 2>&1 || true)"
  awk -v cmd="$command_name" '
    /^Available Commands:/ { in_commands=1; next }
    in_commands && NF == 0 { exit 1 }
    in_commands {
      if ($1 == cmd) {
        found = 1
        exit 0
      }
    }
    END { exit(found ? 0 : 1) }
  ' <<<"$help_output"
}

# Deb 转换函数（使用内置的 deb_converter.py）
deb_convert() {
  local deb_file="$1"
  local workdir="$2"
  local enable_compact_check="$3"
  local compact_check_timeout="$4"
  local enable_layer_export="$5"
  local final_missing_csv="$6"
  local ll_stored_pool="$7"
  local verbose="$8"
  local quiet="$9"

  # 设置默认值
  [ -n "${workdir}" ] || workdir="$(dirname "$(realpath "${deb_file}")")/pica-work"
  [ -n "${ll_stored_pool}" ] || ll_stored_pool="$(dirname "$(realpath "${deb_file}")")/StoredPool"

  # 构建 Python 命令
  local python_cmd=(
    python3
    "${SCRIPT_DIR}/deb_converter.py"
    "${deb_file}"
    --workdir "${workdir}"
    --compact-check-timeout "${compact_check_timeout}"
    --ll-stored-pool "${ll_stored_pool}"
  )

  # 添加布尔参数（action="store_true" 不接受值）
  if [ "${enable_compact_check}" = "true" ]; then
    python_cmd+=(--enable-compact-check)
  else
    python_cmd+=(--no-compact-check)
  fi

  if [ "${enable_layer_export}" = "true" ]; then
    python_cmd+=(--enable-layer-export)
  else
    python_cmd+=(--no-layer-export)
  fi

  # 添加可选参数
  if [ -n "${final_missing_csv}" ]; then
    python_cmd+=(--final-missing-csv "${final_missing_csv}")
  fi

  if [ "${verbose}" = "true" ]; then
    python_cmd+=(--verbose)
  fi

  if [ "${quiet}" = "true" ]; then
    python_cmd+=(--quiet)
  fi

  # 执行转换
  emit_and_run "${python_cmd[@]}"
}

# AppImage 转换函数
appimage_convert() {
  local appimage_file="$1"
  local app_id="$2"
  local version="$3"
  local name="$4"
  local description="$5"
  local workdir="$6"
  local build_flag="$7"

  if [[ ! -f "${appimage_file}" ]]; then
    echo "AppImage file not found: ${appimage_file}" >&2
    exit 1
  fi

  [[ -n "${app_id}" ]] || {
    echo "--id is required for appimage conversion" >&2
    exit 1
  }

  [[ -n "${version}" ]] || {
    echo "--version is required for appimage conversion" >&2
    exit 1
  }

  local cmd=(ll-pica appimage convert -f "${appimage_file}" -i "${app_id}" -v "${version}")

  if [[ -n "${name}" ]]; then
    cmd+=(-n "${name}")
  fi

  if [[ -n "${description}" ]]; then
    cmd+=(-d "${description}")
  fi

  if [[ -n "${workdir}" ]]; then
    cmd+=(-w "${workdir}")
  fi

  if [[ "${build_flag}" -eq 1 ]]; then
    cmd+=(-b)
  fi

  emit_and_run "${cmd[@]}"
}

# Flatpak 转换函数
flatpak_convert() {
  local flatpak_id="$1"
  local base="$2"
  local base_version="$3"
  local version="$4"
  local build_flag="$5"
  local layer="$6"

  [[ -n "${flatpak_id}" ]] || {
    echo "Flatpak app id is required" >&2
    exit 1
  }

  local cmd=(ll-pica flatpak convert "${flatpak_id}")

  if [[ -n "${base}" ]]; then
    cmd+=(--base "${base}")
  fi

  if [[ -n "${base_version}" ]]; then
    cmd+=(--base-version "${base_version}")
  fi

  if [[ -n "${version}" ]]; then
    cmd+=(--version "${version}")
  fi

  if [[ "${build_flag}" -eq 1 ]]; then
    cmd+=(--build)
  fi

  if [[ "${layer}" -eq 1 ]]; then
    cmd+=(--layer)
  fi

  emit_and_run "${cmd[@]}"
}

# 主函数
main() {
  if [[ $# -lt 2 ]]; then
    usage
    exit 1
  fi

  kind="$1"
  shift
  target="$1"
  shift

  # 通用参数
  workdir=""
  verbose="false"
  quiet="false"

  # Deb 专用参数
  enable_compact_check="true"
  compact_check_timeout=30
  enable_layer_export="true"
  final_missing_csv=""
  ll_stored_pool=""

  # AppImage 专用参数
  app_id=""
  version=""
  name=""
  description=""
  build_flag=0

  # Flatpak 专用参数
  base=""
  base_version=""
  layer=0

  # 解析参数
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --workdir)
        workdir="$2"
        shift 2
        ;;
      --verbose)
        verbose="true"
        shift
        ;;
      --quiet)
        quiet="true"
        shift
        ;;
      --enable-compact-check)
        enable_compact_check="true"
        shift
        ;;
      --no-compact-check)
        enable_compact_check="false"
        shift
        ;;
      --compact-check-timeout)
        compact_check_timeout="$2"
        shift 2
        ;;
      --enable-layer-export)
        enable_layer_export="true"
        shift
        ;;
      --no-layer-export)
        enable_layer_export="false"
        shift
        ;;
      --final-missing-csv)
        final_missing_csv="$2"
        shift 2
        ;;
      --ll-stored-pool)
        ll_stored_pool="$2"
        shift 2
        ;;
      --id)
        app_id="$2"
        shift 2
        ;;
      --version)
        version="$2"
        shift 2
        ;;
      --name)
        name="$2"
        shift 2
        ;;
      --description)
        description="$2"
        shift 2
        ;;
      --build)
        build_flag=1
        shift
        ;;
      --base)
        base="$2"
        shift 2
        ;;
      --base-version)
        base_version="$2"
        shift 2
        ;;
      --layer)
        layer=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "Unknown argument: $1" >&2
        usage
        exit 1
        ;;
    esac
  done

  # 检查 ll-pica 是否可用
  if ! command -v ll-pica >/dev/null 2>&1; then
    echo "ll-pica is required for deb/appimage/flatpak conversion." >&2
    echo "Install the linglong-pica package first, then rerun this command." >&2
    exit 1
  fi

  # 根据类型执行转换
  case "$kind" in
    deb)
      if [[ ! -f "$target" ]]; then
        echo "deb file not found: $target" >&2
        exit 1
      fi

      echo "Using built-in deb_converter.py for deb conversion"
      deb_convert \
        "${target}" \
        "${workdir}" \
        "${enable_compact_check}" \
        "${compact_check_timeout}" \
        "${enable_layer_export}" \
        "${final_missing_csv}" \
        "${ll_stored_pool}" \
        "${verbose}" \
        "${quiet}"
      ;;
    appimage)
      if ! supports_modern_subcommand "appimage"; then
        echo "The installed ll-pica does not provide the 'appimage' converter." >&2
        echo "Install or upgrade the linglong-pica package, then rerun this command." >&2
        exit 1
      fi
      appimage_convert \
        "${target}" \
        "${app_id}" \
        "${version}" \
        "${name}" \
        "${description}" \
        "${workdir}" \
        "${build_flag}"
      ;;
    flatpak)
      if ! supports_modern_subcommand "flatpak"; then
        echo "The installed ll-pica does not provide the 'flatpak' converter." >&2
        echo "Install or upgrade the linglong-pica package, then rerun this command." >&2
        exit 1
      fi
      flatpak_convert \
        "${target}" \
        "${base}" \
        "${base_version}" \
        "${version}" \
        "${build_flag}" \
        "${layer}"
      ;;
    *)
      echo "Unsupported conversion type: $kind" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"

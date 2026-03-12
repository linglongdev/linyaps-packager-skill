#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  convert_package.sh deb <deb-file> [--workdir <dir>] [--build]
  convert_package.sh appimage <appimage-file> --id <appid> --version <ver> [--name <name>] [--description <text>] [--build]
  convert_package.sh flatpak <app-id> [--build] [--base <base>] [--base-version <ver>] [--version <ver>] [--layer]
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

if [[ $# -lt 2 ]]; then
  usage
  exit 1
fi

kind="$1"
shift
target="$1"
shift

workdir=""
build_flag=0
app_id=""
version=""
name=""
description=""
base=""
base_version=""
layer=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workdir)
      workdir="$2"
      shift 2
      ;;
    --build)
      build_flag=1
      shift
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

if ! command -v ll-pica >/dev/null 2>&1; then
  echo "ll-pica is required for deb/appimage/flatpak conversion." >&2
  echo "Install the linglong-pica package first, then rerun this command." >&2
  exit 1
fi

if ! supports_modern_subcommand "$kind"; then
  echo "The installed ll-pica does not provide the '$kind' converter." >&2
  echo "Install or upgrade the linglong-pica package, then rerun this command." >&2
  exit 1
fi

runner=(ll-pica)

case "$kind" in
  deb)
    if [[ ! -f "$target" ]]; then
      echo "deb file not found: $target" >&2
      exit 1
    fi
    [[ -n "$workdir" ]] || workdir="$(dirname "$(realpath "$target")")/pica-work"
    cmd=("${runner[@]}" deb convert -c "$target" -w "$workdir")
    if [[ "$build_flag" -eq 1 ]]; then
      cmd+=(-b)
    fi
    ;;
  appimage)
    if [[ ! -f "$target" ]]; then
      echo "AppImage file not found: $target" >&2
      exit 1
    fi
    [[ -n "$app_id" ]] || {
      echo "--id is required for appimage conversion" >&2
      exit 1
    }
    [[ -n "$version" ]] || {
      echo "--version is required for appimage conversion" >&2
      exit 1
    }
    cmd=("${runner[@]}" appimage convert -f "$target" -i "$app_id" -v "$version")
    if [[ -n "$name" ]]; then
      cmd+=(-n "$name")
    fi
    if [[ -n "$description" ]]; then
      cmd+=(-d "$description")
    fi
    if [[ "$build_flag" -eq 1 ]]; then
      cmd+=(-b)
    fi
    ;;
  flatpak)
    [[ -n "$target" ]] || {
      echo "Flatpak app id is required" >&2
      exit 1
    }
    cmd=("${runner[@]}" flatpak convert "$target")
    if [[ -n "$base" ]]; then
      cmd+=(--base "$base")
    fi
    if [[ -n "$base_version" ]]; then
      cmd+=(--base-version "$base_version")
    fi
    if [[ -n "$version" ]]; then
      cmd+=(--version "$version")
    fi
    if [[ "$build_flag" -eq 1 ]]; then
      cmd+=(--build)
    fi
    if [[ "$layer" -eq 1 ]]; then
      cmd+=(--layer)
    fi
    ;;
  *)
    echo "Unsupported conversion type: $kind" >&2
    usage
    exit 1
    ;;
esac

emit_and_run "${cmd[@]}"

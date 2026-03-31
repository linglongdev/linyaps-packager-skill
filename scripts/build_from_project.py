#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import yaml

# Import build flow controller modules for compat-check and dependency fix
try:
    from build_flow_controller import BuildFlowController
except ImportError:
    BuildFlowController = None


DOC_PATTERNS = ["README", "INSTALL", "BUILD", "CONTRIBUTING"]
SUPPORTED_FILES = [
    "CMakeLists.txt",
    "meson.build",
    "go.mod",
    "package.json",
    "pyproject.toml",
    "setup.py",
    "Makefile",
]

RUNTIME_BASE_MAP = {
    "org.deepin.runtime.dtk/25.2.1": "org.deepin.base/25.2.1",
    "org.deepin.runtime.webengine/25.2.0": "org.deepin.base/25.2.0",
    "org.deepin.runtime.dtk/23.1.0": "org.deepin.base/23.1.0",
}

RUNTIME_ALIASES = {
    "org.deepin.Runtime/23.1.0": "org.deepin.runtime.dtk/23.1.0",
}

REPO_PRIORITY = {
    "stable": 0,
    "uos-stable": 1,
    "test-stable": 2,
    "nightly": 3,
    "test": 4,
    "old": 5,
    "smoketesting": 6,
}

_RUNTIME_DOC_CACHE = None
_SCHEMA_CACHE = None
_SCHEMA_FIELDS_CACHE = None

PACKAGE_ALIASES = {
    "libprocps-dev": "libproc2-dev",
}

SKIP_DEBIAN_BUILD_DEPENDS = {
    "linguist-qt6",
    "qt6-tools-dev",
    "qt6-tools-dev-tools",
    "qt6-l10n-tools",
}


def require_command(command_name, package_name, purpose):
    if shutil.which(command_name):
        return
    raise RuntimeError(
        f"`{command_name}` is required to {purpose}. "
        f"Install the `{package_name}` package first, then rerun this command."
    )


def ensure_managed_delete_path(path, workdir):
    resolved = Path(path).resolve()
    managed_root = Path(workdir).resolve()
    if resolved == managed_root or managed_root in resolved.parents:
        return
    raise RuntimeError(
        f"Refusing to delete `{resolved}` because it is outside the managed work directory `{managed_root}`. "
        "Deleting user data requires explicit confirmation."
    )


def run(cmd, cwd=None, check=True, capture_output=True):
    result = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=capture_output,
        check=False,
    )
    if check and result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        detail = stderr or stdout or f"exit code {result.returncode}"
        raise RuntimeError(f"command failed ({' '.join(cmd)}): {detail}")
    return result


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def version_key(value):
    parts = [int(part) for part in re.findall(r"\d+", value)]
    return tuple(parts)


def normalize_ref_version(ref):
    if not ref or "/" not in ref:
        return ref
    pkg_id, version = ref.split("/", 1)
    parts = re.findall(r"\d+", version)
    if len(parts) >= 3:
        return f"{pkg_id}/{'.'.join(parts[:3])}"
    return ref


def latest_remote_ref(ref):
    if not ref or "/" not in ref:
        return ref
    if not os.environ.get("LINYAPS_SKIP_REMOTE_SEARCH"):
        pass
    require_command("ll-cli", "linglong-bin", "query remote base/runtime versions")
    pkg_id, requested_version = ref.split("/", 1)
    try:
        result = run(
            ["ll-cli", "search", pkg_id, "--show-all-version"],
            check=True,
            capture_output=True,
        )
    except Exception:
        return ref

    candidates = []
    requested_parts = requested_version.split(".")
    requested_prefix = ".".join(requested_parts[:3])
    for raw_line in strip_ansi(result.stdout).splitlines():
        line = raw_line.strip()
        if not line.startswith(pkg_id):
            continue
        match = re.match(
            rf"^{re.escape(pkg_id)}\s+.+?\s+([0-9]+(?:\.[0-9]+)+)\s+(\S+)\s+(\S+)\s+(\S+)\s+",
            line,
        )
        if not match:
            continue
        version = match.group(1)
        repo = match.group(4)
        if not (version == requested_version or version.startswith(f"{requested_prefix}.")):
            continue
        candidates.append((REPO_PRIORITY.get(repo, 99), version_key(version), version))
    if not candidates:
        return ref
    candidates.sort(key=lambda item: (item[0], tuple(-value for value in item[1])))
    return normalize_ref_version(f"{pkg_id}/{candidates[0][2]}")


def is_url(value):
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"http", "https", "git", "ssh"}


def is_git_url(value):
    return value.endswith(".git") or "github.com/" in value or value.startswith("git@")


def download_file(url, destination):
    with urllib.request.urlopen(url) as response, open(destination, "wb") as handle:
        shutil.copyfileobj(response, handle)


def extract_archive(archive_path, destination):
    archive_path = Path(archive_path)
    if zipfile.is_zipfile(archive_path):
      with zipfile.ZipFile(archive_path) as zf:
          zf.extractall(destination)
      return

    if tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path) as tf:
            tf.extractall(destination)
        return

    raise RuntimeError(f"Unsupported archive format: {archive_path}")


def materialize_input(input_value, workdir):
    source_root = workdir / "source-tree"
    source_root.mkdir(parents=True, exist_ok=True)
    source_spec = {"kind": "local", "path": str(source_root), "name": source_root.name}
    local_copy = workdir / "input"

    if is_url(input_value):
        if is_git_url(input_value):
            run(["git", "clone", "--depth", "1", input_value, str(source_root)])
            try:
                commit = run(["git", "rev-parse", "HEAD"], cwd=source_root).stdout.strip()
            except Exception:
                commit = "HEAD"
            repo_name = Path(urllib.parse.urlparse(input_value).path).stem or source_root.name
            source_spec = {"kind": "git", "url": input_value, "commit": commit, "name": repo_name}
        else:
            local_copy.parent.mkdir(parents=True, exist_ok=True)
            filename = Path(urllib.parse.urlparse(input_value).path).name or "source-download"
            archive_path = local_copy.with_name(filename)
            download_file(input_value, archive_path)
            if archive_path.suffix.lower() in {".zip", ".gz", ".tgz", ".xz", ".bz2"} or tarfile.is_tarfile(archive_path) or zipfile.is_zipfile(archive_path):
                extract_archive(archive_path, source_root)
                source_spec = {"kind": "archive", "url": input_value, "name": archive_path.stem}
            else:
                shutil.copy2(archive_path, source_root / archive_path.name)
                source_spec = {"kind": "file", "url": input_value, "name": archive_path.name}
    else:
        input_path = Path(input_value).expanduser().resolve()
        if input_path.is_dir():
            shutil.copytree(
                input_path,
                source_root,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(
                    ".git",
                    "build",
                    "node_modules",
                    ".cache",
                    "linglong",
                ),
            )
            source_spec = {"kind": "local-dir", "path": str(input_path), "name": input_path.name}
        elif input_path.is_file():
            if zipfile.is_zipfile(input_path) or tarfile.is_tarfile(input_path):
                extract_archive(input_path, source_root)
                source_spec = {"kind": "archive", "path": str(input_path), "name": input_path.stem}
            else:
                raise RuntimeError(f"Unsupported local input file: {input_path}")
        else:
            raise RuntimeError(f"Input not found: {input_path}")

    normalized = collapse_single_top_level_dir(source_root)
    return normalized, source_spec


def collapse_single_top_level_dir(source_root):
    entries = [entry for entry in source_root.iterdir() if entry.name != ".git"]
    if len(entries) == 1 and entries[0].is_dir():
        nested = entries[0]
        temp_dir = source_root.parent / f"{source_root.name}-tmp"
        if temp_dir.exists():
            ensure_managed_delete_path(temp_dir, source_root.parent)
            shutil.rmtree(temp_dir)
        nested.rename(temp_dir)
        source_root.rmdir()
        temp_dir.rename(source_root)
    return source_root


def read_text(path, limit=8000):
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


def skill_root():
    return Path(__file__).resolve().parent.parent


def resolve_runtime_reference_doc():
    return skill_root() / "references" / "runtime.md"


def resolve_manifest_template():
    return skill_root() / "templates" / "simple.yaml"


def resolve_manifest_schema():
    return skill_root() / "resources" / "linglong-schemas.json"


def load_manifest_schema():
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE

    schema_path = resolve_manifest_schema()
    try:
        _SCHEMA_CACHE = json.loads(read_text(schema_path, limit=200000))
    except Exception as exc:
        raise RuntimeError(f"Failed to read manifest schema: {schema_path}") from exc
    return _SCHEMA_CACHE


def load_schema_allowed_fields():
    global _SCHEMA_FIELDS_CACHE
    if _SCHEMA_FIELDS_CACHE is not None:
        return _SCHEMA_FIELDS_CACHE

    schema = load_manifest_schema()
    _SCHEMA_FIELDS_CACHE = set(schema.get("properties", {}).keys())
    return _SCHEMA_FIELDS_CACHE


def indent_block(text, indent):
    prefix = " " * indent
    lines = text.splitlines() or [""]
    return "\n".join(f"{prefix}{line}" if line else prefix.rstrip() for line in lines)


def yaml_scalar(value):
    text = str(value)
    if not text:
        return '""'
    if re.fullmatch(r"[A-Za-z0-9._/+:-]+", text):
        return text
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def yaml_list_lines(values, indent):
    if not values:
        return " " * indent + "[]"
    prefix = " " * indent
    return "\n".join(f"{prefix}- {yaml_scalar(value)}" for value in values)


def yaml_description_block(text):
    lines = text.splitlines() or [""]
    return "\n".join(f"    {line}" if line else "    " for line in lines)


def yaml_build_script(text):
    lines = text.rstrip().splitlines() or [""]
    return "\n".join(f"  {line}" if line else "  " for line in lines)


def yaml_sources_block(source_spec):
    if source_spec["kind"] == "git":
        lines = [
            "- kind: git",
            f"  url: {yaml_scalar(source_spec['url'])}",
            f"  commit: {yaml_scalar(source_spec['commit'])}",
        ]
        if source_spec.get("name"):
            lines.append(f"  name: {yaml_scalar(source_spec['name'])}")
        return indent_block("\n".join(lines), 2)
    if source_spec["kind"] == "archive" and source_spec.get("url"):
        lines = [
            "- kind: archive",
            f"  url: {yaml_scalar(source_spec['url'])}",
        ]
        if source_spec.get("name"):
            lines.append(f"  name: {yaml_scalar(source_spec['name'])}")
        return indent_block("\n".join(lines), 2)
    if source_spec["kind"] == "file" and source_spec.get("url"):
        lines = [
            "- kind: file",
            f"  url: {yaml_scalar(source_spec['url'])}",
        ]
        if source_spec.get("name"):
            lines.append(f"  name: {yaml_scalar(source_spec['name'])}")
        return indent_block("\n".join(lines), 2)
    return "  []"


def prune_optional_sections(rendered):
    section_patterns = [
        r"\ncommand:\n  - __COMMAND__\n",
        r"\nruntime: __RUNTIME__\n",
        r"\nsources:\n  \[\]\n",
    ]
    for pattern in section_patterns:
        rendered = re.sub(pattern, "\n", rendered)
    return rendered


def validate_scalar_type(value, expected_type, path):
    type_map = {
        "string": str,
        "array": list,
        "object": dict,
        "boolean": bool,
        "integer": int,
        "number": (int, float),
    }
    python_type = type_map.get(expected_type)
    if python_type is None:
        return
    if expected_type == "integer" and isinstance(value, bool):
        raise RuntimeError(f"Manifest field `{path}` must be an integer")
    if expected_type == "number" and isinstance(value, bool):
        raise RuntimeError(f"Manifest field `{path}` must be a number")
    if not isinstance(value, python_type):
        raise RuntimeError(
            f"Manifest field `{path}` has invalid type: expected {expected_type}, got {type(value).__name__}"
        )


def validate_manifest_node(value, schema, path):
    expected_type = schema.get("type")
    if expected_type:
        validate_scalar_type(value, expected_type, path)

    if expected_type == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                raise RuntimeError(f"Manifest field `{path}.{key}` is required")
        extra_keys = sorted(set(value.keys()) - set(properties.keys()))
        if extra_keys:
            raise RuntimeError(
                f"Manifest field `{path}` contains unsupported keys: {', '.join(extra_keys)}"
            )
        for key, child in value.items():
            child_schema = properties.get(key)
            if child_schema is None:
                raise RuntimeError(f"Manifest field `{path}.{key}` is not defined in schema")
            validate_manifest_node(child, child_schema, f"{path}.{key}")
        return

    if expected_type == "array":
        item_schema = schema.get("items", {})
        for index, item in enumerate(value):
            validate_manifest_node(item, item_schema, f"{path}[{index}]")
        return

    if expected_type == "string" and "__" in value:
        raise RuntimeError(f"Manifest field `{path}` still contains an unreplaced template marker")


def validate_manifest_document(manifest_text):
    try:
        manifest_doc = yaml.safe_load(manifest_text)
    except yaml.YAMLError as exc:
        raise RuntimeError(f"Generated manifest is not valid YAML: {exc}") from exc
    if not isinstance(manifest_doc, dict):
        raise RuntimeError("Generated manifest must be a YAML object")
    validate_manifest_node(manifest_doc, load_manifest_schema(), "manifest")
    return manifest_doc


def parse_runtime_reference_packages():
    global _RUNTIME_DOC_CACHE
    if _RUNTIME_DOC_CACHE is not None:
        return _RUNTIME_DOC_CACHE

    doc_path = resolve_runtime_reference_doc()
    if not doc_path:
        _RUNTIME_DOC_CACHE = {}
        return _RUNTIME_DOC_CACHE

    text = read_text(doc_path, limit=500000)
    packages_by_ref = {}
    current_ref = None
    collecting = False
    code_lines = []

    for line in text.splitlines():
        heading = re.match(r"^###\s+(\S+)\s*$", line.strip())
        if heading:
            if current_ref and code_lines:
                packages_by_ref[current_ref] = set(" ".join(code_lines).split())
            current_ref = RUNTIME_ALIASES.get(heading.group(1), heading.group(1))
            collecting = False
            code_lines = []
            continue
        if not current_ref:
            continue
        if line.strip().startswith("```"):
            if collecting:
                if code_lines:
                    packages_by_ref[current_ref] = set(" ".join(code_lines).split())
                collecting = False
                code_lines = []
            else:
                collecting = True
            continue
        if collecting:
            code_lines.append(line.strip())

    if current_ref and code_lines and current_ref not in packages_by_ref:
        packages_by_ref[current_ref] = set(" ".join(code_lines).split())

    _RUNTIME_DOC_CACHE = packages_by_ref
    return _RUNTIME_DOC_CACHE


def packages_provided_by_refs(base, runtime):
    packages_by_ref = parse_runtime_reference_packages()
    provided = set()
    for ref in (base, runtime):
        if ref:
            normalized = RUNTIME_ALIASES.get(ref, ref)
            provided.update(packages_by_ref.get(normalized, set()))
    return provided


def relevant_project_files(source_root, name, skip_parts=None):
    skip_parts = set(skip_parts or [])
    results = []
    for path in sorted(source_root.rglob(name)):
        rel_parts = set(path.relative_to(source_root).parts)
        if rel_parts & skip_parts:
            continue
        results.append(path)
    return results


def find_existing_manifest_hint(source_root):
    candidates = []
    for path in source_root.rglob("linglong.yaml"):
        rel = path.relative_to(source_root)
        if rel.parts and rel.parts[0] == "linglong":
            continue
        candidates.append(path)
    if not candidates:
        return {}

    candidates.sort(key=lambda item: (len(item.relative_to(source_root).parts), str(item)))
    text = read_text(candidates[0], limit=40000)
    if not text:
        return {}

    hint = {"path": candidates[0].relative_to(source_root).as_posix()}
    package_block_match = re.search(r"(?ms)^package:\s*\n(.*?)(?:^\S|\Z)", text)
    package_block = package_block_match.group(1) if package_block_match else ""
    patterns = {
        "package_id": r"(?m)^\s*id:\s*['\"]?([^'\"]+?)['\"]?\s*$",
        "package_name": r"(?m)^\s*name:\s*['\"]?([^'\"]+?)['\"]?\s*$",
        "version": r"(?m)^\s*version:\s*['\"]?([^'\"]+?)['\"]?\s*$",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, package_block)
        if match:
            hint[key] = match.group(1).strip()

    command_match = re.search(r"(?ms)^\s*command:\s*\n\s*-\s*([^\n]+)", text)
    if command_match:
        hint["command"] = [command_match.group(1).strip().strip("'\"")]
    base_match = re.search(r"(?m)^base:\s*['\"]?([^'\"]+?)['\"]?\s*$", text)
    if base_match:
        hint["base"] = base_match.group(1).strip()
    runtime_match = re.search(r"(?m)^runtime:\s*['\"]?([^'\"]*?)['\"]?\s*$", text)
    if runtime_match:
        runtime_value = runtime_match.group(1).strip()
        hint["runtime"] = RUNTIME_ALIASES.get(runtime_value, runtime_value)
    else:
        runtime_block_match = re.search(r"(?ms)^runtime:\s*\n(.*?)(?:^\S|\Z)", text)
        runtime_block = runtime_block_match.group(1) if runtime_block_match else ""
        runtime_id_match = re.search(r"(?m)^\s*id:\s*['\"]?([^'\"]+?)['\"]?\s*$", runtime_block)
        if runtime_id_match:
            runtime_value = runtime_id_match.group(1).strip()
            hint["runtime"] = RUNTIME_ALIASES.get(runtime_value, runtime_value)
    return hint


def collect_doc_hints(source_root):
    hints = []
    allowed_suffixes = {".md", ".markdown", ".txt", ".rst", ".cmake", ".pro", ".toml", ".json", ".yaml", ".yml"}
    skip_parts = {".git", "3rdparty", "third_party", "vendor", "node_modules", "build"}
    for path in sorted(source_root.rglob("*")):
        if not path.is_file():
            continue
        if set(path.relative_to(source_root).parts) & skip_parts:
            continue
        upper = path.name.upper()
        if path.suffix.lower() not in allowed_suffixes and path.name not in SUPPORTED_FILES:
            continue
        if any(upper.startswith(prefix) for prefix in DOC_PATTERNS) or "docs" in path.parts or path.name in SUPPORTED_FILES:
            content = read_text(path)
            if content:
                hints.append((path.relative_to(source_root).as_posix(), content))
    def priority(item):
        path = item[0].lower()
        if path.startswith("readme"):
            return (0, path)
        if any(path.startswith(prefix.lower()) for prefix in DOC_PATTERNS):
            return (1, path)
        if path.startswith("docs/"):
            return (2, path)
        return (3, path)
    return sorted(hints, key=priority)[:20]


def read_debian_control(source_root):
    return read_text(source_root / "debian" / "control", limit=40000)


def parse_debian_control_field(control_text, field_name):
    lines = control_text.splitlines()
    collecting = False
    chunks = []
    field_prefix = f"{field_name}:"
    for line in lines:
        if not collecting:
            if line.startswith(field_prefix):
                collecting = True
                chunks.append(line[len(field_prefix):].strip())
            continue
        if not line.strip():
            break
        if line.startswith((" ", "\t")) or line.lstrip().startswith("#"):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            chunks.append(stripped)
            continue
        break
    return " ".join(part for part in chunks if part).strip()


def parse_debian_control_packages(raw_value):
    packages = []
    for part in raw_value.replace("\n", " ").split(","):
        item = part.strip()
        if not item or item.startswith("${"):
            continue
        alternatives = [candidate.strip() for candidate in item.split("|")]
        resolved = ""
        for candidate in alternatives:
            candidate = re.sub(r"\s*\(.*?\)", "", candidate).strip()
            candidate = PACKAGE_ALIASES.get(candidate, candidate)
            if not candidate:
                continue
            if package_exists(candidate):
                resolved = candidate
                break
            if not resolved:
                resolved = candidate
        item = resolved
        item = re.sub(r"\s*\(.*?\)", "", item).strip()
        if item and item not in packages:
            packages.append(item)
    return packages


def package_exists(package_name):
    if not package_name:
        return False
    try:
        result = run(["apt-cache", "show", package_name], check=False, capture_output=True)
    except Exception:
        return False
    return result.returncode == 0 and bool((result.stdout or "").strip())


def parse_debian_source_name(source_root):
    control_text = read_debian_control(source_root)
    match = re.search(r"(?m)^Source:\s*([^\s]+)\s*$", control_text)
    return match.group(1).strip() if match else ""


def parse_debian_changelog_version(source_root):
    changelog = read_text(source_root / "debian" / "changelog", limit=12000)
    match = re.search(r"(?m)^[^(]+\(([^)]+)\)", changelog)
    return match.group(1).strip() if match else ""


def find_demo_examples(build_system, framework):
    candidates = []
    cwd = Path.cwd().resolve()
    search_roots = [cwd, *cwd.parents]
    seen = set()
    for root in search_roots:
        demo_root = root / "demo"
        if not demo_root.is_dir():
            continue
        for path in sorted(demo_root.rglob("linglong.yaml")):
            project_dir = path.parent
            key = str(project_dir)
            if key in seen:
                continue
            seen.add(key)
            score = 0
            label = project_dir.relative_to(root).as_posix()
            lower_label = label.lower()
            if build_system and build_system in lower_label:
                score += 3
            if framework.get("qt_major") == 5 and "qt5" in lower_label:
                score += 2
            if framework.get("dtk_major") == 5 and "dtk5" in lower_label:
                score += 2
            if framework.get("uses_webengine") and "webengine" in lower_label:
                score += 2
            if "qml" in lower_label and "qml" in " ".join(framework.get("qmake_modules", [])):
                score += 1
            candidates.append((score, label))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [label for score, label in candidates[:3] if score > 0]


def detect_build_system(source_root):
    debian_rules = read_text(source_root / "debian" / "rules", limit=20000)
    if "--buildsystem=qmake" in debian_rules or "QMAKE=qmake6" in debian_rules or "QMAKE = qmake6" in debian_rules:
        return "qmake"
    if "--buildsystem=cmake" in debian_rules:
        return "cmake"
    if "--buildsystem=meson" in debian_rules:
        return "meson"
    if (source_root / "CMakeLists.txt").exists():
        return "cmake"
    if (source_root / "meson.build").exists():
        return "meson"
    if list(source_root.glob("*.pro")):
        return "qmake"
    if (source_root / "go.mod").exists():
        return "golang"
    if (source_root / "package.json").exists():
        return "npm"
    if (source_root / "pyproject.toml").exists() or (source_root / "setup.py").exists():
        return "python"
    if (source_root / "Makefile").exists():
        return "make"
    return "unknown"


def parse_package_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(read_text(path, limit=20000))
    except json.JSONDecodeError:
        return {}


def parse_pyproject(path):
    data = read_text(path, limit=20000)
    info = {}
    match = re.search(r"(?m)^name\s*=\s*[\"']([^\"']+)[\"']", data)
    if match:
        info["name"] = match.group(1)
    match = re.search(r"(?m)^version\s*=\s*[\"']([^\"']+)[\"']", data)
    if match:
        info["version"] = match.group(1)
    return info


def infer_name(source_root, source_spec, manifest_hint):
    if manifest_hint.get("package_name"):
        return manifest_hint["package_name"]
    debian_source = parse_debian_source_name(source_root)
    if debian_source:
        return debian_source
    package_json = parse_package_json(source_root / "package.json")
    if package_json.get("name"):
        return package_json["name"].split("/")[-1]

    pyproject = parse_pyproject(source_root / "pyproject.toml")
    if pyproject.get("name"):
        return pyproject["name"]

    go_mod = read_text(source_root / "go.mod")
    match = re.search(r"^module\s+(.+)$", go_mod, re.M)
    if match:
        return match.group(1).split("/")[-1]

    return source_spec.get("name", source_root.name)


def infer_version(source_root, source_spec):
    debian_version = parse_debian_changelog_version(source_root)
    if debian_version:
        return normalize_version(debian_version)

    package_json = parse_package_json(source_root / "package.json")
    if package_json.get("version"):
        return normalize_version(package_json["version"])

    pyproject = parse_pyproject(source_root / "pyproject.toml")
    if pyproject.get("version"):
        return normalize_version(pyproject["version"])

    meson = read_text(source_root / "meson.build")
    match = re.search(r"version\s*:\s*['\"]([^'\"]+)['\"]", meson)
    if match:
        return normalize_version(match.group(1))

    cmake = read_text(source_root / "CMakeLists.txt")
    match = re.search(r"project\([^)]+VERSION\s+([0-9][^) \n]+)", cmake, re.I)
    if match:
        return normalize_version(match.group(1))

    if source_spec.get("kind") == "git":
        raw = source_spec.get("commit", "HEAD")
        return normalize_version(raw[:8])

    return "1.0.0.0"


def normalize_version(value):
    parts = re.findall(r"[A-Za-z0-9]+", str(value))
    digits = []
    for part in parts:
        if part.isdigit():
            digits.append(part)
        elif re.fullmatch(r"[0-9a-fA-F]{7,40}", part):
            digits.append(str(int(part[:8], 16) % 100000))
    if not digits:
        return "1.0.0.0"
    while len(digits) < 4:
        digits.append("0")
    return ".".join(digits[:4])


def sanitize_token(value):
    token = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return token or "app"


def infer_package_id(source_root, source_spec, explicit_name):
    if explicit_name:
        return explicit_name

    manifest_hint = source_spec.get("manifest_hint", {})
    if manifest_hint.get("package_id"):
        return manifest_hint["package_id"]

    debian_source = parse_debian_source_name(source_root)
    if debian_source:
        if debian_source.startswith("deepin-"):
            return f"org.deepin.{debian_source.removeprefix('deepin-')}"
        if "." in debian_source:
            return debian_source

    if source_spec.get("kind") == "git":
        url = source_spec.get("url", "")
        match = re.search(r"github\.com[:/]+([^/]+)/([^/.]+)", url)
        if match:
            owner = sanitize_token(match.group(1)).replace("-", "_")
            repo = sanitize_token(match.group(2)).replace("-", "_")
            return f"io.github.{owner}.{repo}"

    stem = sanitize_token(infer_name(source_root, source_spec, manifest_hint)).replace("-", "_")
    return f"io.github.local.{stem}"


def infer_description(source_root, docs, source_spec, manifest_hint):
    for _, content in docs:
        for line in content.splitlines():
            line = line.strip().strip("#").strip()
            if len(line) > 20 and len(line) < 140:
                return line
    return f"Linglong package for {infer_name(source_root, source_spec, manifest_hint)}"


def parse_cmake_qt_components(cmake_text):
    components = {"Qt5": set(), "Qt6": set()}
    uncommented_lines = []
    for line in cmake_text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        uncommented_lines.append(line)
    cleaned = "\n".join(uncommented_lines)
    for match in re.finditer(r"find_package\((Qt[56])\s+REQUIRED\s+COMPONENTS\s+([^)]+)\)", cleaned, re.I | re.M):
        qt_name = match.group(1)
        raw = match.group(2)
        component_names = re.findall(r"[A-Za-z0-9_]+", raw)
        components.setdefault(qt_name, set()).update(component_names)
    return components


def parse_qmake_qt_modules(source_root):
    modules = set()
    qmake_text_parts = []
    for path in relevant_project_files(source_root, "*.pro", skip_parts={".git", "3rdparty", "third_party", "vendor", "node_modules", "tests", "test"}):
        text = read_text(path, limit=20000)
        if not text:
            continue
        qmake_text_parts.append(text)
        for match in re.finditer(r"(?m)^\s*QT\s*\+=\s*(.+)$", text):
            modules.update(token.lower() for token in re.findall(r"[A-Za-z0-9_]+", match.group(1)))
    return modules, "\n".join(qmake_text_parts)


def detect_framework(source_root, docs, build_system, manifest_hint):
    hint_text = "\n".join(content for _, content in docs[:5])
    debian_control = read_debian_control(source_root)
    cmake = "\n".join(
        read_text(path, limit=40000)
        for path in relevant_project_files(source_root, "CMakeLists.txt", skip_parts={".git", "3rdparty", "third_party", "vendor", "node_modules", "tests", "test"})
    )
    qmake_modules, qmake_text = parse_qmake_qt_modules(source_root)
    source_snippets = []
    for path in sorted(source_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".hh"}:
            continue
        source_snippets.append(read_text(path, limit=4000))
        if len(source_snippets) >= 8:
            break
    combined_source = "\n".join(source_snippets)
    combined = "\n".join([hint_text, cmake, qmake_text, combined_source])

    qt_major = None
    dtk_major = None
    uses_webengine = False

    if "qt6-base-dev" in debian_control or "qt6-base-dev-tools" in debian_control:
        qt_major = 6
    elif "qtbase5-dev" in debian_control or "qt5-qmake" in debian_control:
        qt_major = 5

    if "libdtk6gui-dev" in debian_control or "libdtk6widget-dev" in debian_control:
        dtk_major = 6
    elif "libdtkgui-dev" in debian_control or "libdtkwidget-dev" in debian_control:
        dtk_major = 5

    if qt_major is None and ("Qt6::" in combined or "find_package(Qt6" in combined):
        qt_major = 6
    elif qt_major is None and ("Qt5::" in combined or "find_package(Qt5" in combined):
        qt_major = 5
    elif qt_major is None and build_system == "qmake":
        qt_major = 5

    if re.search(r"(Qt6WebEngine|qtwebengine|webengine)", combined, re.I):
        uses_webengine = True
        qt_major = 6

    if dtk_major is None and ("find_package(Dtk6" in combined or re.search(r"DTK_VERSION_MAJOR\s+6", combined)):
        dtk_major = 6
    elif dtk_major is None and re.search(r"(DtkWidget|DtkGui|DtkCore|dtkwidget|dtkgui|dtkcore)", combined):
        dtk_major = 5
    elif dtk_major is None and manifest_hint.get("runtime") == "org.deepin.runtime.dtk/25.2.1":
        dtk_major = 6
    elif dtk_major is None and manifest_hint.get("runtime") == "org.deepin.runtime.dtk/23.1.0":
        dtk_major = 5

    if build_system == "qmake" and qt_major is None:
        qt_major = 5
    if qt_major is None and re.search(r"\bQT\s*\+=", qmake_text):
        qt_major = 5

    return {
        "qt_major": qt_major,
        "dtk_major": dtk_major,
        "uses_webengine": uses_webengine,
        "qmake_modules": sorted(qmake_modules),
    }


def select_base_runtime(framework, explicit_base, explicit_runtime, manifest_hint):
    if explicit_runtime:
        runtime = explicit_runtime
        base = explicit_base or RUNTIME_BASE_MAP.get(runtime, "org.deepin.base/25.2.1")
        return latest_remote_ref(base), latest_remote_ref(runtime)
    if explicit_base:
        return latest_remote_ref(explicit_base), latest_remote_ref(manifest_hint.get("runtime", ""))
    if framework["uses_webengine"] and framework["qt_major"] == 6:
        return latest_remote_ref("org.deepin.base/25.2.0"), latest_remote_ref("org.deepin.runtime.webengine/25.2.0")
    if framework["qt_major"] == 5 or framework["dtk_major"] == 5:
        return latest_remote_ref("org.deepin.base/23.1.0"), latest_remote_ref("org.deepin.runtime.dtk/23.1.0")
    if framework["qt_major"] == 6 or framework["dtk_major"] == 6:
        return latest_remote_ref("org.deepin.base/25.2.1"), latest_remote_ref("org.deepin.runtime.dtk/25.2.1")
    return latest_remote_ref(manifest_hint.get("base", "org.deepin.base/25.2.1")), latest_remote_ref(manifest_hint.get("runtime", ""))


def infer_depends(source_root, build_system, docs, framework, base, runtime):
    build_depends = []
    runtime_depends = []
    text_blob = "\n".join(content for _, content in docs[:10])
    debian_control = read_debian_control(source_root)

    def add_build(*items):
        for item in items:
            if item and item not in build_depends:
                build_depends.append(item)

    def add_runtime(*items):
        for item in items:
            if item and item not in runtime_depends:
                runtime_depends.append(item)

    if debian_control:
        for package_name in parse_debian_control_packages(parse_debian_control_field(debian_control, "Build-Depends")):
            if package_name in SKIP_DEBIAN_BUILD_DEPENDS:
                continue
            add_build(package_name)
        depends_field = parse_debian_control_field(debian_control, "Depends")
        for package_name in parse_debian_control_packages(depends_field):
            add_runtime(package_name)

    if build_system in {"cmake", "qmake", "make"}:
        add_build("build-essential")
    if build_system == "cmake":
        add_build("cmake")
    if build_system == "meson":
        add_build("meson", "ninja-build")
    if build_system == "qmake" and framework["qt_major"] != 6:
        add_build("qtbase5-dev")
        add_runtime("libqt5widgets5", "libqt5gui5", "libqt5core5a")
    if build_system == "golang":
        add_build("golang-go")
    if build_system == "npm":
        add_build("nodejs", "npm")
    if build_system == "python":
        add_build("python3", "python3-pip")
        add_runtime("python3")

    cmake = "\n".join(
        read_text(path, limit=20000)
        for path in relevant_project_files(source_root, "CMakeLists.txt", skip_parts={".git", "3rdparty", "third_party", "vendor", "node_modules", "tests", "test"})
    )
    qt_components = parse_cmake_qt_components(cmake)
    if framework["qt_major"] == 6 or "Qt6" in cmake:
        add_build("qt6-base-dev")
        runtime_depends = [dep for dep in runtime_depends if dep not in {"libqt5widgets5", "libqt5gui5", "libqt5core5a"}]
        add_runtime("libqt6core6", "libqt6gui6", "libqt6widgets6")
    elif framework["qt_major"] == 5 or "Qt5" in cmake or "find_package(Qt" in cmake:
        add_build("qtbase5-dev")
        add_runtime("libqt5widgets5", "libqt5gui5", "libqt5core5a")
    qt6_dev_map = {
        "Svg": "qt6-svg-dev",
    }
    qt5_dev_map = {
        "Svg": "libqt5svg5-dev",
    }
    for component in sorted(qt_components.get("Qt6", set())):
        package_name = qt6_dev_map.get(component)
        if package_name:
            add_build(package_name)
    for component in sorted(qt_components.get("Qt5", set())):
        package_name = qt5_dev_map.get(component)
        if package_name:
            add_build(package_name)
    if framework["uses_webengine"]:
        add_build("qt6-webengine-dev")
        add_runtime("libqt6webenginecore6", "libqt6webenginewidgets6")
    qmake_modules = set(framework.get("qmake_modules", []))
    qmake_text = "\n".join(
        read_text(path, limit=20000)
        for path in relevant_project_files(source_root, "*.pro", skip_parts={".git", "3rdparty", "third_party", "vendor", "node_modules", "tests", "test"})
    )
    if {"dtkwidget", "dtkgui", "dtkcore"} & qmake_modules:
        add_build("libdtkwidget-dev", "libdtkgui-dev")
    if "dwaylandclient" in qmake_modules:
        add_build("libkf5wayland-dev", "libkf5i18n-dev", "libepoxy-dev")
    if "svg" in qmake_modules and framework["qt_major"] == 5:
        add_build("libqt5svg5-dev")
    if "multimedia" in qmake_modules and framework["qt_major"] == 5:
        add_build("qtmultimedia5-dev")
    if "pkg_check_modules(GTK" in cmake or "gtk+-3.0" in text_blob:
        add_build("libgtk-3-dev")
        add_runtime("libgtk-3-0")
    if "SDL2" in cmake or "libsdl2" in text_blob:
        add_build("libsdl2-dev")
        add_runtime("libsdl2-2.0-0")

    provided_packages = packages_provided_by_refs(base, runtime)
    if provided_packages:
        build_depends = [item for item in build_depends if item not in provided_packages]
        runtime_depends = [item for item in runtime_depends if item not in provided_packages]

    return build_depends, runtime_depends


def infer_command(source_root, package_id, build_system, manifest_hint):
    if manifest_hint.get("command"):
        return manifest_hint["command"]
    for desktop_file in relevant_project_files(source_root, "*.desktop", skip_parts={".git", "3rdparty", "third_party", "vendor", "node_modules", "tests", "test"}):
        desktop_text = read_text(desktop_file, limit=8000)
        match = re.search(r"(?m)^Exec=([^\n]+)", desktop_text)
        if match:
            command = match.group(1).strip().split()[0]
            if command:
                return [command]
    cmake_text = "\n".join(
        read_text(path, limit=12000)
        for path in relevant_project_files(source_root, "CMakeLists.txt", skip_parts={".git", "3rdparty", "third_party", "vendor", "node_modules", "tests", "test"})
    )
    target_match = re.search(r"add_executable\(\s*([A-Za-z0-9_.+-]+)", cmake_text)
    if target_match:
        return [target_match.group(1)]
    qmake_text = "\n".join(
        read_text(path, limit=12000)
        for path in relevant_project_files(source_root, "*.pro", skip_parts={".git", "3rdparty", "third_party", "vendor", "node_modules", "tests", "test"})
    )
    target_match = re.search(r"(?m)^\s*TARGET\s*=\s*([A-Za-z0-9_.+-]+)\s*$", qmake_text)
    if target_match:
        return [target_match.group(1)]
    if build_system in {"golang", "make", "cmake", "meson", "qmake"}:
        binary = package_id.rsplit(".", 1)[-1]
        return [binary]
    return []


def build_script_for(build_system, source_root, framework):
    source_dir = "source-tree"
    if build_system == "cmake":
        return textwrap.dedent(f"""\
            cd {source_dir}
            cmake -B build -S . -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=$PREFIX
            cmake --build build -j$(nproc)
            DESTDIR=$DESTDIR cmake --install build
        """)
    if build_system == "meson":
        return textwrap.dedent(f"""\
            cd {source_dir}
            meson setup build --prefix=$PREFIX
            meson compile -C build
            DESTDIR=$DESTDIR meson install -C build
        """)
    if build_system == "qmake":
        pro_files = list(source_root.glob("*.pro"))
        pro_arg = pro_files[0].name if pro_files else ""
        qmake_bin = "qmake6" if framework.get("qt_major") == 6 else "qmake"
        return textwrap.dedent(f"""\
            cd {source_dir}
            {qmake_bin} {pro_arg} PREFIX=$PREFIX
            make -j$(nproc)
            make INSTALL_ROOT=$DESTDIR install
        """)
    if build_system == "golang":
        binary = sanitize_token(source_root.name)
        return textwrap.dedent(f"""\
            cd {source_dir}
            mkdir -p "$DESTDIR/$PREFIX/bin"
            go build -o "{binary}" .
            install -Dm755 "{binary}" "$DESTDIR/$PREFIX/bin/{binary}"
        """)
    if build_system == "npm":
        package_json = parse_package_json(source_root / "package.json")
        build_cmd = "npm run build" if "build" in package_json.get("scripts", {}) else "npm pack"
        dist_dir = "dist" if (source_root / "dist").exists() or "build" in package_json.get("scripts", {}) else "."
        return textwrap.dedent(f"""\
            cd {source_dir}
            npm install
            {build_cmd}
            mkdir -p "$DESTDIR/$PREFIX/share/{sanitize_token(source_root.name)}"
            cp -r {dist_dir}/* "$DESTDIR/$PREFIX/share/{sanitize_token(source_root.name)}/"
        """)
    if build_system == "python":
        return textwrap.dedent(f"""\
            cd {source_dir}
            python3 -m pip install . --prefix "$PREFIX" --root "$DESTDIR" --no-deps
        """)
    if build_system == "make":
        return textwrap.dedent(f"""\
            cd {source_dir}
            make PREFIX=$PREFIX -j$(nproc)
            make PREFIX=$PREFIX DESTDIR=$DESTDIR install
        """)
    return textwrap.dedent(f"""\
        cd {source_dir}
        # TODO: unsupported build system. Replace this section with project-specific steps.
        exit 1
    """)


def write_manifest(output_path, data):
    allowed_fields = load_schema_allowed_fields()
    required_fields = {"version", "package", "base", "build"}
    if allowed_fields and not required_fields.issubset(allowed_fields):
        raise RuntimeError("resources/linglong-schemas.json does not contain the expected linglong.yaml fields")

    template_text = read_text(resolve_manifest_template(), limit=40000)
    if not template_text:
        raise RuntimeError("templates/simple.yaml is missing or empty")

    replacements = {
        "__MANIFEST_VERSION__": "1",
        "__PACKAGE_ID__": yaml_scalar(data["package_id"]),
        "__PACKAGE_NAME__": yaml_scalar(data["package_name"]),
        "__PACKAGE_VERSION__": yaml_scalar(data["version"]),
        "__PACKAGE_DESCRIPTION__": yaml_description_block(data["description"]),
        "__COMMAND__": data["command"][0] if data["command"] else "__COMMAND__",
        "__BASE__": yaml_scalar(data["base"]),
        "__RUNTIME__": yaml_scalar(data["runtime"]) if data["runtime"] else "__RUNTIME__",
        "__SOURCES__": yaml_sources_block(data["source_spec"]),
        "__BUILD_DEPENDS__": yaml_list_lines(data["build_depends"], 6),
        "__RUNTIME_DEPENDS__": yaml_list_lines(data["runtime_depends"], 6),
        "__BUILD_SCRIPT__": yaml_build_script(data["build_script"]),
    }

    rendered = template_text
    for marker, value in replacements.items():
        rendered = rendered.replace(marker, value)
    rendered = prune_optional_sections(rendered)
    validate_manifest_document(rendered)
    output_path.write_text(rendered.rstrip() + "\n", encoding="utf-8")


def write_report(output_path, report):
    lines = [
        "# 推断报告",
        "",
        f"- 输入对象：`{report['input']}`",
        f"- 构建系统：`{report['build_system']}`",
        f"- 包 ID：`{report['package_id']}`",
        f"- 包版本：`{report['version']}`",
        f"- Base：`{report['base']}`",
    ]
    if report["runtime"]:
        lines.append(f"- Runtime：`{report['runtime']}`")
    if report["docs"]:
        lines.append("- 参考过的项目文档：")
        for path in report["docs"]:
            lines.append(f"  - `{path}`")
    if report["notes"]:
        lines.append("- 说明：")
        for note in report["notes"]:
            lines.append(f"  - {note}")
    if report["demo_examples"]:
        lines.append("- 相似示例:")
        for path in report["demo_examples"]:
            lines.append(f"  - `{path}`")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def select_export_ref(package_id, version, ll_builder_output):
    candidates = []
    for line in ll_builder_output.splitlines():
        if package_id not in line:
            continue
        tokens = re.findall(r"[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)+", line)
        for token in tokens:
            if package_id in token:
                candidates.append(token)
    if not candidates:
        return ""
    versionish = version.replace(".", "")
    for candidate in candidates:
        if version in candidate or versionish in candidate.replace(".", ""):
            return candidate
    return candidates[0]


def main():
    parser = argparse.ArgumentParser(description="Generate linglong.yaml from a project and optionally build/export it.")
    parser.add_argument("--input", required=True, help="Project directory, archive path, URL, or git URL")
    parser.add_argument("--workdir", required=True, help="Work directory for generated files")
    parser.add_argument("--package-id", help="Override inferred package id")
    parser.add_argument("--package-name", help="Override inferred package name")
    parser.add_argument("--version", help="Override inferred package version")
    parser.add_argument("--base", help="Linglong base ref")
    parser.add_argument("--runtime", help="Linglong runtime ref")
    parser.add_argument("--skip-build", action="store_true", help="Only generate files")
    parser.add_argument("--skip-export", action="store_true", help="Do not run ll-builder export")
    parser.add_argument("--enable-compat-check", action="store_true", default=True,
                       help="Enable compat check after build (default: True)")
    parser.add_argument("--no-compat-check", action="store_true",
                       help="Disable compat check after build")
    parser.add_argument("--compat-check-timeout", type=int, default=30,
                       help="Compat check timeout in seconds (default: 30)")
    parser.add_argument("--max-fix-attempts", type=int, default=3,
                       help="Maximum dependency fix attempts (default: 3)")
    args = parser.parse_args()

    workdir = Path(args.workdir).expanduser().resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    source_root, source_spec = materialize_input(args.input, workdir)
    manifest_hint = find_existing_manifest_hint(source_root)
    source_spec["manifest_hint"] = manifest_hint
    docs = collect_doc_hints(source_root)
    build_system = detect_build_system(source_root)
    package_name = args.package_name or infer_name(source_root, source_spec, manifest_hint)
    package_id = infer_package_id(source_root, source_spec, args.package_id)
    raw_version = args.version or manifest_hint.get("version") or infer_version(source_root, source_spec)
    version = normalize_version(raw_version)
    description = infer_description(source_root, docs, source_spec, manifest_hint)
    framework = detect_framework(source_root, docs, build_system, manifest_hint)
    demo_examples = find_demo_examples(build_system, framework)
    base, runtime = select_base_runtime(framework, args.base, args.runtime, manifest_hint)
    build_depends, runtime_depends = infer_depends(source_root, build_system, docs, framework, base, runtime)
    build_script = build_script_for(build_system, source_root, framework)
    command = infer_command(source_root, package_id, build_system, manifest_hint)

    notes = []
    if build_system == "unknown":
        notes.append("暂时无法可靠识别构建系统，请手动补全 build 段。")
    if not runtime_depends:
        notes.append("运行依赖采用了保守推断策略，请人工复核 buildext.apt.depends。")
    if source_spec["kind"] in {"local-dir", "archive"}:
        notes.append("本地输入已复制到 workdir/source-tree，生成的 manifest 不包含远程 sources。")
    if manifest_hint.get("path"):
        notes.append(f"已参考项目现有的 linglong.yaml：{manifest_hint['path']}")
        notes.append("项目中已经存在 linglong.yaml，生成结果会沿用当前源码目录布局，不再补写远程 sources。")
    notes.append(
        "框架识别结果："
        f"qt_major={framework['qt_major'] or 'unknown'}，"
        f"dtk_major={framework['dtk_major'] or 'unknown'}，"
        f"webengine={'yes' if framework['uses_webengine'] else 'no'}"
    )
    if len(base.split("/", 1)[-1].split(".")) >= 4:
        notes.append(f"Base 版本已根据远程仓库解析为最新可用版本：{base}")
    if runtime and len(runtime.split("/", 1)[-1].split(".")) >= 4:
        notes.append(f"Runtime 版本已根据远程仓库解析为最新可用版本：{runtime}")
    if demo_examples:
        notes.append("当前工作区中找到了相似示例，修改 manifest 前建议先对照这些样例。")

    manifest_data = {
        "package_id": package_id,
        "package_name": package_name,
        "version": version,
        "description": description,
        "base": base,
        "runtime": runtime,
        "command": command,
        "source_spec": source_spec,
        "build_depends": build_depends,
        "runtime_depends": runtime_depends,
        "build_script": build_script,
    }
    manifest_path = workdir / "linglong.yaml"
    if manifest_path.exists():
        raise SystemExit(f"Refusing to overwrite existing manifest: {manifest_path}")
    write_manifest(manifest_path, manifest_data)

    report_path = workdir / "inference-report.md"
    write_report(
        report_path,
        {
            "input": args.input,
            "build_system": build_system,
            "package_id": package_id,
            "version": version,
            "base": base,
            "runtime": runtime,
            "docs": [path for path, _ in docs],
            "notes": notes,
            "demo_examples": demo_examples,
        },
    )

    print(f"Generated: {manifest_path}")
    print(f"Report: {report_path}")

    if notes:
        print("\nNotes:")
        for note in notes:
            print(f"- {note}")

    if build_system == "unknown":
        raise SystemExit(2)

    if args.skip_build:
        return

    require_command("ll-builder", "linglong-builder", "build Linglong packages")

    # Determine compat check setting
    enable_compat_check = args.enable_compat_check and not args.no_compat_check

    # Use BuildFlowController if available for compat-check and auto-fix
    if BuildFlowController is not None and enable_compat_check:
        print("\n" + "=" * 60)
        print("Using BuildFlowController with compat-check and auto-fix")
        print("=" * 60)

        try:
            controller = BuildFlowController(
                build_dir=workdir,
                enable_compat_check=enable_compat_check,
                compat_check_timeout=args.compat_check_timeout,
                verbose=False
            )

            # Execute full build flow with compat check and auto-fix
            success, message = controller.build_with_compat_check_and_auto_fix()

            # Print final status
            print("\n" + "=" * 60)
            print("Final Build Status")
            print("=" * 60)
            print(f"Build Status: {controller.get_build_status()}")
            print(f"Compat Check Status: {controller.get_compat_check_status()}")
            if controller.get_fix_attempts() > 0:
                print(f"Fix Attempts: {controller.get_fix_attempts()}")
            print(f"Result: {message}")
            
            if not success:
                print(f"\n✗ Build flow failed: {message}")
                raise SystemExit(1)
                
        except Exception as e:
            print(f"\n✗ BuildFlowController error: {e}")
            # Fallback to simple build
            print("\nFalling back to simple build...")
            run(["ll-builder", "build"], cwd=workdir, check=True, capture_output=False)
    else:
        # Simple build without compact-check
        print("\n" + "=" * 60)
        print("Simple Build (compact-check disabled or not available)")
        print("=" * 60)
        run(["ll-builder", "build"], cwd=workdir, check=True, capture_output=False)
        
    if args.skip_export:
        return

    listed = run(["ll-builder", "list"], cwd=workdir).stdout
    export_ref = select_export_ref(package_id, version, listed)
    if not export_ref:
        print(listed)
        raise SystemExit("Unable to identify a unique ref from ll-builder list output")
    run(["ll-builder", "export", "--ref", export_ref], cwd=workdir, check=True, capture_output=False)


if __name__ == "__main__":
    main()

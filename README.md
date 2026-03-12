# linyaps-packager-skill

`linyaps-packager-skill` is the English name of `玲珑打包技能`. It is a self-contained skill package for generating and repairing `linglong.yaml`, building Linglong packages from source projects, and converting existing package formats into Linglong packages.

The repository is designed to be portable across AI agents that can read a skill directory and run local scripts. The core artifacts are the skill prompt, the helper scripts, the reference documents, the manifest template, and the schema file. No machine-specific path is required.

## What this skill does

This skill covers three major workflows:

1. Build a Linglong package from source input

- Accept a local project directory, source archive, download URL, Git repository URL, or GitHub repository URL
- Inspect project documentation, Debian packaging metadata, and build files
- Infer package metadata, build system, build dependencies, runtime dependencies, `base`, `runtime`, `command`, and `build` rules
- Generate `linglong.yaml`
- Optionally run `ll-builder build`, `ll-builder list`, and `ll-builder export`

2. Convert existing package files into Linglong packages

- Convert `deb` files through `ll-pica deb convert`
- Convert `AppImage` files through `ll-pica appimage convert`

3. Convert Flatpak applications into Linglong packages

- Convert a Flatpak app ID through `ll-pica flatpak convert`

## Repository layout

- `SKILL.md`
  The main skill instruction file. It explains when to use the skill, the execution rules, the base/runtime strategy, and the expected workflow.
- `scripts/build_from_project.py`
  The source-project entry point. It analyzes the project, generates `linglong.yaml`, writes an inference report, validates the manifest, and optionally runs the build/export flow.
- `scripts/convert_package.sh`
  The conversion entry point for `deb`, `AppImage`, and `Flatpak`.
- `references/project-build-workflow.md`
  Detailed guidance for source-based packaging.
- `references/pica-convert-workflow.md`
  Detailed guidance for package conversion.
- `references/runtime.md`
  Base/runtime reference, including built-in package lists used for dependency filtering.
- `templates/simple.yaml`
  The manifest template used to render `linglong.yaml`.
- `resources/linglong-schemas.json`
  The schema used to validate generated manifests.

## Prerequisites

To use this skill effectively, the host environment should provide:

- `python3`
- `ll-builder`, provided by the `linglong-builder` package
- `ll-cli`, provided by the `linglong-bin` package
- `linglong-pica`, which provides `ll-pica`, for conversion workflows

Depending on the target project, you may also need:

- `git`
- network access for source download or `ll-cli search`
- a working Linglong build environment for `ll-builder build`

## Source-project workflow

Run the source-project helper script like this:

```bash
python3 scripts/build_from_project.py \
  --input /path/to/project-or-archive-or-url \
  --workdir /tmp/linglong-build
```

Useful flags:

- `--skip-build`
  Only generate `linglong.yaml` and `inference-report.md`
- `--skip-export`
  Run `ll-builder build` but skip `ll-builder export`
- `--package-id`
  Override the inferred package ID
- `--package-name`
  Override the inferred package name
- `--version`
  Override the inferred package version
- `--base`
  Override the selected base
- `--runtime`
  Override the selected runtime

The script performs these steps:

1. Materialize the input into `<workdir>/source-tree`
2. Search project documentation and build metadata
3. Detect the build system
4. Infer package metadata, dependency lists, base/runtime, command, and build script
5. Render `linglong.yaml` from `templates/simple.yaml`
6. Validate the generated manifest against `resources/linglong-schemas.json`
7. Write `inference-report.md`
8. Optionally run `ll-builder build`
9. Optionally run `ll-builder list` and `ll-builder export`

## Build-system detection

The script currently supports these common build systems:

- CMake
- Meson
- qmake
- npm
- Python via `pyproject.toml` or `setup.py`
- Go
- Make

If the build system cannot be identified reliably, the script generates a TODO-style build section and exits with a non-zero status so the manifest can be completed manually.

## Base and runtime selection

The skill uses stable base/runtime combinations and can check remote availability through `ll-cli search`.

Current preferred combinations:

- Qt6 or DTK6: `org.deepin.base/25.2.1` + `org.deepin.runtime.dtk/25.2.1`
- Qt6 WebEngine: `org.deepin.base/25.2.0` + `org.deepin.runtime.webengine/25.2.0`
- Qt5 or DTK5: `org.deepin.base/23.1.0` + `org.deepin.runtime.dtk/23.1.0`

When the version family has been identified, the script tries to resolve the latest available remote version in that family. The generated manifest still uses the Linglong-style three-part version form.

## Dependency inference rules

The script separates dependencies into:

- `buildext.apt.build_depends`
  Build-time dependencies
- `buildext.apt.depends`
  Runtime dependencies

The filtering logic is conservative:

- Packages already provided by the selected base/runtime are removed from `buildext`
- The built-in package lists come from `references/runtime.md`
- Runtime dependencies are inferred conservatively and should always be reviewed

If the target project already contains `linglong.yaml`, the script keeps the local source-tree layout and does not add a remote `sources` section.

## Strict manifest validation

Generated manifests are validated immediately after rendering.

The validation currently checks:

- required fields defined by the schema
- unsupported fields outside the schema
- nested object and array structure
- field types
- unreplaced template placeholders
- YAML parsing errors

If validation fails, the script stops before any build step starts.

## Package-conversion workflow

Run the conversion helper like this:

```bash
bash scripts/convert_package.sh deb ./pkg.deb --workdir /tmp/pica-work --build
bash scripts/convert_package.sh appimage ./pkg.AppImage --id io.github.demo.app --version 1.0.0.0 --build
bash scripts/convert_package.sh flatpak org.kde.kate --build
```

The wrapper script maps the input type to the corresponding `ll-pica` command:

- `deb` -> `ll-pica deb convert`
- `appimage` -> `ll-pica appimage convert`
- `flatpak` -> `ll-pica flatpak convert`

If `ll-pica` is missing or does not support the requested subcommand, the script stops and tells the user to install or upgrade `linglong-pica`.

## Safety rules

This skill must not delete files or user data outside its managed work directory without explicit confirmation.

In practice, that means:

- temporary cleanup is allowed only inside the current managed work directory
- destructive operations targeting user directories must be blocked
- the workflow must stop and ask for confirmation before removing user-owned data

## Manifest template and schema

The repository intentionally keeps manifest generation constrained:

- `templates/simple.yaml` defines the base output structure and field order
- `resources/linglong-schemas.json` defines the allowed fields and their types

This keeps the generated manifest predictable and avoids adding unsupported or unnecessary fields.

## Typical examples

Generate a manifest only:

```bash
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/demo \
  --skip-build
```

Generate, build, and export:

```bash
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/demo
```

Convert a Debian package:

```bash
bash scripts/convert_package.sh deb ./demo.deb --workdir /tmp/pica-demo --build
```

Convert an AppImage:

```bash
bash scripts/convert_package.sh appimage ./demo.AppImage \
  --id io.github.demo.app \
  --version 1.0.0.0 \
  --build
```

Convert a Flatpak application:

```bash
bash scripts/convert_package.sh flatpak org.kde.kate --build
```

## Notes

- The generated manifest is a strong starting point, not an unconditional guarantee that the package will build correctly without review.
- Complex projects may still require manual adjustments to `build`, `command`, or dependency lists.
- The skill is portable because it depends on relative paths inside the skill directory rather than host-specific absolute paths.

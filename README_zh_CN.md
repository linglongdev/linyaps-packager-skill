# 玲珑打包技能

“玲珑打包技能” 的英文名是 `linyaps-packager-skill`。它是一套自包含的玲珑打包 skill，用于生成或修复 `linglong.yaml`、从源码项目构建玲珑包，以及把现成的软件包格式转换为玲珑包。

这个仓库的设计目标是尽量与宿主 AI 工具解耦。只要宿主能够读取 skill 目录并执行本地脚本，就可以复用这里的核心能力。仓库中不依赖任何机器专属路径，主要由技能说明、脚本、参考文档、模板和 schema 组成。

## 功能概览

这个 skill 主要覆盖三类任务：

1. 从源码生成玲珑包

- 支持本地项目目录、本地源码压缩包、下载地址、Git 仓库地址、GitHub 仓库地址
- 分析项目文档、Debian 打包元数据和构建文件
- 推断包信息、构建系统、构建依赖、运行依赖、`base`、`runtime`、`command` 和 `build`
- 生成 `linglong.yaml`
- 按需执行 `ll-builder build`、`ll-builder list` 和 `ll-builder export`

2. 将现成的软件包转换为玲珑包

- 通过 `ll-pica deb convert` 转换 `deb`
- 通过 `ll-pica appimage convert` 转换 `AppImage`

3. 将 Flatpak 应用转换为玲珑包

- 通过 `ll-pica flatpak convert` 转换 Flatpak 应用名
4. 自动兼容性测试和依赖修复

- 在构建后自动执行兼容性测试（Compatibility Check）
- 检测应用是否能正常启动
- 自动分析缺失的动态库依赖
- 自动下载并安装缺失的依赖包
- 为非标准目录中的库创建软链接
- 修复依赖后自动重建并再次验证
- 支持最多 3 次修复尝试
- 详细文档：[references/compatibility-check-workflow.md](references/compatibility-check-workflow.md)
## 目录结构

- `SKILL.md`
  技能主说明文件，定义使用场景、执行原则、base/runtime 选型和整体工作流。
- `scripts/build_from_project.py`
  源码项目打包入口。负责分析项目、生成 `linglong.yaml`、输出推断报告、执行 manifest 校验，并按需继续构建和导出。
- `scripts/convert_package.sh`
  `deb`、`AppImage`、`Flatpak` 的转换入口。
- `references/project-build-workflow.md`
  源码项目打包的详细说明。
- `references/pica-convert-workflow.md`
  包格式转换的详细说明。
- `references/runtime.md`
  base/runtime 参考文档，同时提供内置包列表，用于过滤 `buildext` 里的重复依赖。
- `templates/simple.yaml`
  生成 `linglong.yaml` 时使用的模板。
- `resources/linglong-schemas.json`
  生成后校验 manifest 的 schema。

## 依赖前提

要完整使用这份 skill，宿主环境通常需要具备以下命令：

- `python3`
- `ll-builder`，由 `linglong-builder` 包提供
- `ll-cli`，由 `linglong-bin` 包提供
- `linglong-pica` 提供的 `ll-pica`

根据目标项目的不同，可能还需要：

- `git`
- 可访问网络，用于下载源码或执行 `ll-cli search`
- 可用的玲珑构建环境，用于执行 `ll-builder build`

## 从源码生成玲珑包

基础用法如下：

```bash
python3 scripts/build_from_project.py \
  --input /path/to/project-or-archive-or-url \
  --workdir /tmp/linglong-build
```

常用参数：

- `--skip-build`
  只生成 `linglong.yaml` 和 `inference-report.md`，不执行构建
- `--skip-export`
  执行 `ll-builder build`，但跳过导出
- `--package-id`
  手动指定包 ID
- `--package-name`
  手动指定包名
- `--version`
  手动指定版本号
- `--base`
  手动指定 base
- `--runtime`
  手动指定 runtime

脚本会按以下顺序工作：

1. 将输入整理到 `<workdir>/source-tree`
2. 搜索项目文档和打包元数据
3. 识别项目使用的构建系统
4. 推断包信息、依赖、`base/runtime`、启动命令和构建脚本
5. 基于 `templates/simple.yaml` 渲染 `linglong.yaml`
6. 依据 `resources/linglong-schemas.json` 严格校验 manifest
7. 写出 `inference-report.md`
8. 如果没有指定 `--skip-build`，继续执行 `ll-builder build`
9. 如果没有指定 `--skip-export`，继续执行 `ll-builder list` 和 `ll-builder export`

## 当前支持的构建系统

目前脚本支持以下常见构建系统：

- CMake
- Meson
- qmake
- npm
- Python，包含 `pyproject.toml` 和 `setup.py`
- Go
- Make

如果无法可靠识别构建系统，脚本会生成带 TODO 的 `build` 段，并以非零状态退出，提示人工补全。

## base 和 runtime 选型

这份 skill 默认采用稳定的 base/runtime 组合，并且可以通过 `ll-cli search` 查询远程仓库中可用的最新版本。

当前优先组合如下：

- Qt6 或 DTK6：`org.deepin.base/25.2.1` + `org.deepin.runtime.dtk/25.2.1`
- Qt6 WebEngine：`org.deepin.base/25.2.0` + `org.deepin.runtime.webengine/25.2.0`
- Qt5 或 DTK5：`org.deepin.base/23.1.0` + `org.deepin.runtime.dtk/23.1.0`

在识别出版本系列后，脚本会尽量查询远程仓库中的最新可用版本，然后再按玲珑配置文件要求写成三段式版本。

## 依赖推断规则

脚本会把依赖分成两类：

- `buildext.apt.build_depends`
  构建阶段依赖
- `buildext.apt.depends`
  运行阶段依赖

依赖推断采用保守策略：

- 已经由所选 `base/runtime` 提供的包，不再写入 `buildext`
- 过滤依据来自 `references/runtime.md` 中记录的内置包列表
- 运行依赖只做保守推断，生成后仍然应人工复核

如果目标项目本身已经包含 `linglong.yaml`，脚本会沿用当前源码目录布局，不再为了新 manifest 补写远程 `sources`。

## 严格的 manifest/schema 校验

`linglong.yaml` 生成完成后，脚本会立即执行严格校验。

当前会检查以下内容：

- schema 中要求的必填字段是否齐全
- 是否出现 schema 未定义的字段
- 嵌套对象和数组的结构是否正确
- 字段类型是否匹配
- 模板占位符是否还有残留
- 生成结果是否是合法 YAML

只要校验失败，脚本会立刻停止，不会继续进入构建阶段。

## 包格式转换

转换入口如下：

```bash
bash scripts/convert_package.sh deb ./pkg.deb --workdir /tmp/pica-work --build
bash scripts/convert_package.sh appimage ./pkg.AppImage --id io.github.demo.app --version 1.0.0.0 --build
bash scripts/convert_package.sh flatpak org.kde.kate --build
```

脚本会根据输入类型自动映射到底层命令：

- `deb` -> `ll-pica deb convert`
- `appimage` -> `ll-pica appimage convert`
- `flatpak` -> `ll-pica flatpak convert`

如果系统中没有 `ll-pica`，或者当前 `ll-pica` 不支持对应子命令，脚本会直接停止，并提示用户安装或升级 `linglong-pica`。

## 安全规范

这份 skill 不应在未经确认的情况下删除工作目录之外的用户文件或用户数据。

具体要求如下：

- 临时清理操作只允许发生在当前受管工作目录内
- 涉及用户目录的数据删除操作必须被阻塞
- 如果确实需要删除用户数据，必须先停止流程并征求用户确认

## 模板与 schema 的作用

这个仓库有意把 manifest 生成约束在可控范围内：

- `templates/simple.yaml` 决定输出结构和字段顺序
- `resources/linglong-schemas.json` 决定字段集合和类型约束

这样可以让生成结果更稳定，也能避免脚本随意拼出不受支持或没有必要的字段。

## 常见用法示例

只生成 manifest：

```bash
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/demo \
  --skip-build
```

生成并继续构建、导出：

```bash
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/demo
```

转换 Debian 包：

```bash
bash scripts/convert_package.sh deb ./demo.deb --workdir /tmp/pica-demo --build
```

转换 AppImage：

```bash
bash scripts/convert_package.sh appimage ./demo.AppImage \
  --id io.github.demo.app \
  --version 1.0.0.0 \
  --build
```

转换 Flatpak：

```bash
bash scripts/convert_package.sh flatpak org.kde.kate --build
```

## 使用建议

- 自动生成的 manifest 可以显著减少手工整理工作，但不应当默认认为一定可以零修改通过构建。
- 对复杂项目，仍然可能需要人工调整 `build`、`command` 或依赖列表。
- 这份 skill 之所以便于迁移，是因为它只依赖 skill 目录内的相对路径，而不依赖宿主机器上的固定绝对路径。

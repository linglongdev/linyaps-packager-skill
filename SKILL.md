---
name: 玲珑打包技能
description: 用于生成或修复玲珑应用的 linglong.yaml，并完成源码项目、源码压缩包、URL、Git 仓库、deb、AppImage、Flatpak 的玲珑打包或转换。适合需要推断 build_depends、depends、base、runtime、build 规则，以及执行 ll-builder build/export 或 ll-pica 转换的场景。
references:
  - references/project-build-workflow.md
  - references/pica-convert-workflow.md
  - references/runtime.md
  - references/compat-check-workflow.md
---

# 玲珑打包技能

当需要生成或修复 `linglong.yaml`、推断构建依赖与运行依赖、选择合适的 `base/runtime`、执行 `ll-builder build/export`，或者把 `deb`、`AppImage`、`Flatpak` 转换为玲珑包时，使用这个 skill。

优先使用 skill 自带脚本处理可重复步骤。如果自动推断结果不够可靠，再结合参考文档和项目自身资料人工调整。关于玲珑规范、字段格式和构建约束，以本 skill 自带文档、模板和 schema 为准，不要凭记忆补字段。

## 目录约定

- 源码项目入口：`scripts/build_from_project.py`
- 包格式转换入口：`scripts/convert_package.sh`
- 源码项目打包说明：`references/project-build-workflow.md`
- `ll-pica` 转换说明：`references/pica-convert-workflow.md`
- base/runtime 包列表参考：`references/runtime.md`
- `linglong.yaml` 模板：`templates/simple.yaml`
- 字段结构参考：`resources/linglong-schemas.json`
- 兼容性测试模块：`scripts/compat_checker.py`
- 依赖分析模块：`scripts/dependency_analyzer.py`
- 依赖修复模块：`scripts/dependency_fixer.py`
- 构建流程控制器：`scripts/build_flow_controller.py`

## 使用前准备

- 处理源码项目时，优先参考项目自身提供的开发文档、构建说明、`debian/` 打包信息和构建配置文件。
- 如果当前工作区存在 `demo/` 示例目录，应优先查找与目标项目类型相近的样例，再决定 `linglong.yaml` 的写法。
- `ll-builder` 由 `linglong-builder` 包提供；如果系统中没有安装，应先安装 `linglong-builder`。
- `ll-cli` 由 `linglong-bin` 包提供；如果系统中没有安装，应先安装 `linglong-bin`。
- 处理 `deb`、`appimage`、`flatpak` 时，系统中需要已安装 `linglong-pica`，并能直接调用 `ll-pica`。
- 生成 `linglong.yaml` 时，应以 `templates/simple.yaml` 为基础，只替换模板中的内容，不额外拼接模板外的新字段。

## 兼容性测试（Compatibility Check）和依赖修复

本 skill 已集成 `linyaps-pica-helper` 的兼容性测试（compat-check）和依赖修复能力，能够：

1. **自动兼容性测试**：在构建后自动执行运行时测试，验证应用是否能正常启动
2. **依赖分析**：通过 `apt-file` 分析缺失的动态库依赖
3. **依赖修复**：自动下载并安装缺失的依赖包，或为非标准目录中的库创建软链接
4. **自动重建**：修复依赖后自动重新构建并再次验证

### 工作流程

```
构建 → 兼容性测试 → 检测失败？ → 否：完成
                    ↓ 是
              分析缺失依赖
                    ↓
              下载并安装依赖
                    ↓
              重建 → 兼容性测试 → 检测失败？ → 否：完成
                    ↓ 是
              尝试其他修复方法
                    ↓
              最多 3 次修复尝试
                    ↓
              最终构建（跳过测试）
```

### 使用参数

- `--enable-compat-check`：启用兼容性测试（默认启用）
- `--no-compat-check`：禁用兼容性测试
- `--compat-check-timeout <seconds>`：兼容性测试超时时间（默认 30 秒）
- `--max-fix-attempts <number>`：最大修复尝试次数（默认 3 次）

### 前置要求

使用兼容性测试和依赖修复功能需要：

1. **apt-file**：用于分析缺失依赖
   ```bash
   apt-get install apt-file
   apt-file update
   ```

2. **apt-get**：用于下载依赖包
   ```bash
   apt-get update
   ```

3. **zstd**：用于处理 files.tar.zst 归档（可选，不安装时会使用 Python 实现）

### 命令示例

启用紧凑检查和自动修复：

```bash
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/linglong-build \
  --enable-compat-check
```

禁用兼容性测试：

```bash
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/linglong-build \
  --no-compat-check
```

自定义兼容性测试超时时间：

```bash
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/linglong-build \
  --compat-check-timeout 60
```

### 输出文件

构建流程会生成以下文件：

- `missing_deps.csv`：缺失的依赖列表（由 ldd 检测）
- `missing-libs.packages`：匹配的包列表（由 apt-file 分析）
- `nonStrDir_found_libs.csv`：在非标准目录中找到的库
- `files.tar.zst`：应用文件的压缩归档（使用 zstd 压缩）
- `compat-check-errors/run-error.log`：兼容性测试错误日志

### 注意事项

- 兼容性测试使用 `ll-builder run` 命令，默认 30 秒超时
- 超时（退出码 124）被视为检查通过，因为应用已成功启动
- 依赖分析需要网络连接以查询 apt-file 缓存
- 依赖修复会修改 `linglong.yaml`，添加 `buildext.apt.depends` 段
- 如果超过最大修复次数仍未成功，会执行最终构建（跳过输出检查）
- 构建失败（退出码 255）通常表示依赖问题，会触发自动修复流程

## 快速上手

### 1. 从源码生成玲珑包

```bash
python3 scripts/build_from_project.py \
  --input /path/to/project-or-archive-or-url \
  --workdir /tmp/linglong-build
```

脚本会准备源码目录，生成 `linglong.yaml` 和 `inference-report.md`。默认还会继续执行：

```bash
ll-builder build
ll-builder list
ll-builder export --ref <selected-ref>
```

如果只需要生成配置文件，不希望立即构建或导出，可以使用：

- `--skip-build`
- `--skip-export`

### 2. 转换 deb、AppImage 或 Flatpak

```bash
bash scripts/convert_package.sh deb ./demo.deb --workdir /tmp/pica-work --build
bash scripts/convert_package.sh appimage ./demo.AppImage --id io.github.demo.app --version 1.0.0.0 --build
bash scripts/convert_package.sh flatpak org.kde.kate --build
```

## 执行原则

- 项目文档和打包元数据优先级高于启发式推断。
- `debian/control`、`debian/changelog`、`debian/rules` 可作为框架识别、版本提取、构建系统选择的重要依据。
- 如果存在相似的 `demo/` 示例，优先参考其 `base`、`runtime`、`build` 和 `command`。
- 生成 `linglong.yaml` 时，字段集合以 `resources/linglong-schemas.json` 为准，输出顺序以 `templates/simple.yaml` 为准。
- 生成完成后，应按 `resources/linglong-schemas.json` 对 manifest 做严格校验；如果出现 schema 外字段、缺少必填字段、类型不匹配或模板占位符未替换，应直接报错，不要继续构建。
- 自动生成的构建规则必须遵循 `PREFIX` 和 `DESTDIR`。
- 自动推断的运行依赖要尽量保守，不要写入明显不可用的包名。
- `buildext` 中只保留 base/runtime 没有提供的包；`references/runtime.md` 中已经记录在 base/runtime 里的包不要重复写入。
- skill 不应主动删除用户目录中的文件或数据；如果某个操作会删除工作目录之外的内容，必须立即阻塞并要求用户确认。
- 如果推断报告中仍存在不确定项，不要声称结果已经可以直接投入生产。

## base 和 runtime 选型

- Qt6 或 DTK6 项目：优先使用 `org.deepin.base/25.2.2` + `org.deepin.runtime.dtk/25.2.2`
- Qt6 WebEngine 项目：优先使用 `org.deepin.base/25.2.2` + `org.deepin.runtime.webengine/25.2.2`
- Qt5 或 DTK5 项目：优先使用 `org.deepin.base/23.1.0` + `org.deepin.runtime.dtk/23.1.0`
- 在确定版本系列后，优先通过 `ll-cli search ... --show-all-version` 查询远程仓库里的最新可用版本，再写入符合玲珑配置要求的三段式版本。
- 过滤 `buildext` 依赖时，以 `references/runtime.md` 中记录的 base/runtime 已内置包为准；已由 base/runtime 提供的包不再重复写入 `buildext`。

## 注意事项

- 本 skill 依赖宿主环境已安装 `ll-builder`、`ll-cli`，以及在转换场景下已安装 `linglong-pica`。
- `ll-builder` 来自 `linglong-builder`，`ll-cli` 来自 `linglong-bin`。
- 如果宿主工具支持从 skill 目录直接运行脚本，优先用本目录中的脚本入口；如果不支持，也可以直接手动执行上述命令。
- `agents/openai.yaml` 这类宿主专用元数据不是本 skill 的必需部分；真正可迁移的是 `SKILL.md`、`scripts/` 和 `references/`。

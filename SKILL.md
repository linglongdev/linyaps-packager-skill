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
- Deb 包转换器：`scripts/deb_converter.py`
- 源码项目打包说明：`references/project-build-workflow.md`
- `ll-pica` 转换说明：`references/pica-convert-workflow.md`
- base/runtime 包列表参考：`references/runtime.md`
- 兼容性测试工作流：`references/compatibility-check-workflow.md`
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
3. **依赖修复**：按顺序尝试3个修复模式，从最轻量到最重
4. **自动重建**：修复依赖后自动重新构建并再次验证

### 依赖修复的3个模式

当兼容性测试失败时，系统会按顺序尝试以下3个修复模式（从最轻量到最重）：

**构建策略**：
- **所有修复模式都使用 `--skip-output-check`**，避免 ldd 检查中断构建
- `--skip-output-check` 的实际作用：
  - **不会阻止 ldd 检查**：ldd 检查仍然会执行
  - **仍然会生成 missing_deps.csv**：可以收集缺失依赖信息用于后续分析
  - **只是不中断构建**：ldd 检查失败不会导致构建失败，但会作为警告显示
- **兼容性测试才是真正的验证**：`ll-builder run` 运行时测试才是更真实的验证方式
- 这样可以避免不必要的构建中断，保持一致性，同时仍然可以收集依赖信息

#### 模式2：软链接（最轻量）

扫描应用的 `files` 目录，在非标准目录中查找缺失的库，并创建软链接到 `files/lib` 目录。

- **优点**：最轻量，不增加包体积，提高运行库复用率
- **缺点**：只适用于应用自带的库，软链接可能不稳定
- **适用场景**：应用自带了缺失的库但不在标准位置

#### 模式0：运行时依赖（中等）

向 `linglong.yaml` 的 `depends` 字段追加缺失的依赖包名。这些依赖由运行时环境（runtime/base）提供，不会打包到应用中。

- **优点**：不增加包体积，依赖由运行时环境统一管理
- **缺点**：依赖运行时环境提供这些包
- **适用场景**：缺失的依赖是常见的系统库，运行时环境已包含

#### 模式1：构建时依赖（最重）

下载缺失的依赖包，解压到应用的 `files` 目录，并更新 `linglong.yaml` 的 `buildext.apt.depends` 字段。

- **优点**：确保依赖可用，不依赖运行时环境
- **缺点**：增加包体积，依赖更新需要重新打包
- **适用场景**：缺失的依赖不在运行时环境中，需要特定版本

**修复流程**：每次修复尝试只尝试一个模式，按顺序：模式2 → 模式0 → 模式1。每次修复后都会重建并重新测试，最多尝试3次（对应3个模式）。

**技术实现细节**：
- **第一次构建成功后**：自动备份原始的 `linglong.yaml` 到 `linglong.yaml.original`
- **每次修复前**：从备份的yaml提取信息，使用模板生成新的yaml
- **每次修复前**：从 `files.tar.zst` 解压 `files` 目录，确保使用最新的文件
- **build区域**：始终使用模板中的固定内容 `cp -rf /project/files/* $PREFIX/`，确保构建一致性
- **source区域**：始终使用模板中的固定内容 `kind: local, name: "${orig_yaml_name}"`，确保源码引用正确
- **yaml生成**：使用 skill 的 `templates/linglong-rebuild.yaml` 或 `templates/linglong-rebuild-WithoutRuntime.yaml` 模板
- **变量替换**：使用字符串替换方式（与 pica-helper 的 envsubst 效果相同），替换以下变量：
  - `${orig_yaml_version}`：包版本
  - `${orig_yaml_id}`：包 ID
  - `${orig_yaml_name}`：包名称
  - `${orig_yaml_description}`：包描述
  - `${orig_yaml_base}`：基础包
  - `${orig_yaml_runtime}`：运行时包（可选）
  - `${orig_yaml_command}`：启动命令
- **模板路径**：模板文件位于 skill 的 `templates/` 目录，确保生成的 yaml 使用模板中的固定 build 和 source 模块，而不是继承原始 yaml 的内容

### 工作流程

#### Deb 包转换完整流程

```
Phase 1: ll-pica convert
    ↓
Phase 2: 初始构建 (ll-builder build --skip-output-check)
    ↓
    备份原始 linglong.yaml 到 linglong.yaml.original
    ↓
Phase 3: 兼容性测试 (ll-builder run)
    ↓
检测失败？ → 否：Phase 7: 导出 Layer → 完成
    ↓ 是
Phase 4: 依赖修复尝试
    ↓
    从 files.tar.zst 解压 files 目录（确保使用最新文件）
    ↓
    从备份的 yaml 提取信息，使用模板生成新的 yaml
    ↓
第1次尝试：模式2（扫描非标准目录库，创建软链接）
    ↓ 失败
Phase 5: 重建 (ll-builder build --skip-output-check)
    ↓
Phase 6: 兼容性测试
    ↓ 失败
第2次尝试：模式0（追加运行时依赖 depends）
    ↓ 失败
Phase 5: 重建 (ll-builder build --skip-output-check)
    ↓
Phase 6: 兼容性测试
    ↓ 失败
第3次尝试：模式1（下载安装依赖 buildext.apt.depends）
    ↓ 失败
模式2: 扫描非标准目录库 (软链接)
    ↓
Phase 5: 重建 (ll-builder build --skip-output-check)
    ↓
Phase 6: 兼容性测试 (ll-builder run)
    ↓
检测失败？ → 否：Phase 7: 导出 Layer → 完成
    ↓ 是
修复次数 < 3？ → 是：返回 Phase 4
    ↓ 否
Phase 7: 最终构建 (ll-builder build --skip-output-check)
    ↓
Phase 8: 导出 Layer → 完成
```

**关键改进**：
- **Phase 2** 使用 `--skip-output-check` 参数，避免因非必要库或插件导致构建失败
- **Phase 3** 通过运行时测试验证应用是否能正常启动，这是更真实的验证方式
- 只有当兼容性测试失败时才触发依赖修复流程，而不是基于构建退出码
- **依赖修复按3个模式依次尝试**：模式2（最轻量）→ 模式0（中等）→ 模式1（最重）
- **所有修复模式都使用 `--skip-output-check`**，避免 ldd 检查中断构建
- `--skip-output-check` 的实际作用：
  - **不会阻止 ldd 检查**：ldd 检查仍然会执行
  - **仍然会生成 missing_deps.csv**：可以收集缺失依赖信息用于后续分析
  - **只是不中断构建**：ldd 检查失败不会导致构建失败，但会作为警告显示
- **兼容性测试才是真正的验证**：`ll-builder run` 运行时测试才是更真实的验证方式

#### 源码项目构建流程

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

- `--enable-compact-check`：启用兼容性测试（默认启用）
- `--no-compact-check`：禁用兼容性测试
- `--compact-check-timeout <seconds>`：兼容性测试超时时间（默认 30 秒）
- `--enable-layer-export`：启用 layer 导出（默认启用）
- `--no-layer-export`：禁用 layer 导出
- `--final-missing-csv <path>`：final-missing CSV 文件路径（用于包信息查找）
- `--ll-stored-pool <dir>`：layer 存储目录（默认：./StoredPool）
- `--missing-deps-strategy <strategy>`：兼容性测试通过但存在缺失依赖时的处理策略（默认：auto）
  - `auto`：只在兼容性测试失败时触发修复（保持向后兼容）
  - `ask`：询问用户是否触发修复
  - `force`：只要有缺失依赖就触发修复（无论兼容性测试结果）
  - `ignore`：忽略缺失依赖，只在兼容性测试失败时触发修复
- `--verbose`：显示详细输出
- `--quiet`：只显示最终结果（适合脚本自动化）

### 前置要求

#### 兼容性测试和依赖修复

使用兼容性测试和依赖修复功能需要：

1. **apt-file**：用于分析缺失依赖
   ```bash
   apt-get install apt-file
   # 更新缓存（需要 root 权限）
   sudo apt-file update
   ```
   **注意**：
   - apt-file 可以作为普通用户使用，基于现有数据库进行索引搜索
   - apt-file 缓存不需要实时更新，旧数据也可以用于索引
   - 如果缓存不存在或过旧，依赖分析会显示警告提示
   - 要更新 apt-file 缓存，需要 root 权限：`sudo apt-file update`

2. **apt-get**：用于下载依赖包
   ```bash
   apt-get update
   ```

3. **zstd**：用于处理 files.tar.zst 归档（可选，不安装时会使用 Python 实现）

#### Deb 包转换

使用 Deb 包转换功能需要：

1. **ll-pica**：用于 deb 包转换
   ```bash
   apt-get install linglong-pica
   ```

2. **ll-builder**：用于构建和测试
   ```bash
   apt-get install linglong-builder
   ```

3. **Python 3**：用于运行 deb_converter.py
   ```bash
   apt-get install python3 python3-pip
   ```

4. **PyYAML**：用于处理 linglong.yaml
   ```bash
   pip3 install pyyaml
   ```

### 命令示例

#### Deb 包转换

启用兼容性测试和 layer 导出：

```bash
bash scripts/convert_package.sh deb ./demo.deb \
  --workdir /tmp/pica-work \
  --enable-compact-check \
  --enable-layer-export
```

禁用兼容性测试：

```bash
bash scripts/convert_package.sh deb ./demo.deb \
  --workdir /tmp/pica-work \
  --no-compact-check
```

自定义兼容性测试超时时间：

```bash
bash scripts/convert_package.sh deb ./demo.deb \
  --workdir /tmp/pica-work \
  --compact-check-timeout 60
```

使用 final-missing CSV 文件更新包信息：

```bash
bash scripts/convert_package.sh deb ./demo.deb \
  --workdir /tmp/pica-work \
  --final-missing-csv /path/to/final-missing.csv \
  --ll-stored-pool /path/to/StoredPool
```

询问用户是否修复缺失依赖（适用于有可选 GUI 功能的程序）：

```bash
bash scripts/convert_package.sh deb ./demo.deb \
  --workdir /tmp/pica-work \
  --missing-deps-strategy ask
```

强制修复缺失依赖（即使兼容性测试通过）：

```bash
bash scripts/convert_package.sh deb ./demo.deb \
  --workdir /tmp/pica-work \
  --missing-deps-strategy force
```

忽略缺失依赖（只在兼容性测试失败时触发修复）：

```bash
bash scripts/convert_package.sh deb ./demo.deb \
  --workdir /tmp/pica-work \
  --missing-deps-strategy ignore
```

#### 源码项目构建

启用兼容性测试和自动修复：

```bash
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/linglong-build \
  --enable-compact-check
```

禁用兼容性测试：

```bash
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/linglong-build \
  --no-compact-check
```

自定义兼容性测试超时时间：

```bash
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/linglong-build \
  --compact-check-timeout 60
```

### 输出级别控制

Deb 包转换器支持三种输出级别：

- **normal（默认）**：显示简要的进度信息，包括 Phase 标题和关键结果
  - 适合一般使用和交互式操作
  - 提供足够的反馈，但不会过于冗长

- **quiet**：只显示最终结果（Final Status 和 Conversion Summary）
  - 适合脚本自动化和 CI/CD 环境
  - 减少输出噪音，便于日志分析

- **verbose**：显示所有详细信息，包括命令执行和详细错误
  - 适合问题排查和调试
  - 提供完整的执行过程信息

**使用示例**：

```bash
# Normal 模式（默认）
bash scripts/convert_package.sh deb ./demo.deb --workdir /tmp/pica-work

# Quiet 模式
bash scripts/convert_package.sh deb ./demo.deb --workdir /tmp/pica-work --quiet

# Verbose 模式
bash scripts/convert_package.sh deb ./demo.deb --workdir /tmp/pica-work --verbose
```

**输出对比**：

Normal 模式输出：
```
============================================================
Phase 2: Initial Build (skip output check)
============================================================

✓ Build successful

============================================================
Phase 3: Compat Check
============================================================

✓ Compat check passed: Application started successfully

============================================================
Final Status
============================================================
Build Status: passed
Compat Check Status: passed
Layer Export Status: passed
```



Verbose 模式输出：
```
============================================================
Phase 1: ll-pica convert
============================================================
Executing: ll-pica convert -c demo.deb -w /tmp/pica-work/pica-work
Working directory: /tmp/pica-work/pica-work
✓ ll-pica convert successful

============================================================
Phase 2: Initial Build (skip output check)
============================================================
Executing: ll-builder build --skip-output-check
Working directory: /tmp/pica-work/pica-work/package/demo
[详细的构建输出...]
✓ Build successful

============================================================
Phase 3: Compat Check
============================================================
Executing: ll-builder run
[详细的运行时测试输出...]
✓ Compat check passed: Application started successfully

============================================================
Final Status
============================================================
Build Status: passed
Compat Check Status: passed
Layer Export Status: passed
```

### 输出文件

#### Deb 包转换输出文件

构建流程会生成以下文件：

- `missing_deps.csv`：缺失的依赖列表（由 ldd 检测）
- `missing-libs.packages`：匹配的包列表（由 apt-file 分析）
- `nonStrDir_found_libs.csv`：在非标准目录中找到的库
- `files.tar.zst`：应用文件的压缩归档（使用 zstd 压缩）
- `linglong.yaml.original`：第一次构建成功后备份的原始yaml文件
- `compat-check-errors/run-error.log`：兼容性测试错误日志
- `*_binary.layer`：导出的 layer 文件（如果启用 layer 导出）

#### Layer 存储位置

- 如果兼容性测试通过：存储在 `--ll-stored-pool` 指定的目录（默认：./StoredPool）
- 如果兼容性测试未执行或失败：存储在 `--ll-stored-pool/forceTested` 目录

### 注意事项

#### 兼容性测试和依赖修复

- 兼容性测试使用 `ll-builder run` 命令，默认 30 秒超时
- 超时（退出码 124）被视为检查通过，因为应用已成功启动
- **apt-file 使用说明**：
  - apt-file 可以作为普通用户使用，基于现有数据库进行索引搜索
  - apt-file 缓存不需要实时更新，旧数据也可以用于索引
  - 如果缓存不存在或过旧（超过 7 天），会显示警告提示
  - 要更新 apt-file 缓存，需要 root 权限：`sudo apt-file update`
  - 依赖分析会自动检测缓存状态并给出相应提示
- 依赖修复会修改 `linglong.yaml`，添加 `buildext.apt.depends` 段
- 如果超过最大修复次数仍未成功，会执行最终构建（跳过输出检查）
- **第一次构建使用 `--skip-output-check`**，避免因非必要库或插件导致构建失败
- **只有兼容性测试失败时才触发依赖修复**，而不是基于构建退出码
- 修复后的重建使用标准构建，因为已经添加了必要的依赖
- **`--missing-deps-strategy` 参数的使用场景**：
  - 适用于有可选 GUI 功能的程序，CLI 可以正常启动，但 GUI 功能可能缺失依赖
  - `auto`（默认）：只在兼容性测试失败时触发修复，保持向后兼容
  - `ask`：在兼容性测试通过但有缺失依赖时询问用户，适合需要用户决策的场景
  - `force`：只要有缺失依赖就触发修复，适合需要确保所有功能可用的场景
  - `ignore`：忽略缺失依赖，只在兼容性测试失败时触发修复，适合只需要基本功能的场景
  - 在 `quiet` 模式下，`ask` 策略会自动降级为 `auto` 策略，避免交互

- **yaml备份机制**：
  - 第一次构建成功后，会自动备份原始的 `linglong.yaml` 到 `linglong.yaml.original`
  - 每次修复前，会从备份的yaml提取信息，使用模板生成新的yaml
  - 这确保了每次修复都使用干净的yaml模板，build区域始终是固定的 `cp -rf /project/files/* $PREFIX/`
  - 如果需要恢复原始yaml，可以从 `linglong.yaml.original` 复制

#### Deb 包转换

- Deb 包转换使用内置的 `deb_converter.py` 脚本，不直接调用 `ll-pica deb convert`
- 转换流程包含完整的兼容性测试和依赖修复功能
- 支持通过 `--final-missing-csv` 参数更新包的 ID 和名称
- Layer 文件会根据兼容性测试结果存储到不同目录
- AppImage 和 Flatpak 转换仍使用 `ll-pica` 的对应子命令

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

#### Deb 包转换

Deb 包转换使用内置的 `deb_converter.py` 脚本，提供完整的兼容性测试和依赖修复功能：

```bash
bash scripts/convert_package.sh deb ./demo.deb --workdir /tmp/pica-work
```

**Deb 转换选项**：
- `--workdir <dir>`：工作目录（默认：./pica-work）
- `--enable-compact-check`：启用兼容性测试（默认启用）
- `--no-compact-check`：禁用兼容性测试
- `--compact-check-timeout <s>`：兼容性测试超时时间（默认 30 秒）
- `--enable-layer-export`：启用 layer 导出（默认启用）
- `--no-layer-export`：禁用 layer 导出
- `--final-missing-csv <path>`：final-missing CSV 文件路径（用于包信息查找）
- `--ll-stored-pool <dir>`：layer 存储目录（默认：./StoredPool）
- `--verbose`：显示详细输出
- `--quiet`：只显示最终结果（适合脚本自动化）

**Deb 转换工作流程**：
1. **Phase 1**: 执行 `ll-pica convert` 转换 deb 包
2. **Phase 2**: 执行 `ll-builder build` 初始构建
   - 构建成功后备份原始 `linglong.yaml` 到 `linglong.yaml.original`
3. **Phase 3**: 执行 `ll-builder run` 兼容性测试
4. **Phase 4-6**: 如果测试失败，自动分析和修复依赖（最多 3 次尝试）
   - 每次修复前从 `files.tar.zst` 解压 `files` 目录
   - 每次修复前从备份的yaml生成新的yaml
   - 确保build区域始终是 `cp -rf /project/files/* $PREFIX/`
5. **Phase 7**: 导出 layer 文件到存储目录

#### AppImage 转换

```bash
bash scripts/convert_package.sh appimage ./demo.AppImage --id io.github.demo.app --version 1.0.0.0 --build
```

**AppImage 转换选项**：
- `--id <appid>`：应用 ID（必需）
- `--version <ver>`：版本（必需）
- `--name <name>`：应用名称
- `--description <text>`：描述
- `--workdir <dir>`：工作目录
- `--build`：转换后构建

#### Flatpak 转换

```bash
bash scripts/convert_package.sh flatpak org.kde.kate --build
```

**Flatpak 转换选项**：
- `--base <base>`：基础包
- `--base-version <ver>`：基础包版本
- `--version <ver>`：版本
- `--build`：转换后构建
- `--layer`：导出 layer

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

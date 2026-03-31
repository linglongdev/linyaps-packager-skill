# Linyaps Packager Skill 架构文档（增强版）

## 概述

`linyaps-packager-skill` 是一套自包含的玲珑打包技能，用于生成或修复 `linglong.yaml`、从源码项目构建玲珑包，以及将现成的软件包格式转换为玲珑包。增强版集成了 `linyaps-pica-helper` 的 compatibility-check（兼容性测试）和依赖修复能力，能够在构建失败或运行时检测失败时自动分析和修复依赖问题。

**版本**: 2.0 (增强版)

---

## 架构演进

### 原始架构

原始 skill 主要包含以下模块：

- `scripts/build_from_project.py`：源码项目打包入口
- `scripts/convert_package.sh`：包格式转换入口
- `references/`：参考文档
- `templates/`：模板文件
- `resources/`：资源文件（schema 等）

### 增强架构

基于 `linyaps-pica-helper` 的架构设计，新增以下模块：

- `scripts/compat_checker.py`：兼容性测试模块
- `scripts/dependency_analyzer.py`：依赖分析模块
- `scripts/dependency_fixer.py`：依赖修复模块
- `scripts/build_flow_controller.py`：构建流程控制器
- `references/compat-check-workflow.md`：兼容性测试工作流文档

---

## 核心架构

### 1. 模块划分

```
linyaps-packager-skill/
├── SKILL.md                          # 技能主说明文件
├── ARCHITECTURE.md                   # 架构文档（本文件）
├── scripts/
│   ├── build_from_project.py         # 主构建脚本（已增强）
│   ├── convert_package.sh            # 包格式转换脚本
│   ├── compat_checker.py            # 兼容性测试模块
│   ├── dependency_analyzer.py        # 依赖分析模块
│   ├── dependency_fixer.py           # 依赖修复模块
│   └── build_flow_controller.py      # 构建流程控制器
├── references/
│   ├── project-build-workflow.md     # 源码项目打包说明
│   ├── pica-convert-workflow.md      # pica 转换说明
│   ├── runtime.md                    # base/runtime 参考
│   └── compatibility-check-workflow.md  # 兼容性测试工作流
├── templates/
│   └── simple.yaml                   # linglong.yaml 模板
├── resources/
│   └── linglong-schemas.json         # schema 校验
└── tests/
    └── test_build_from_project.py    # 测试脚本
```

### 2. 模块依赖关系

```
build_from_project.py
    ↓ 依赖
build_flow_controller.py
    ↓ 聚合
├── compat_checker.py
├── dependency_analyzer.py
└── dependency_fixer.py
```

---

## 详细模块设计

### 1. CompatChecker（兼容性测试器）

**文件**: `scripts/compat_checker.py`

**职责**:
- 执行运行时测试（`ll-builder run`）
- 检测应用是否能正常启动
- 记录兼容性测试状态和错误日志

**类结构**:

```python
class CompatChecker:
    """兼容性测试器 - 执行运行时测试"""

    def __init__(self, build_dir: Path, enable_compat_check: bool, timeout: int)
    def check(self) -> Tuple[bool, str]
    def get_status(self) -> str
    def get_error_log_path(self) -> Optional[Path]
    def get_error_log_content(self) -> Optional[str]
```

**状态转换**:

```
N/A → checking → passed
             → failed
```

**核心逻辑**:

1. 检查是否启用兼容性测试
2. 使用 `timeout` 命令执行 `ll-builder run`
3. 根据退出码判断状态：
   - 124（超时）→ passed
   - 0 → passed
   - 其他 → failed

---

### 2. DependencyAnalyzer（依赖分析器）

**文件**: `scripts/dependency_analyzer.py`

**职责**:
- 分析缺失的动态库依赖
- 使用 `apt-file` 查找包含缺失库的包
- 匹配缺失库到对应的 Debian 包

**类结构**:

```python
class DependencyAnalyzer:
    """依赖分析器 - 分析缺失的依赖库"""
    
    def __init__(self, build_dir: Path, verbose: bool)
    def analyze_missing_deps(self, missing_deps_csv_path: Path, force_update_cache: bool) -> Tuple[bool, List[str]]
    def save_matched_packages(self, output_file: Path) -> bool
    def load_matched_packages(self, input_file: Path) -> List[str]
    def get_matched_packages(self) -> List[str]
    
    # 私有方法
    def _detect_elf_tag(self) -> str
    def _check_apt_file(self) -> bool
    def _update_apt_file_cache(self) -> bool
    def _search_package_for_library(self, library_name: str) -> List[str]
    def _parse_missing_deps_csv(self, csv_path: Path) -> List[str]
```

**数据流**:

```
missing_deps.csv
    ↓ (解析)
library_names
    ↓ (apt-file search)
packages (过滤 /usr/lib/<elf_tag>)
    ↓ (去重)
matched_packages
    ↓ (保存)
missing-libs.packages
```

**关键算法**:

1. **ELF 标签检测**：通过 `dpkg --print-architecture` 检测系统架构并映射到 ELF 标签
2. **库文件过滤**：只保留 `/usr/lib/<elf_tag>` 路径下的库
3. **并行查询**：使用 `xargs -P $(nproc)` 并行执行 `apt-file search`

---

### 3. DependencyFixer（依赖修复器）

**文件**: `scripts/dependency_fixer.py`

**职责**:
- 扫描非标准目录中的库
- 为库创建软链接到标准位置
- 下载并安装缺失的依赖包
- 合并依赖到应用文件目录
- 管理 `files.tar.zst` 归档

**类结构**:

```python
class DependencyFixer:
    """依赖修复器 - 修复缺失的依赖"""
    
    def __init__(self, build_dir: Path, verbose: bool)
    def scan_non_std_dir_libraries(self, app_installed_files_dir: Path) -> Tuple[bool, List[str]]
    def create_symlinks_for_libraries(self, libraries: List[str], source_dir: Path, target_lib_dir: Path) -> Tuple[bool, List[str]]
    def download_and_install_dependencies(self, packages: List[str], repo_deps_dir: Path) -> Tuple[bool, Path]
    def merge_dependencies_to_files(self, extracted_deps_dir: Path, target_files_dir: Path) -> Tuple[bool, List[str]]
    
    # 私有方法
    def _find_library_in_non_std_dir(self, files_dir: Path, library_name: str) -> List[Path]
    def _library_matches(self, pattern: str, filename: str) -> bool
    def _extract_files_tar(self, target_dir: Path) -> bool
    def create_files_tar(self, source_dir: Path) -> bool
    def _parse_missing_deps_csv(self, csv_path: Path) -> List[str]
```

**修复策略**:

1. **软链接策略**（优先）：
   - 在非标准目录中找到库
   - 在 `files/lib/` 中创建软链接
   - 适用于应用自带但位置不当的库

2. **下载依赖策略**（备选）：
   - 使用 `apt-file` 找到对应的包
   - 使用 `apt-get download` 下载 deb 包
   - 解压并合并到 `files/` 目录
   - 适用于系统库依赖

**归档管理**:

- 使用 `files.tar.zst` 存储应用文件
- 采用 zstd 压缩提高性能
- 支持解压和重建

---

### 4. BuildFlowController（构建流程控制器）

**文件**: `scripts/build_flow_controller.py`

**职责**:
- 协调整个构建、检查、修复流程
- 管理流程状态和尝试次数
- 协调各子模块的调用

**类结构**:

```python
class BuildFlowController:
    """构建流程控制器"""

    def __init__(self, build_dir: Path, enable_compat_check: bool, compat_check_timeout: int, verbose: bool)
    def build_with_compat_check_and_auto_fix(self, skip_output_check: bool) -> Tuple[bool, str]

    # 私有方法
    def _attempt_dependency_fix(self) -> Tuple[bool, str]
    def _attempt_final_build(self) -> Tuple[bool, str]
    def _execute_build(self, skip_output_check: bool) -> Tuple[bool, str]
    def _analyze_and_fix_dependencies(self) -> Tuple[bool, str]
    def _fix_non_std_dir_libraries(self) -> Tuple[bool, str]
    def _update_yaml_with_dependencies(self, packages: list) -> bool
    def _update_files_tar(self) -> bool

    # 状态查询
    def get_build_status(self) -> str
    def get_compat_check_status(self) -> str
    def get_fix_attempts(self) -> int
```

**状态机**:

```
Initial Build → Build_Passed → Compat_Check → Check_Passed → End
                                                → Check_Failed → Dependency_Fix → Rebuild → ...
```

**阶段划分**:

1. **Phase 1: Initial Build** - 初始构建
2. **Phase 2: Compatibility Check** - 兼容性测试
3. **Phase 3: Dependency Fix** - 依赖修复
4. **Phase 4: Rebuild After Fix** - 修复后重建
5. **Phase 5: Compatibility Check After Fix** - 修复后检查
6. **Phase 6: Final Build Without Test** - 最终构建

---

## 整合设计

### 1. build_from_project.py 增强

**新增参数**:

```python
--enable-compat-check       # 启用兼容性测试（默认）
--no-compat-check           # 禁用兼容性测试
--compat-check-timeout      # 超时时间（默认 30 秒）
--max-fix-attempts           # 最大修复次数（默认 3 次）
```

**流程变化**:

```python
# 原始流程
ll-builder build → ll-builder list → ll-builder export

# 增强流程
BuildFlowController.build_with_compat_check_and_auto_fix()
  ↓
ll-builder build → compat-check → (失败时) 依赖修复 → 重建
  ↓
ll-builder list → ll-builder export
```

**兼容性**:

- 保持向后兼容
- 默认启用 compat-check（兼容性测试）
- 可通过 `--no-compat-check` 禁用
- 缺少依赖时自动降级到简单构建

---

## 数据流架构

### 1. 构建数据流

```
source-tree/
    ↓ (分析)
linglong.yaml
    ↓ (构建)
ll-builder build
    ↓
linglong/output/binary/files/
    ↓ (归档)
files.tar.zst
    ↓ (检查)
ll-builder run (compat-check)
    ↓
    ├── 成功 → 导出
    └── 失败 → 依赖修复
```

### 2. 依赖分析数据流

```
missing_deps.csv
    ↓ (解析)
library_names
    ↓ (apt-file search)
package_results
    ↓ (过滤)
packages (in /usr/lib/<elf_tag>)
    ↓ (去重)
matched_packages
    ↓ (保存)
missing-libs.packages
```

### 3. 依赖修复数据流

```
missing-libs.packages
    ↓ (下载)
.deb files
    ↓ (解压)
extracted/usr/
    ↓ (合并)
files/
    ↓ (更新 yaml)
linglong.yaml (with buildext.apt.depends)
    ↓ (归档)
files.tar.zst
    ↓ (重建)
rebuild
```

### 4. 软链接修复数据流

```
missing_deps.csv
    ↓ (扫描)
non-std-dir libraries
    ↓ (创建软链接)
files/lib/ (symlinks)
    ↓ (归档)
files.tar.zst
    ↓ (重建)
rebuild
```

---

## 错误处理架构

### 1. 错误分类

| 错误类型 | 触发条件 | 处理策略 |
|---------|---------|---------|
| 构建错误（255） | 依赖缺失 | 触发依赖修复 |
| 构建错误（其他） | 其他问题 | 记录失败 |
| 紧凑检查失败 | 运行时错误 | 触发依赖修复 |
| 依赖分析失败 | apt-file 问题 | 尝试其他方法 |
| 下载失败 | 网络问题 | 跳过该包 |
| 超过最大修复次数 | 所有修复失败 | 最终构建（跳过测试） |

### 2. 错误恢复策略

```python
try:
    # 构建和兼容性测试
    success = build_with_compat_check()
except BuildError as e:
    if e.exit_code == 255:
        # 依赖问题，触发修复
        fix_dependencies()
        rebuild()
    else:
        # 其他错误，记录失败
        log_error(e)

try:
    # 依赖分析
    packages = analyze_dependencies()
except AnalysisError as e:
    # 尝试其他修复方法
    fix_method1()
    fix_method2()

if attempts >= max_attempts:
    # 超过最大次数，执行最终构建
    final_build_without_test()
```

---

## 性能优化架构

### 1. 并行处理

- **依赖分析**：使用 `xargs -P $(nproc)` 并行执行
- **apt-file 查询**：每个库独立进程
- **超时控制**：每个查询 30 秒超时

### 2. 归档优化

- **zstd 压缩**：高效压缩算法
- **避免重复解压**：复用 `files.tar.zst`
- **增量更新**：只更新变更的文件

### 3. 缓存策略

- **apt-file 缓存**：控制更新频率
- **匹配包列表**：全局变量缓存
- **构建结果**：files.tar.zst 缓存

---

## 扩展性架构

### 1. 插件化设计

```python
# 每个模块可独立使用
checker = CompatChecker(build_dir, True)
success = checker.check()

analyzer = DependencyAnalyzer(build_dir)
packages = analyzer.analyze_missing_deps()

fixer = DependencyFixer(build_dir)
fixer.download_and_install_dependencies(packages)

# 控制器协调所有模块
controller = BuildFlowController(build_dir)
controller.build_with_compact_check_and_auto_fix()
```

### 2. 自定义修复策略

```python
class CustomDependencyFixer(DependencyFixer):
    def custom_fix_method(self):
        # 自定义修复逻辑
        pass
```

### 3. 配置驱动

```python
# 命令行参数
parser.add_argument("--compact-check-timeout", type=int)
parser.add_argument("--max-fix-attempts", type=int)

# 环境变量
os.environ.get("LINYAPS_SKIP_REMOTE_SEARCH")
```

---

## 安全架构

### 1. 权限控制

- **禁止 root 检查**：防止权限问题
- **工作目录限制**：只允许在受管目录操作
- **文件权限保留**：保持原始权限

### 2. 路径安全

```python
def ensure_managed_path(path, workdir):
    resolved = Path(path).resolve()
    managed_root = Path(workdir).resolve()
    if resolved != managed_root and managed_root not in resolved.parents:
        raise RuntimeError("Path outside managed directory")
```

### 3. 数据验证

- **输入验证**：检查文件存在性
- **输出验证**：检查构建结果
- **完整性检查**：验证文件完整性

---

## 测试架构

### 1. 单元测试

```python
# tests/test_compact_checker.py
def test_compact_checker_success():
    checker = CompactChecker(test_dir, True)
    success, msg = checker.check()
    assert success is True

# tests/test_dependency_analyzer.py
def test_analyze_missing_deps():
    analyzer = DependencyAnalyzer(test_dir)
    success, packages = analyzer.analyze_missing_deps()
    assert success is True
    assert len(packages) > 0
```

### 2. 集成测试

```python
# tests/test_build_flow_controller.py
def test_build_flow_with_fix():
    controller = BuildFlowController(test_dir)
    success, msg = controller.build_with_compact_check_and_auto_fix()
    assert success is True
    assert controller.get_fix_attempts() > 0
```

---

## 文档架构

### 1. 用户文档

- `README_zh_CN.md`：用户指南
- `SKILL.md`：技能说明

### 2. 开发文档

- `ARCHITECTURE.md`：架构文档（本文件）
- `references/`：参考文档集

### 3. 工作流文档

- `references/compact-check-workflow.md`：compact-check 工作流
- `references/project-build-workflow.md`：项目构建工作流
- `references/pica-convert-workflow.md`：pica 转换工作流

---

## 部署架构

### 1. 依赖要求

```bash
# 必需工具
apt-get install linglong-builder linglong-bin

# compact-check 和依赖修复工具
apt-get install apt-file
apt-get install apt-get
apt-get install zstd  # 可选

# Python 依赖
pip install pyyaml
pip install zstandard  # 可选
```

### 2. 配置文件

```bash
# apt-file 缓存配置
/etc/apt-file.conf

# 玲珑配置
/etc/linglong-builder/config.yaml
```

### 3. 环境变量

```bash
export LINYAPS_SKIP_REMOTE_SEARCH=1
export PATH=/path/to/linyaps-bin:$PATH
```

---

## 监控和日志架构

### 1. 构建日志

```python
# 构建状态日志
build_status.csv
- deb_id
- linyaps_arch
- deb_version
- building_status
- compact_checking
- layer_export
```

### 2. 错误日志

```python
# 紧凑检查错误日志
compact-check-errors/run-error.log

# 构建错误日志
linglong/output/binary/build.log
```

### 3. 调试日志

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug(f"Building with compact check: {enable_compact_check}")
logger.info(f"Analyzing {len(packages)} packages")
logger.warning(f"Compact check failed: {error}")
logger.error(f"Build failed: {error}")
```

---

## 与 pica-helper 的对比

| 特性 | pica-helper | skill（增强版） |
|-----|-------------|----------------|
| 语言 | Bash | Python |
| 职责 | deb 转换 | 源码构建 + 转换 |
| compact-check | ✓ | ✓ |
| 依赖分析 | ✓ | ✓ |
| 依赖修复 | ✓ | ✓ |
| 软链接修复 | ✓ | ✓ |
| 下载依赖 | ✓ | ✓ |
| 重建流程 | ✓ | ✓ |
| 模块化 | 函数 | 类 |
| 并行处理 | ✓ | ✓ |
| 归档优化 | ✓ | ✓ |
| 可扩展性 | 中 | 高 |
| 文档 | 详细 | 详细 |

---

## 最佳实践

### 1. 开发环境

```bash
# 设置开发环境
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/linglong-build \
  --enable-compact-check \
  --compact-check-timeout 60
```

### 2. 生产环境

```bash
# 快速构建，跳过紧凑检查
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/linglong-build \
  --no-compact-check
```

### 3. 调试模式

```bash
# 增加超时时间，便于调试
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/linglong-build \
  --compact-check-timeout 120 \
  --max-fix-attempts 5
```

### 4. 持续集成

```bash
# CI/CD 环境中使用
python3 scripts/build_from_project.py \
  --input "$INPUT_PATH" \
  --workdir "$WORKDIR" \
  --enable-compact-check \
  --skip-export
```

---

## 未来规划

### 1. 短期目标

- [ ] 增加更多修复策略
- [ ] 支持更多包格式
- [ ] 优化并行处理性能
- [ ] 完善单元测试覆盖

### 2. 中期目标

- [ ] 支持 CI/CD 集成
- [ ] 提供可视化界面
- [ ] 支持分布式构建
- [ ] 增加智能依赖推荐

### 3. 长期目标

- [ ] 支持多平台交叉编译
- [ ] 机器学习驱动依赖推断
- [ ] 云端构建服务
- [ ] 社区包仓库

---

## 总结

### 核心特点

1. **模块化设计**：每个功能独立成类
2. **状态驱动**：清晰的状态转换
3. **错误恢复**：多层次错误处理
4. **性能优化**：并行处理和归档优化
5. **扩展性强**：插件化架构
6. **向后兼容**：保持原有功能不变

### 主要优势

- 基于 `linyaps-pica-helper` 的成熟架构
- Python 实现便于扩展和维护
- 完整的 compact-check 和依赖修复流程
- 详细的文档和参考实现
- 灵活的配置和参数控制

### 适用场景

- 源码项目玲珑打包
- 包格式转换（deb、AppImage、Flatpak）
- 自动化依赖修复
- CI/CD 集成
- 批量构建

---

## 附录

### A. 命令行参数完整列表

```bash
# 基础参数
--input              # 输入路径（必需）
--workdir            # 工作目录（必需）
--package-id         # 包 ID
--package-name       # 包名
--version            # 版本号
--base               # base 引用
--runtime            # runtime 引用

# 构建控制
--skip-build         # 跳过构建
--skip-export        # 跳过导出

# Compact-check 和依赖修复
--enable-compact-check    # 启用紧凑检查
--no-compact-check        # 禁用紧凑检查
--compact-check-timeout   # 紧凑检查超时时间（秒）
--max-fix-attempts        # 最大修复尝试次数
```

### B. 环境变量

```bash
LINYAPS_SKIP_REMOTE_SEARCH  # 跳过远程仓库查询
PATH                        # 可执行文件路径
```

### C. 输出文件清单

```
workdir/
├── linglong.yaml                    # manifest
├── inference-report.md              # 推断报告
├── source-tree/                     # 源码
├── linglong/
│   └── output/
│       └── binary/
│           └── files/               # 构建文件
├── files/
│   └── (应用文件)
├── files.tar.zst                    # 文件归档
├── missing_deps.csv                 # 缺失依赖
├── missing-libs.packages            # 匹配包
├── nonStrDir_found_libs.csv         # 非标准目录库
└── compact-check-errors/
    └── run-error.log                # 检查错误
```

### D. 依赖工具清单

| 工具 | 用途 | 必需 |
|------|------|-----|
| `ll-builder` | 构建玲珑包 | ✓ |
| `ll-cli` | 查询远程仓库 | ✓ |
| `apt-file` | 分析依赖 | ✓ |
| `apt-get` | 下载依赖 | ✓ |
| `dpkg` | 解压 deb 包 | ✓ |
| `zstd` | 压缩/解压 | - |
| `python3-yaml` | YAML 解析 | ✓ |
| `python3-zstandard` | 压缩支持 | - |

---

**文档版本**: 2.0
**最后更新**: 2026-03-24
**基于版本**: linyaps-pica-helper v1.13.6

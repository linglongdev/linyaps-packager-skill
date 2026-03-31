# Compat-Check 和依赖修复工作流

## 概述

本文档描述了 linyaps-packager-skill 中的 compat-check（兼容性测试）和依赖修复工作流程。该功能基于 `linyaps-pica-helper` 的架构设计，能够在构建失败或运行时检测失败时自动分析和修复依赖问题。

## 架构设计

### 模块划分

```
scripts/
├── build_from_project.py         # 主构建脚本（已增强）
├── compat_checker.py            # 兼容性测试模块
├── dependency_analyzer.py        # 依赖分析模块
├── dependency_fixer.py           # 依赖修复模块
└── build_flow_controller.py      # 构建流程控制器
```

### 模块职责

#### 1. CompatChecker（兼容性测试器）

**文件**: `scripts/compat_checker.py`

**职责**:
- 执行运行时测试（`ll-builder run`）
- 检测应用是否能正常启动
- 记录兼容性测试状态和错误日志

**核心方法**:
- `check()` - 执行兼容性测试，返回成功/失败状态
- `get_status()` - 获取兼容性测试状态
- `get_error_log_path()` - 获取错误日志路径
- `get_error_log_content()` - 获取错误日志内容

**状态定义**:
- `passed` - 测试通过（包括超时情况）
- `failed` - 测试失败
- `N/A` - 测试未执行或禁用

#### 2. DependencyAnalyzer（依赖分析器）

**文件**: `scripts/dependency_analyzer.py`

**职责**:
- 分析缺失的动态库依赖
- 使用 `apt-file` 查找包含缺失库的包
- 匹配缺失库到对应的 Debian 包

**核心方法**:
- `analyze_missing_deps()` - 分析缺失的依赖
- `_search_package_for_library()` - 搜索单个库对应的包
- `save_matched_packages()` - 保存匹配的包列表
- `load_matched_packages()` - 加载匹配的包列表

**输入文件**:
- `missing_deps.csv` - 由 ldd 检测的缺失依赖列表
  ```csv
  library_name,file_path
  libc.so.6,/usr/lib/x86_64-linux-gnu/libc.so.6
  libssl.so.1.1,/usr/lib/x86_64-linux-gnu/libssl.so.1.1
  ```

**输出文件**:
- `missing-libs.packages` - 匹配的包列表
  ```
  libssl1.1
  libc6
  ```

#### 3. DependencyFixer（依赖修复器）

**文件**: `scripts/dependency_fixer.py`

**职责**:
- 扫描非标准目录中的库
- 为库创建软链接到标准位置
- 下载并安装缺失的依赖包
- 合并依赖到应用文件目录
- 管理 `files.tar.zst` 归档

**核心方法**:
- `scan_non_std_dir_libraries()` - 扫描非标准目录中的库
- `create_symlinks_for_libraries()` - 为库创建软链接
- `download_and_install_dependencies()` - 下载并安装依赖包
- `merge_dependencies_to_files()` - 合并依赖到 files 目录
- `_extract_files_tar()` - 解压 files.tar.zst
- `create_files_tar()` - 创建 files.tar.zst

**修复策略**:

1. **软链接策略**（优先）
   - 在非标准目录中找到库
   - 在 `files/lib/` 中创建软链接
   - 适用于应用自带但位置不当的库

2. **下载依赖策略**（备选）
   - 使用 `apt-file` 找到对应的包
   - 使用 `apt-get download` 下载 deb 包
   - 解压并合并到 `files/` 目录
   - 适用于系统库依赖

#### 4. BuildFlowController（构建流程控制器）

**文件**: `scripts/build_flow_controller.py`

**职责**:
- 协调整个构建、检查、修复流程
- 管理流程状态和尝试次数
- 协调各子模块的调用

**核心方法**:
- `build_with_compat_check_and_auto_fix()` - 执行完整流程
- `_execute_build()` - 执行构建
- `_attempt_dependency_fix()` - 尝试依赖修复
- `_attempt_final_build()` - 执行最终构建

## 工作流程

### 完整流程图

```
════════════════════════════════════════════════════════════════
                     Phase 1: Initial Build
════════════════════════════════════════════════════════════════
                                ↓
                    ll-builder build
                                ↓
                ┌───────────────┴───────────────┐
                ↓                               ↓
           Success?                         Failure
                ↓                               ↓
                Yes                              No
                ↓                               ↓
═════════════════════════════════════════    Return Failed
            Phase 2: Compat Check
════════════════════════════════════════
                ↓
          ll-builder run (30s timeout)
                ↓
                ┌───────────┴───────────┐
                ↓                       ↓
            Success?                Failure
                ↓                       ↓
                Yes                      No
                ↓                       ↓
═════════════════════════════    Phase 3: Dependency Fix
           Return Passed════════════════════════════
                                ↓
     ┌──────────────────────────┴──────────────────┐
     ↓                                              ↓
Check missing_deps.csv?                      No missing deps
     ↓                                              ↓
     Yes                                   Scan non-std dir libs
     ↓                                              ↓
Analyze with apt-file                          Create symlinks
     ↓                                              ↓
Download dependencies                    Update files.tar.zst
     ↓                                              ↓
Extract to temporary dir                    Rebuild
     ↓
Merge to files/
     ↓
Update linglong.yaml
     ↓
Update files.tar.zst
     ↓
═════════════════════════════════════════════════════
        Phase 4: Rebuild After Fix
═════════════════════════════════════════════════════
                                ↓
                    ll-builder build
                                ↓
                ┌───────────────┴───────────────┐
                ↓                               ↓
           Success?                         Failure
                ↓                               ↓
                Yes                              No
                ↓                               ↓
═════════════════════════════════════════    Next Fix Attempt
    Phase 5: Compat Check After Fix
════════════════════════════════════════
                ↓
          ll-builder run (30s timeout)
                ↓
                ┌───────────┴───────────┐
                ↓                       ↓
            Success?                Failure
                ↓                       ↓
                Yes                      No
                ↓                       ↓
────────────────────────────    Increment fix attempt
      Return Passed───────────────────────────────────
                                ↓
                    fix_attempts <= 3?
                                ↓
              ┌─────────────────┴─────────────────┐
              ↓ Yes                              No ↓
              Try next fix method        Phase 6: Final Build
              ↓                              ↓
                                      ll-builder build
                                      --skip-output-check
                                             ↓
                                   ┌──────────┴──────────┐
                                   ↓                     ↓
                               Success?              Failure
                                   ↓                     ↓
────────────────────────────────────────────────────────────
      Return Passed                        Return Failed
────────────────────────────────────────────────────────────
```

### 状态机

#### 构建状态机

```
状态: Building
  ↓ ll-builder build 返回 0
状态: Build_Passed
  ↓ 启用 compat-check
状态: Checking
  ↓ ll-builder run 返回 0 或 124
状态: Check_Passed → End
  ↓ ll-builder run 返回其他
状态: Check_Failed
  ↓ 存在 missing_deps.csv
状态: Analyzing_Deps
  ↓ 找到匹配包
状态: Downloading_Deps
  ↓ 解压成功
状态: Merging_Deps
  ↓ 更新 linglong.yaml
状态: Rebuilding
  ↓ ll-builder build 返回 0
状态: Rebuild_Passed → Checking (循环)
  ↓ ll-builder run 返回其他
状态: Check_Failed_Again
  ↓ fix_attempts < 3
状态: Trying_Next_Fix_Method → Analyzing_Deps (循环)
  ↓ fix_attempts >= 3
状态: Final_Build
  ↓ ll-builder build --skip-output-check
状态: Final_Build_Passed / Final_Build_Failed → End
```

### 错误处理

#### 错误分类

1. **构建错误**
   - 退出码 255：依赖问题
   - 退出码 1：其他构建错误
   - 超时：构建时间过长

2. **紧凑检查错误**
   - 退出码 124：超时（视为成功）
   - 退出码非 0：运行时错误

3. **依赖分析错误**
   - `apt-file` 未安装
   - 网络连接失败
   - 找不到匹配的包

#### 错误恢复策略

1. **构建失败（退出码 255）**
   - 触发依赖分析
   - 尝试软链接修复
   - 尝试下载依赖
   - 重建并验证

2. **紧凑检查失败**
   - 检查缺失依赖
   - 修复依赖
   - 重建
   - 再次检查

3. **依赖分析失败**
   - 尝试其他修复方法
   - 跳过该修复步骤
   - 继续下一步

4. **超过最大修复次数**
   - 执行最终构建（跳过测试）
   - 不保证运行时正确性

## 数据流

### 构建数据流

```
source-tree/
    ↓
linglong.yaml (生成)
    ↓
ll-builder build
    ↓
linglong/output/binary/files/
    ↓
files.tar.zst (归档)
    ↓
ll-builder run (compat-check)
    ↓
成功 → 导出
失败 → 依赖修复
```

### 依赖分析数据流

```
missing_deps.csv (输入)
    ↓
library_name, file_path
    ↓
apt-file search library_name
    ↓
package-name: /path/to/library
    ↓
过滤 /usr/lib/<elf_tag>
    ↓
去重
    ↓
missing-libs.packages (输出)
```

### 依赖修复数据流

```
missing-libs.packages
    ↓
package list
    ↓
apt-get download
    ↓
.deb files
    ↓
dpkg -x
    ↓
extracted/usr/
    ↓
merge to files/
    ↓
update linglong.yaml
    ↓
files.tar.zst (更新)
    ↓
rebuild
```

### 软链接修复数据流

```
missing_deps.csv
    ↓
scan non-std dirs
    ↓
found libraries
    ↓
create symlinks in files/lib/
    ↓
files.tar.zst (更新)
    ↓
rebuild
```

## 配置参数

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--enable-compat-check` | 启用兼容性测试 | 默认启用 |
| `--no-compat-check` | 禁用兼容性测试 | - |
| `--compat-check-timeout` | 兼容性测试超时时间（秒） | 30 |
| `--max-fix-attempts` | 最大修复尝试次数 | 3 |

### 环境变量

| 变量 | 说明 |
|------|------|
| `LINYAPS_SKIP_REMOTE_SEARCH` | 跳过远程仓库查询 |

## 输出文件

### 构建输出

- `linglong.yaml` - 玲珑 manifest
- `inference-report.md` - 推断报告

### 兼容性测试输出

- `compat-check-errors/run-error.log` - 兼容性测试错误日志

### 依赖分析输出

- `missing_deps.csv` - 缺失依赖列表
- `missing-libs.packages` - 匹配的包列表
- `nonStrDir_found_libs.csv` - 非标准目录中的库

### 归档文件

- `files.tar.zst` - 应用文件归档（zstd 压缩）

## 性能优化

### 并行处理

- 依赖分析使用多进程（`xargs -P $(nproc)`）
- 每个 apt-file 查询独立进行
- 超时控制（30 秒）

### 归档优化

- 使用 `zstd` 压缩提高性能
- 避免重复解压
- 复用 `files.tar.zst`

### 缓存策略

- apt-file 缓存更新控制
- 匹配的包列表缓存
- 构建结果缓存

## 扩展性

### 插件化设计

- `CompatChecker` 可独立使用
- `DependencyAnalyzer` 可独立调用
- `DependencyFixer` 可独立使用
- `BuildFlowController` 协调所有模块

### 自定义修复策略

- 可扩展 `DependencyFixer` 添加新的修复方法
- 可自定义软链接目标目录
- 可自定义依赖包来源

## 注意事项

1. **权限要求**
   - 需要 root 权限运行 `apt-get download`（如果不是 root，需要在 docker 或其他容器中运行）

2. **网络要求**
   - 依赖分析需要访问 apt 源
   - 下载依赖需要网络连接

3. **磁盘空间**
   - 重建会占用额外的磁盘空间
   - 建议清理临时文件

4. **兼容性**
   - 需要安装 `apt-file` 并更新缓存
   - 需要 `zstd` 工具（可选）

5. **局限性**
   - 自动修复不能保证 100% 成功
   - 复杂依赖关系可能需要人工干预
   - 非 Debian 系需要适配

## 依赖工具

| 工具 | 用途 | 安装方法 |
|------|------|----------|
| `ll-builder` | 构建玲珑包 | `apt-get install linglong-builder` |
| `apt-file` | 分析依赖 | `apt-get install apt-file && apt-file update` |
| `apt-get` | 下载依赖 | 系统自带 |
| `dpkg` | 解压 deb 包 | 系统自带 |
| `zstd` | 压缩/解压 | `apt-get install zstd` |
| `python3-distutils` | Python 支持 | 系统自带 |
| `python3-yaml` | YAML 解析 | `apt-get install python3-yaml` |

## 最佳实践

1. **开发环境**
   - 在开发环境中先进行兼容性测试
   - 确保所有依赖都正确安装

2. **生产环境**
   - 使用 `--skip-compat-check` 加速构建
   - 通过其他方式验证应用功能

3. **调试模式**
   - 使用 `--compat-check-timeout` 增加超时时间
   - 查看 `compat-check-errors/run-error.log` 了解错误详情

4. **持续集成**
   - 将兼容性测试集成到 CI/CD
   - 失败时触发人工审查

## 故障排查

### 常见问题

1. **apt-file 未找到**
   ```
   错误: apt-file command not found
   解决: apt-get install apt-file && apt-file update
   ```

2. **zstd 未找到**
   ```
   错误: zstd command not found
   解决: apt-get install zstd
   ```

3. **依赖下载失败**
   ```
   错误: Failed to download package
   解决: 检查网络连接和 apt 源配置
   ```

4. **兼容性测试超时**
   ```
   提示: Compat check timed out
   说明: 这是正常的，超时被视为成功
   ```

5. **超过最大修复次数**
   ```
   错误: Exceeded maximum fix attempts
   解决: 人工检查缺失依赖并添加到 linglong.yaml
   ```

## 参考资料

- [linyaps-pica-helper 架构文档](../../linglong-pica-helper/ARCHITECTURE.md)
- [玲珑打包规范](https://linglong.deepin.org/docs/)
- [ll-builder 使用文档](https://linglong.deepin.org/docs/ll-builder/)

**文档版本**: 1.0
**最后更新**: 2026-03-24

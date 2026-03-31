# Compact-Check 和依赖修复使用示例

## 目录

1. [基础使用](#基础使用)
2. [完整工作流示例](#完整工作流示例)
3. [常见场景](#常见场景)
4. [故障排查](#故障排查)
5. [最佳实践](#最佳实践)

---

## 基础使用

### 1. 默认启用 Compact-Check

如果不指定任何参数，compat-check 默认启用：

```bash
cd linyaps-packager-skill
python3 scripts/build_from_project.py \
  --input /path/to/your/project \
  --workdir /tmp/linglong-test
```

这会执行：

1. 生成 `linglong.yaml`
2. 执行 `ll-builder build`
3. 执行 `ll-builder run`（compat-check，30秒超时）
4. 如果检查失败，自动分析和修复依赖
5. 重建并再次验证

### 2. 禁用 Compact-Check

如果不想执行紧凑检查，可以禁用：

```bash
python3 scripts/build_from_project.py \
  --input /path/to/your/project \
  --workdir /tmp/linglong-test \
  --no-compat-check
```

这会执行：

1. 生成 `linglong.yaml`
2. 执行 `ll-builder build`
3. 直接执行导出（不进行运行时验证）

### 3. 自定义超时时间

如果应用启动需要更长时间，可以增加超时时间：

```bash
python3 scripts/build_from_project.py \
  --input /path/to/your/project \
  --workdir /tmp/linglong-test \
  --compat-check-timeout 60
```

这会给应用 60 秒的启动时间。

### 4. 调整最大修复尝试次数

默认情况下，最多尝试 3 次修复。可以调整：

```bash
python3 scripts/build_from_project.py \
  --input /path/to/your/project \
  --workdir /tmp/linglong-test \
  --max-fix-attempts 5
```

---

## 完整工作流示例

### 示例 1: 简单的 C++ 项目

```bash
# 假设有一个简单的 C++ 项目
cd /path/to/simple-cpp-app
tree .
# .
# ├── CMakeLists.txt
# ├── src/
# │   └── main.cpp
# └── README.md

# 检查前置条件
apt-file update

# 执行构建
cd linyaps-packager-skill
python3 scripts/build_from_project.py \
  --input /path/to/simple-cpp-app \
  --workdir /tmp/simple-cpp-build \
  --enable-compat-check

# 输出示例
# Generated: /tmp/simple-cpp-build/linglong.yaml
# Report: /tmp/simple-cpp-build/inference-report.md
# 
# ============================================================
# Phase 1: Initial Build
# ============================================================
# ✓ Build successful
# 
# ============================================================
# Phase 2: Compat Check
# ============================================================
# ✓ Compact check passed (timeout as expected)
# 
# ============================================================
# Final Build Status
# ============================================================
# Build Status: passed
# Compat Check Status: passed
# Fix Attempts: 0
# Result: Build and compat check passed
```

### 示例 2: 有缺失依赖的 Python 项目

```bash
# 假设有一个依赖缺失库的 Python 项目
python3 scripts/build_from_project.py \
  --input /path/to/python-app \
  --workdir /tmp/python-build \
  --compat-check-timeout 45

# 输出示例
# Generated: /tmp/python-build/linglong.yaml
# Report: /tmp/python-build/inference-report.md
# 
# ============================================================
# Phase 1: Initial Build
# ============================================================
# ✓ Build successful
# 
# ============================================================
# Phase 2: Compat Check
# ============================================================
# ✗ Compact check failed
# 
# ============================================================
# Phase 3: Dependency Fix Attempt 1
# ============================================================
# 
# Analyzing missing dependencies...
# Found 2 missing packages
#   - libssl1.1
#   - libcrypto1.1
# 
# ✓ Analyzed 5 missing dependencies
# ✓ Merged 2 files
# ✓ Updated linglong.yaml with 2 dependencies
# ✓ Created files.tar.zst
# 
# ============================================================
# Phase 4: Rebuild After Fix
# ============================================================
# ✓ Build successful
# 
# ============================================================
# Phase 5: Compat Check After Fix
# ============================================================
# ✓ Compact check passed
# 
# ============================================================
# Final Build Status
# ============================================================
# Build Status: passed
# Compat Check Status: passed
# Fix Attempts: 1
# Result: Build and compat check passed after 1 fix attempt(s)
```

### 示例 3: 需要多次修复的复杂项目

```bash
# 复杂项目可能需要多次修复
python3 scripts/build_from_project.py \
  --input /path/to/complex-app \
  --workdir /tmp/complex-build \
  --max-fix-attempts 3 \
  --compat-check-timeout 30

# 可能会经历多次修复循环
# 
# ============================================================
# Phase 3: Dependency Fix Attempt 1
# ============================================================
# ...
# ✗ Compact check still failed
# 
# ============================================================
# Phase 3: Dependency Fix Attempt 2
# ============================================================
# Scanning for libraries in non-standard directories...
# Found 1 libraries in non-standard directories
# ✓ Created 1 symlinks
# ...
# ✗ Compact check still failed
# 
# ============================================================
# Phase 3: Dependency Fix Attempt 3
# ============================================================
# ...
# ✗ Compact check still failed
# 
# ============================================================
# Phase 6: Final Build Without Test
# ============================================================
# ✓ Final build successful
# 
# ============================================================
# Final Build Status
# ============================================================
# Build Status: passed
# Compat Check Status: failed
# Fix Attempts: 3
# Result: All fix attempts failed. Final build successful (compat check bypassed)
```

---

## 常见场景

### 场景 1: 应用自带库但位置不当

**问题描述**: 应用包含所需的库文件，但不在标准库路径中，导致 ldd 无法找到。

**解决方案**: compat-check 会自动在非标准目录中扫描这些库，并在 `files/lib/` 中创建软链接。

**示例**:

```bash
# 扫描非标准目录
python3 scripts/build_from_project.py \
  --input /path/to/app \
  --workdir /tmp/app-build \
  --enable-compat-check

# 输出
# Scanning for libraries in non-standard directories...
# Found 3 libraries in non-standard directories
#   ✓ Found libcustom.so.1 at: files/opt/app/lib/libcustom.so.1
#   ✓ Found libhelper.so.2 at: files/opt/app/lib/libhelper.so.2
#   ✓ Found libutil.so.3 at: files/opt/app/lib/libutil.so.3
# 
# ✓ Created 3 symlinks in /tmp/app-build/files/lib/
```

### 场景 2: 缺失系统库依赖

**问题描述**: 应用依赖系统库，但这些库没有包含在 base/runtime 中。

**解决方案**: compat-check 会使用 `apt-file` 分析缺失的库，并下载对应的 Debian 包。

**示例**:

```bash
# 分析缺失依赖
python3 scripts/build_from_project.py \
  --input /path/to/app \
  --workdir /tmp/app-build \
  --enable-compat-check

# 输出
# Analyzing missing dependencies...
# [1/5] Searching for: libssl.so.1.1
#   Found packages: libssl1.1
# [2/5] Searching for: libcrypto.so.1.1
#   Found packages: libcrypto1.1
# [3/5] Searching for: libz.so.1
#   Found packages: zlib1g
# [4/5] Searching for: libxml2.so.2
#   Found packages: libxml2
# [5/5] Searching for: libcurl.so.4
#   Found packages: libcurl4
# 
# ✓ Analysis complete
#   Found 5 packages:
#     - libssl1.1
#     - libcrypto1.1
#     - zlib1g
#     - libxml2
#     - libcurl4
# 
# Downloading 5 dependencies...
#   Downloading: libssl1.1
#   Downloading: libcrypto1.1
#   Downloading: zlib1g
#   Downloading: libxml2
#   Downloading: libcurl4
# ✓ Downloaded packages to /tmp/app-build/.repo_deps/debs
# 
# Extracting packages...
#   Extracting: libssl1.1_1.1.1f-1ubuntu2.20_amd64.deb
#   Extracting: libcrypto1.1_1.1.1f-1ubuntu2.20_amd64.deb
#   Extracting: zlib1g_1%3a1.2.11.dfsg-2ubuntu9.2_amd64.deb
#   Extracting: libxml2_2.9.13+dfsg-1ubuntu0.3_amd64.deb
#   Extracting: libcurl4_7.81.0-1ubuntu1.14_amd64.deb
# ✓ Extracted packages to /tmp/app-build/.repo_deps/extracted
# 
# Merging dependencies to /tmp/app-build/files/...
# ✓ Merged 1250 files
# 
# ✓ Updated linglong.yaml with 5 dependencies
```

### 场景 3: CI/CD 环境使用

**问题描述**: 在 CI/CD 环境中快速构建，不需要运行时验证。

**解决方案**: 禁用 compat-check 以加快构建速度。

**示例** (GitLab CI):

```yaml
# .gitlab-ci.yml
stages:
  - build

build-linglong:
  stage: build
  image: deepindebian/latest
  script:
    - apt-get update
    - apt-get install -y linglong-builder python3-yaml apt-file
    - apt-file update
    - cd /path/to/linyaps-packager-skill
    - python3 scripts/build_from_project.py \
        --input $CI_PROJECT_DIR \
        --workdir /tmp/linglong-ci-build \
        --no-compat-check \
        --skip-export
  artifacts:
    paths:
      - /tmp/linglong-ci-build/
    expire_in: 1 day
```

**示例** (GitHub Actions):

```yaml
# .github/workflows/build.yml
name: Build Linglong Package

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    container:
      image: deepindebian/latest
    steps:
      - uses: actions/checkout@v2
      - name: Install dependencies
        run: |
          apt-get update
          apt-get install -y linglong-builder python3-yaml apt-file
          apt-file update
      - name: Build Linglong package
        run: |
          cd /path/to/linyaps-packager-skill
          python3 scripts/build_from_project.py \
            --input $GITHUB_WORKSPACE \
            --workdir /tmp/linglong-gh-build \
            --no-compat-check \
            --skip-export
      - name: Upload artifacts
        uses: actions/upload-artifact@v2
        with:
          name: linglong-build
          path: /tmp/linglong-gh-build/
```

### 场景 4: 调试模式

**问题描述**: 构建失败，需要详细的调试信息。

**解决方案**: 增加超时时间，查看错误日志。

**示例**:

```bash
# 构建并检查错误日志
python3 scripts/build_from_project.py \
  --input /path/to/app \
  --workdir /tmp/debug-build \
  --compat-check-timeout 120 \
  --max-fix-attempts 5

# 如果检查失败，查看错误日志
cat /tmp/debug-build/compat-check-errors/run-error.log

# 查看 missing_deps.csv
cat /tmp/debug-build/missing_deps.csv

# 查看匹配的包
cat /tmp/debug-build/missing-libs.packages

# 查看 linglong.yaml 中的依赖
grep -A 5 "depends:" /tmp/debug-build/linglong.yaml
```

### 场景 5: 批量构建

**问题描述**: 需要批量构建多个项目。

**解决方案**: 使用脚本批量处理。

**示例**:

```bash
#!/bin/bash
# batch-build.sh

PROJECTS=(
  "/path/to/project1"
  "/path/to/project2"
  "/path/to/project3"
)

WORKDIR_BASE="/tmp/batch-build"

for project in "${PROJECTS[@]}"; do
  project_name=$(basename "$project")
  workdir="$WORKDIR_BASE/$project_name"
  
  echo "=========================================="
  echo "Building $project_name..."
  echo "=========================================="
  
  python3 scripts/build_from_project.py \
    --input "$project" \
    --workdir "$workdir" \
    --compat-check-timeout 45 \
    --max-fix-attempts 3 \
    --no-export
  
  if [ $? -eq 0 ]; then
    echo "✓ $project_name built successfully"
  else
    echo "✗ $project_name build failed"
  fi
  
  echo ""
done

echo "=========================================="
echo "Batch build complete"
echo "=========================================="
```

---

## 故障排查

### 问题 1: apt-file 命令未找到

**错误信息**:
```
✗ apt-file command not found
```

**解决方案**:
```bash
apt-get install apt-file
apt-file update
```

### 问题 2: 紧凑检查超时

**错误信息**:
```
✗ Compact check timed out (30 seconds)
```

**说明**: 这不是错误，超时意味着应用已经成功启动。

**解决方案**: 如果确认应用确实需要更长的启动时间，增加超时：
```bash
python3 scripts/build_from_project.py \
  --input /path/to/app \
  --workdir /tmp/long-start-build \
  --compat-check-timeout 120
```

### 问题 3: 找不到匹配的包

**错误信息**:
```
✗ No packages found in non-standard directories
✗ Found 0 missing packages
```

**解决方案**:
1. 手动检查 `missing_deps.csv` 的内容
2. 使用 `apt-file search` 手动搜索
3. 确认包名是否正确
4. 更新 apt-file 缓存：
   ```bash
   apt-file update
   ```

### 问题 4: 下载依赖失败

**错误信息**:
```
✗ Failed to download package-name
```

**解决方案**:
1. 检查网络连接
2. 更新 apt 源：
   ```bash
   apt-get update
   ```
3. 检查包名是否正确：
   ```bash
   apt-cache search package-name
   ```

### 问题 5: 超过最大修复次数

**错误信息**:
```
✗ Exceeded maximum fix attempts (3)
```

**解决方案**:
1. 增加最大修复次数：
   ```bash
   python3 scripts/build_from_project.py \
     --input /path/to/app \
     --workdir /tmp/build \
     --max-fix-attempts 5
   ```
2. 手动分析问题：
   ```bash
   # 查看错误日志
   cat /tmp/build/compat-check-errors/run-error.log
   
   # 查看缺失依赖
   cat /tmp/build/missing_deps.csv
   
   # 手动添加依赖到 linglong.yaml
   vim /tmp/build/linglong.yaml
   ```
3. 重新构建：
   ```bash
   cd /tmp/build
   ll-builder build
   ```

### 问题 6: files.tar.zst 解压失败

**错误信息**:
```
✗ Failed to extract files.tar.zst
```

**解决方案**:
1. 安装 zstd：
   ```bash
   apt-get install zstd
   ```
2. 或安装 Python zstandard 模块：
   ```bash
   pip install zstandard
   ```

### 问题 7: 构建失败（退出码 255）

**错误信息**:
```
✗ Build failed with exit code 255 (likely dependency issue)
```

**说明**: 退出码 255 通常表示依赖问题，会自动触发依赖修复流程。

**解决方案**: 这是正常流程，compat-check 会自动尝试修复。如果修复失败，查看错误日志并手动修复。

---

## 最佳实践

### 1. 开发环境

在开发环境中启用 compat-check，确保应用能正常运行：

```bash
python3 scripts/build_from_project.py \
  --input /path/to/app \
  --workdir /tmp/dev-build \
  --enable-compat-check \
  --compat-check-timeout 60
```

### 2. 生产环境

在生产环境中禁用 compat-check，加快构建速度：

```bash
python3 scripts/build_from_project.py \
  --input /path/to/app \
  --workdir /tmp/prod-build \
  --no-compat-check
```

### 3. 持续集成

在 CI/CD 中根据需要选择：

- **快速构建**: 禁用 compat-check
- **质量检查**: 启用 compat-check
- **夜间构建**: 启用 compat-check，增加超时时间

### 4. 批量构建

批量构建时：
- 使用 `--no-export` 跳过导出步骤
- 使用 `--compat-check-timeout` 增加超时时间
- 使用脚本循环处理多个项目

### 5. 调试问题

调试问题时：
- 增加超时时间
- 查看错误日志
- 检查缺失依赖
- 手动验证修复

### 6. 资源管理

- 清理临时文件：
  ```bash
  rm -rf /tmp/linglong-*
  ```
- 监控磁盘空间
- 使用 `--max-fix-attempts` 限制修复次数
- 定期清理 apt 缓存：
  ```bash
  apt-get clean
  apt-get autoclean
  ```

---

## 附录

### A. 输出文件说明

| 文件 | 说明 |
|------|------|
| `linglong.yaml` | 玲珑 manifest |
| `inference-report.md` | 推断报告 |
| `missing_deps.csv` | 缺失的依赖列表 |
| `missing-libs.packages` | 匹配的包列表 |
| `nonStrDir_found_libs.csv` | 非标准目录中的库 |
| `files.tar.zst` | 应用文件归档 |
| `compat-check-errors/run-error.log` | 紧凑检查错误日志 |

### B. 环境变量

```bash
# 跳过远程仓库查询
export LINYAPS_SKIP_REMOTE_SEARCH=1

# 设置 PATH
export PATH=/opt/linglong/bin:$PATH
```

### C. 相关文档

- [Compact-Check 工作流](../references/compat-check-workflow.md)
- [项目构建工作流](../references/project-build-workflow.md)
- [技能说明](../SKILL.md)
- [架构文档](../ARCHITECTURE.md)

---

**文档版本**: 1.0
**最后更新**: 2026-03-24

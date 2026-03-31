# 兼容性测试（Compatibility Check）使用示例

本文档提供了 linyaps-packager-skill 中兼容性测试和依赖修复功能的详细使用示例。

## 目录

- [基础使用](#基础使用)
- [完整工作流示例](#完整工作流示例)
- [常见场景处理](#常见场景处理)
- [CI/CD 集成](#cicd-集成)
- [调试模式](#调试模式)
- [批量构建](#批量构建)
- [故障排查](#故障排查)
- [最佳实践](#最佳实践)

---

## 基础使用

### 1. 默认启用兼容性测试

```bash
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/linglong-build
```

**说明**:
- 默认启用兼容性测试（`--enable-compact-check`）
- 默认超时时间为 30 秒
- 默认最多尝试 3 次修复
- 检测失败时会自动分析和修复依赖

### 2. 禁用兼容性测试

```bash
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/linglong-build \
  --no-compact-check
```

**说明**:
- 跳过兼容性测试，直接构建和导出
- 适用于生产环境加速构建
- 或者已经通过其他方式验证了应用功能

### 3. 自定义超时时间

```bash
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/linglong-build \
  --compact-check-timeout 60
```

**说明**:
- 将兼容性测试超时时间设置为 60 秒
- 适用于启动时间较长的应用
- 超时（退出码 124）仍被视为成功

### 4. 增加修复尝试次数

```bash
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/linglong-build \
  --max-fix-attempts 5
```

**说明**:
- 将最大修复尝试次数增加到 5 次
- 适用于依赖关系复杂的应用
- 注意：增加尝试次数会增加构建时间

### 5. 组合使用

```bash
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/linglong-build \
  --compact-check-timeout 60 \
  --max-fix-attempts 5
```

---

## 完整工作流示例

### 示例 1: 从源码构建（默认配置）

```bash
# 准备工作目录
mkdir -p /tmp/linglong-build
cd /tmp/linglong-build

# 从源码构建
python3 /path/to/linyaps-packager-skill/scripts/build_from_project.py \
  --input /path/to/my-app \
  --workdir /tmp/linglong-build

# 查看构建输出
ls -lh linglong/

# 安装并运行
ll-cli install io.github.myapp:$(cat linglong/refs/last-ref)
ll-cli run io.github.myapp
```

**输出文件**:
```
linglong/
├── refs/
│   └── last-ref
├── output/
│   └── binary/
│       ├── io.github.myapp_1.0.0.0_x86_64_main.uab
│       └── io.github.myapp_1.0.0.0_x86_64_debug.uab
├── linglong.yaml
├── inference-report.md
└── compact-check-errors/
    └── run-error.log (如果失败)
```

### 示例 2: 处理依赖缺失

```bash
# 场景：应用因为缺失依赖而无法启动

# 步骤 1：首次构建（可能会失败）
python3 scripts/build_from_project.py \
  --input /path/to/my-app \
  --workdir /tmp/linglong-build \
  --compact-check-timeout 30

# 步骤 2：如果失败，查看错误日志
cat /tmp/linglong-build/compact-check-errors/run-error.log

# 步骤 3：查看缺失的依赖
cat /tmp/linglong-build/missing_deps.csv

# 步骤 4：查看匹配的包
cat /tmp/linglong-build/missing-libs.packages

# 步骤 5：自动化修复会尝试：
#   - 下载 apt-file 找到的包
#   - 创建非标准目录库的软链接
#   - 重建并重新检查

# 重建后的构建
# 如果修复成功，可以继续导出
ll-builder list
ll-builder export --ref io.github.myapp:1.0.0.0
```

**自动化修复流程**:
```
1. 检测到启动失败
   ↓
2. 读取 missing_deps.csv
   ↓
3. 使用 apt-file 查找包
   ↓
4. 下载并提取依赖包
   ↓
5. 合并到 files/ 目录
   ↓
6. 创建软链接
   ↓
7. 更新 linglong.yaml
   ↓
8. 重建
   ↓
9. 再次兼容性测试
```

### 示例 3: 多轮修复

```bash
# 场景：依赖关系复杂，需要多轮修复

python3 scripts/build_from_project.py \
  --input /path/to/complex-app \
  --workdir /tmp/linglong-build \
  --max-fix-attempts 5 \
  --compact-check-timeout 30 2>&1 | tee build.log

# 构建日志会显示每一轮的修复尝试
# 例如：
# Round 1: Fixed libssl1.1 → Rebuild → Failed
# Round 2: Fixed libcurl4 → Rebuild → Failed
# Round 3: Fixed libpng16-16 → Rebuild → Passed

# 查看最终结果
cat build.log | grep "Compatibility check"
```

---

## 常见场景处理

### 场景 1: Qt 应用缺库

```bash
# 问题：Qt 应用缺少 Qt 库

python3 scripts/build_from_project.py \
  --input /path/to/qt-app \
  --workdir /tmp/linglong-build \
  --compact-check-timeout 30

# 自动化修复会：
# 1. 检测缺失 Qt 库
# 2. 使用 apt-file 找到相关的 Qt 包
# 3. 下载并安装 Qt 运行时库
# 4. 为 Qt plugin 创建软链接
# 5. 重建并验证
```

**典型缺失库**:
- `libQt5Core.so.5`
- `libQt5Gui.so.5`
- `libQt5Widgets.so.5`

**自动匹配的包**:
- `libqt5core5a`
- `libqt5gui5`
- `libqt5widgets5`

### 场景 2: Python 应用缺库

```bash
# 问题：Python 应用缺少第三方库

python3 scripts/build_from_project.py \
  --input /path/to/python-app \
  --workdir /tmp/linglong-build \
  --compact-check-timeout 30

# 注意：Python 库通常需要通过 pip 安装
# 自动化修复可能无法处理纯 Python 库
# 建议手动在构建规则中添加 pip install
```

**手动修复**:
```yaml
# 在 linglong.yaml 中添加
build:
  kind: qmake
  manual:
    install: |
      pip3 install -r requirements.txt
```

### 场景 3: 非标准目录库

```bash
# 问题：应用自带库，但放在非标准目录

python3 scripts/build_from_project.py \
  --input /path/to/app-with-libs \
  --workdir /tmp/linglong-build \
  --compact-check-timeout 30

# 自动化修复会：
# 1. 扫描非标准目录中的库
# 2. 在 files/lib/ 中创建软链接
# 3. 重建并验证
```

**软链接示例**:
```
files/lib/libmyapp.so.1 -> ../opt/myapp/lib/libmyapp.so.1
files/lib/libmyapp_core.so -> ../opt/myapp/lib/libmyapp_core.so
```

### 场景 4: 系统库依赖

```bash
# 问题：应用依赖系统库

python3 scripts/build_from_project.py \
  --input /path/to/system-dep-app \
  --workdir /tmp/linglong-build \
  --compact-check-timeout 60

# 自动化修复会：
# 1. 检测缺失的系统库
# 2. 使用 apt-file 匹配到系统包
# 3. 下载并提取包内容
# 4. 合并到 files/ 目录
# 5. 重建并验证
```

---

## CI/CD 集成

### GitHub Actions 示例

```yaml
name: Build Linglong Package

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    container:
      image: deepin/linglong-builder:latest

    steps:
    - uses: actions/checkout@v3

    - name: Install dependencies
      run: |
        apt-get update
        apt-get install -y apt-file python3-yaml
        apt-file update

    - name: Build with compatibility check
      run: |
        python3 scripts/build_from_project.py \
          --input . \
          --workdir /tmp/linglong-build \
          --compact-check-timeout 30 \
          --max-fix-attempts 3

    - name: Export package
      run: |
        cd /tmp/linglong-build
        ll-builder list
        ll-builder export --ref io.github.myapp:latest

    - name: Upload artifact
      uses: actions/upload-artifact@v3
      with:
        name: linglong-package
        path: /tmp/linglong-build/linglong/output/binary/*.uab
```

### GitLab CI 示例

```yaml
image: deepin/linglong-builder:latest

stages:
  - build
  - export
  - test

build:
  stage: build
  before_script:
    - apt-get update
    - apt-get install -y apt-file python3-yaml
    - apt-file update

  script:
    - python3 scripts/build_from_project.py
      --input .
      --workdir /tmp/linglong-build
      --compact-check-timeout 30
      --max-fix-attempts 3

  artifacts:
    paths:
      - /tmp/linglong-build/

export:
  stage: export
  dependencies:
    - build

  script:
    - cd /tmp/linglong-build
    - ll-builder list
    - ll-builder export --ref io.github.myapp:latest

  artifacts:
    paths:
      - /tmp/linglong-build/linglong/output/binary/*.uab

test:
  stage: test
  dependencies:
    - export

  script:
    - ll-cli install /tmp/linglong-build/linglong/output/binary/*.uab
    - ll-cli run io.github.myapp
```

---

## 调试模式

### 1. 增加超时时间

```bash
# 对于启动时间长的应用，增加超时时间
python3 scripts/build_from_project.py \
  --input /path/to/slow-app \
  --workdir /tmp/linglong-build \
  --compact-check-timeout 120
```

### 2. 查看详细日志

```bash
# 将构建输出保存到文件
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/linglong-build \
  --compact-check-timeout 30 2>&1 | tee debug.log

# 查看兼容性测试错误
cat /tmp/linglong-build/compact-check-errors/run-error.log
```

### 3. 手动检查依赖

```bash
# 进入工作目录
cd /tmp/linglong-build

# 查看缺失的依赖
cat missing_deps.csv

# 查找匹配的包
apt-file search libssl.so.1.1

# 手动测试应用
ll-builder run io.github.myapp:latest
```

### 4. 禁用兼容性测试（快速构建）

```bash
# 开发阶段快速迭代构建
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/linglong-build \
  --no-compact-check
```

---

## 批量构建

### 构建多个项目

```bash
#!/bin/bash
# 批量构建脚本

PROJECTS=(
  "/path/to/project1"
  "/path/to/project2"
  "/path/to/project3"
)

for PROJECT in "${PROJECTS[@]}"; do
  echo "Building $PROJECT..."
  python3 scripts/build_from_project.py \
    --input "$PROJECT" \
    --workdir "/tmp/linglong-build/$(basename $PROJECT)" \
    --compact-check-timeout 30 \
    --max-fix-attempts 3

  if [ $? -eq 0 ]; then
    echo "✓ $PROJECT built successfully"
  else
    echo "✗ $PROJECT failed"
  fi
done
```

### 并行构建

```bash
#!/bin/bash
# 并行构建脚本（使用 GNU Parallel）

build_project() {
  local PROJECT=$1
  echo "Building $PROJECT..."

  python3 scripts/build_from_project.py \
    --input "$PROJECT" \
    --workdir "/tmp/linglong-build/$(basename $PROJECT)" \
    --compact-check-timeout 30 \
    --max-fix-attempts 3

  if [ $? -eq 0 ]; then
    echo "✓ $PROJECT built successfully"
  else
    echo "✗ $PROJECT failed"
  fi
}

export -f build_project

# 并行构建所有项目
find /path/to/projects -maxdepth 1 -type d | \
  parallel -j 4 build_project {}
```

---

## 故障排查

### 问题 1: apt-file 未安装

**错误信息**:
```
Error: apt-file command not found
```

**解决方案**:
```bash
sudo apt-get update
sudo apt-get install -y apt-file
sudo apt-file update
```

### 问题 2: 兼容性测试超时

**错误信息**:
```
Compatibility check timed out after 30 seconds
```

**说明**:
- 这是正常的，超时（退出码 124）被视为成功
- 表示应用已经成功启动
- 如果需要更多时间，可以增加超时：
  ```bash
  --compact-check-timeout 60
  ```

### 问题 3: 超过最大修复次数

**错误信息**:
```
Exceeded maximum fix attempts (3)
```

**解决方案**:
```bash
# 增加最大修复次数
python3 scripts/build_from_project.py \
  --input /path/to/project \
  --workdir /tmp/linglong-build \
  --max-fix-attempts 5

# 或者手动修复：
cat /tmp/linglong-build/missing_deps.csv
# 根据缺失依赖手动添加到 linglong.yaml
```

### 问题 4: 找不到匹配的包

**错误信息**:
```
No package found for library "libcustom.so.1"
```

**解决方案**:
```bash
# 检查库是否在应用目录中
find /tmp/linglong-build -name "libcustom.so.1"

# 如果在应用目录中，检查是否需要软链接
# 如果不是，可能需要手动提供该库
```

### 问题 5: zstd 压缩失败

**错误信息**:
```
Error: Failed to compress files.tar.zst
```

**解决方案**:
```bash
# 安装 zstd
sudo apt-get install -y zstd

# 或者安装 Python zstd 模块
pip3 install zstandard
```

---

## 最佳实践

### 1. 开发环境

```bash
# 开发时推荐设置
python3 scripts/build_from_project.py \
  --input . \
  --workdir /tmp/linglong-build-dev \
  --compact-check-timeout 60 \
  --max-fix-attempts 5
```

**优点**:
- 更长的超时时间，便于调试
- 更多的修复尝试，处理复杂依赖
- 快速发现和修复问题

### 2. 测试环境

```bash
# 测试时推荐设置
python3 scripts/build_from_project.py \
  --input . \
  --workdir /tmp/linglong-build-test \
  --compact-check-timeout 30 \
  --max-fix-attempts 3
```

**优点**:
- 标准配置，模拟生产环境
- 适中的超时和修复次数
- 平衡准确性和效率

### 3. 生产环境

```bash
# 生产时推荐设置
python3 scripts/build_from_project.py \
  --input . \
  --workdir /tmp/linglong-build-prod \
  --no-compact-check
```

**优点**:
- 构建速度快
- 通过其他方式（测试环境）确保质量
- 避免在生产环境运行兼容性测试

### 4. 持续集成

```bash
# CI/CD 推荐
python3 scripts/build_from_project.py \
  --input . \
  --workdir /tmp/linglong-build-ci \
  --compact-check-timeout 30 \
  --max-fix-attempts 3
```

**优点**:
- 与测试环境配置一致
- 自动化质量检查
- 集成到 CI/CD 流水线

### 5. 性能优化

```bash
# 提前更新 apt-file 缓存
apt-file update

# 使用本地缓存
export LINYAPS_CACHE_DIR=/opt/linyaps-cache

# 并行处理
# （内部已使用多进程，无需手动配置）
```

---

## 总结

兼容性测试和依赖修复功能为 linyaps-packager-skill 增加了自动化能力，可以：

1. **自动检测运行时问题**
2. **智能分析缺失依赖**
3. **自动下载和安装依赖**
4. **创建软链接修复路径问题**
5. **多轮尝试提高成功率**

合理使用这些功能可以显著提高打包成功率和用户体验！

**文档版本**: 1.0
**最后更新**: 2026-03-24

# convert_package.sh 优化完成报告

## 优化概述

本次优化成功将 `convert_package.sh` 脚本升级，使其在处理 deb 包转换时遵循 `linyaps-pica-helper.sh` 的正确用法和 API 参数，同时保留了完整的转包流程。对于 AppImage 和 Flatpak 格式的转换，保持了原有逻辑不变。

## 主要变更

### 1. Deb 转换流程优化

#### 原始问题
- 使用了错误的 ll-pica API：`ll-pica deb convert -c <deb> -w <workdir>`
- 缺少兼容性测试（compact check）
- 缺少依赖分析和自动修复功能
- 缺少 layer 导出功能

#### 优化后的流程
- 优先使用 `linyaps-pica-helper.sh` 进行 deb 转换
- 保留完整的转包流程，包括：
  - 兼容性测试（compact check）
  - 依赖分析（使用 apt-file）
  - 依赖修复（下载并安装缺失的依赖包）
  - 非标准目录库扫描和软链接创建
  - 自动重建和验证
  - Layer 导出和存储

#### 新增参数
```bash
--enable-compact-check       # 启用兼容性测试（默认：true）
--no-compact-check           # 禁用兼容性测试
--compact-check-timeout <s>  # 兼容性测试超时时间（默认：30秒）
--enable-layer-export        # 启用 layer 导出（默认：true）
--no-layer-export            # 禁用 layer 导出
--final-missing-csv <path>   # 指定 final-missing CSV 文件路径
--ll-stored-pool <dir>       # 指定 layer 存储目录（默认：./StoredPool）
```

### 2. 降级机制

当 `linyaps-pica-helper.sh` 不可用时，自动降级到简单模式：

```bash
ll-pica convert -c <deb> -w <workdir> [-b]
```

### 3. AppImage 和 Flatpak 转换

保持原有逻辑不变，继续使用 ll-pica 的标准 API。

## 文件变更

### 修改的文件
1. [`scripts/convert_package.sh`](scripts/convert_package.sh) - 主要优化文件

### 新增的文件
1. [`docs/convert-package-optimization.md`](docs/convert-package-optimization.md) - 详细优化说明
2. [`docs/optimization-summary.md`](docs/optimization-summary.md) - 优化总结文档
3. [`scripts/test_convert_package.sh`](scripts/test_convert_package.sh) - 测试脚本

## 使用示例

### Deb 转换（使用 linyaps-pica-helper）

```bash
# 基本转换
bash scripts/convert_package.sh deb ./demo.deb

# 指定工作目录
bash scripts/convert_package.sh deb ./demo.deb --workdir /tmp/pica-work

# 禁用兼容性测试
bash scripts/convert_package.sh deb ./demo.deb --no-compact-check

# 自定义兼容性测试超时时间
bash scripts/convert_package.sh deb ./demo.deb --compact-check-timeout 60

# 禁用 layer 导出
bash scripts/convert_package.sh deb ./demo.deb --no-layer-export

# 指定 final-missing CSV 文件
bash scripts/convert_package.sh deb ./demo.deb --final-missing-csv /path/to/final-missing.csv

# 指定 layer 存储目录
bash scripts/convert_package.sh deb ./demo.deb --ll-stored-pool /path/to/StoredPool
```

### AppImage 转换

```bash
# 基本转换
bash scripts/convert_package.sh appimage ./demo.AppImage --id io.github.demo.app --version 1.0.0.0

# 指定名称和描述
bash scripts/convert_package.sh appimage ./demo.AppImage \
  --id io.github.demo.app \
  --version 1.0.0.0 \
  --name "Demo Application" \
  --description "A demo application"

# 转换后构建
bash scripts/convert_package.sh appimage ./demo.AppImage \
  --id io.github.demo.app \
  --version 1.0.0.0 \
  --build
```

### Flatpak 转换

```bash
# 基本转换
bash scripts/convert_package.sh flatpak org.kde.kate

# 指定 base 和版本
bash scripts/convert_package.sh flatpak org.kde.kate \
  --base org.deepin.base/23.1.0 \
  --base-version 23.1.0 \
  --version 23.08.4

# 转换后构建并导出 layer
bash scripts/convert_package.sh flatpak org.kde.kate --build --layer
```

## linyaps-pica-helper 流程说明

### 完整流程

```
1. ll-pica convert -c <deb> -w <workdir>
   ↓
2. ll-builder build
   ↓
3. compact check (timeout 30s)
   ↓
4. 如果构建失败（退出码 255）：
   a. 分析缺失依赖（ldd + apt-file）
   b. 下载并安装依赖包
   c. 扫描非标准目录中的库
   d. 创建软链接
   e. 重建并验证
   f. 最多 3 次修复尝试
   ↓
5. 如果所有修复失败：
   执行最终构建（跳过测试）
   ↓
6. 导出 layer（如果启用）
   ↓
7. 存储 layer 到指定目录
```

### 输出文件

- `missing_deps.csv`：缺失的依赖列表
- `missing-libs.packages`：匹配的包列表
- `nonStrDir_found_libs.csv`：在非标准目录中找到的库
- `files.tar.zst`：应用文件的压缩归档
- `compat-check-errors/run-error.log`：兼容性测试错误日志
- `linglong.yaml`：更新后的配置文件（包含 buildext.apt.depends）

## 技术细节

### 1. linyaps-pica-helper 调用方式

```bash
bash ${LINYAPS_HELPER_DIR}/linyaps-pica-helper.sh \
  --deb_pool=<deb文件所在目录> \
  --ll_stored_pool=<layer存储目录> \
  --workdir=<工作目录> \
  --enable_compact_check=<true|false> \
  --enable_layer_export=<true|false> \
  [--final_missing_csv=<CSV文件路径>]
```

### 2. 降级机制

当 `linyaps-pica-helper.sh` 不可用时，自动降级到简单模式：

```bash
ll-pica convert -c <deb> -w <workdir> [-b]
```

### 3. 参数传递

- `--enable-compact-check`：传递给 `linyaps-pica-helper.sh` 的 `--enable_compact_check`
- `--enable-layer-export`：传递给 `linyaps-pica-helper.sh` 的 `--enable_layer_export`
- `--final-missing-csv`：传递给 `linyaps-pica-helper.sh` 的 `--final_missing_csv`
- `--ll-stored-pool`：传递给 `linyaps-pica-helper.sh` 的 `--ll_stored_pool`

## 验证结果

### 语法检查
```bash
bash -n scripts/convert_package.sh
```
✅ 通过

### 帮助信息测试
```bash
bash scripts/convert_package.sh -h
```
✅ 正常显示帮助信息

## 注意事项

1. **linyaps-pica-helper.sh 位置**：默认在 `../linyaps-pica-helper/linyaps-pica-helper.sh`，相对于 `scripts/` 目录
2. **降级机制**：当 `linyaps-pica-helper.sh` 不可用时，会自动降级到简单模式，但会失去兼容性测试和依赖修复功能
3. **兼容性测试**：默认启用，超时时间为 30 秒
4. **Layer 导出**：默认启用，导出的 layer 会存储到 `--ll-stored-pool` 指定的目录
5. **依赖修复**：最多尝试 3 次，如果所有尝试都失败，会执行最终构建（跳过测试）

## 优势

1. **完整的转包流程**
   - 兼容性测试
   - 依赖分析和修复
   - 自动重建和验证
   - Layer 导出

2. **降级机制**
   - 当 linyaps-pica-helper 不可用时，自动降级
   - 保证基本功能可用

3. **灵活的配置**
   - 支持启用/禁用兼容性测试
   - 支持自定义超时时间
   - 支持启用/禁用 layer 导出

4. **向后兼容**
   - AppImage 和 Flatpak 转换保持不变
   - 原有参数继续有效

## 版本历史

- **1.0.0** (2026-04-01)：初始版本，优化 deb 转换流程，集成 linyaps-pica-helper

## 总结

本次优化成功解决了以下问题：

1. ✅ 修正了错误的 ll-pica API 使用
2. ✅ 集成了 linyaps-pica-helper 的完整转包流程
3. ✅ 添加了兼容性测试功能
4. ✅ 添加了依赖分析和自动修复功能
5. ✅ 添加了 layer 导出功能
6. ✅ 实现了降级机制
7. ✅ 保持了 AppImage 和 Flatpak 转换的向后兼容性

优化后的 `convert_package.sh` 脚本现在可以：
- 使用 linyaps-pica-helper 进行专业的 deb 包转换
- 自动进行兼容性测试和依赖修复
- 导出并存储 layer 文件
- 在 linyaps-pica-helper 不可用时降级到简单模式
- 保持对 AppImage 和 Flatpak 转换的完整支持

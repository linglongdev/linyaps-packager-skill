# convert_package.sh 优化总结

## 优化目标

针对 deb 包转换业务，使其遵循 `linyaps-pica-helper.sh` 的正确用法和 API 参数，同时保留完整的转包流程。对于 AppImage 和 Flatpak 格式，保持原有逻辑不变。

## 核心问题

### 原始代码的问题

1. **错误的 API 使用**
   ```bash
   # 错误：使用了不存在的 deb 子命令
   ll-pica deb convert -c <deb> -w <workdir>
   ```

2. **缺少关键功能**
   - 没有兼容性测试（compact check）
   - 没有依赖分析和自动修复
   - 没有 layer 导出功能

3. **不符合 linyaps-pica-helper 的设计**
   - linyaps-pica-helper 提供了完整的转包流程
   - 包括依赖分析、修复、重建、验证等步骤
   - 原始代码没有利用这些功能

## 优化方案

### 1. 集成 linyaps-pica-helper

```bash
# 优化后：使用 linyaps-pica-helper
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

### 3. 新增参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--enable-compact-check` | 启用兼容性测试 | true |
| `--no-compact-check` | 禁用兼容性测试 | - |
| `--compact-check-timeout` | 兼容性测试超时时间（秒） | 30 |
| `--enable-layer-export` | 启用 layer 导出 | true |
| `--no-layer-export` | 禁用 layer 导出 | - |
| `--final-missing-csv` | 指定 final-missing CSV 文件路径 | - |
| `--ll-stored-pool` | 指定 layer 存储目录 | ./StoredPool |

## linyaps-pica-helper 完整流程

### 流程图

```
ll-pica convert
    ↓
ll-builder build
    ↓
compact check (timeout 30s)
    ↓
如果构建失败（退出码 255）：
    ├─ 分析缺失依赖（ldd + apt-file）
    ├─ 下载并安装依赖包
    ├─ 扫描非标准目录中的库
    ├─ 创建软链接
    ├─ 重建并验证
    └─ 最多 3 次修复尝试
    ↓
如果所有修复失败：
    执行最终构建（跳过测试）
    ↓
导出 layer（如果启用）
    ↓
存储 layer 到指定目录
```

### 关键功能

1. **兼容性测试（Compact Check）**
   - 使用 `timeout 30 ll-builder run` 命令
   - 退出码 124：超时，视为测试通过
   - 退出码 0：正常退出，测试通过
   - 其他退出码：测试失败

2. **依赖分析**
   - 使用 `ldd` 检测缺失的动态库
   - 使用 `apt-file search` 查找提供这些库的包
   - 并行处理以提高性能

3. **依赖修复**
   - 下载缺失的依赖包
   - 解压到临时目录
   - 合并到 files 目录
   - 更新 linglong.yaml

4. **非标准目录库扫描**
   - 扫描非标准目录中的库文件
   - 创建软链接到 files/lib 目录
   - 支持通配符匹配

5. **Layer 导出**
   - 使用 `ll-builder export --no-develop --layer -z zstd`
   - 存储到指定目录
   - 根据兼容性测试结果选择存储位置

## 使用示例

### Deb 转换

```bash
# 基本转换（使用 linyaps-pica-helper）
bash scripts/convert_package.sh deb ./demo.deb

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

### AppImage 转换（保持不变）

```bash
bash scripts/convert_package.sh appimage ./demo.AppImage \
  --id io.github.demo.app \
  --version 1.0.0.0 \
  --name "Demo Application" \
  --description "A demo application" \
  --build
```

### Flatpak 转换（保持不变）

```bash
bash scripts/convert_package.sh flatpak org.kde.kate \
  --base org.deepin.base/23.1.0 \
  --base-version 23.1.0 \
  --version 23.08.4 \
  --build \
  --layer
```

## 输出文件

| 文件 | 说明 |
|------|------|
| `missing_deps.csv` | 缺失的依赖列表（由 ldd 检测） |
| `missing-libs.packages` | 匹配的包列表（由 apt-file 分析） |
| `nonStrDir_found_libs.csv` | 在非标准目录中找到的库 |
| `files.tar.zst` | 应用文件的压缩归档 |
| `compat-check-errors/run-error.log` | 兼容性测试错误日志 |
| `linglong.yaml` | 更新后的配置文件（包含 buildext.apt.depends） |

## 技术细节

### 1. linyaps-pica-helper 调用

```bash
bash ${LINYAPS_HELPER_DIR}/linyaps-pica-helper.sh \
  --deb_pool="$(dirname "${deb_file}")" \
  --ll_stored_pool="${ll_stored_pool}" \
  --workdir="${workdir}" \
  --enable_compact_check="${enable_compact_check}" \
  --enable_layer_export="${enable_layer_export}" \
  [--final_missing_csv="${final_missing_csv}"]
```

### 2. 降级机制

```bash
# 检查 linyaps-pica-helper 是否可用
if check_linyaps_helper; then
  # 使用 linyaps-pica-helper
  deb_convert_with_helper ...
else
  # 降级到简单模式
  deb_convert_simple ...
fi
```

### 3. 参数映射

| convert_package.sh 参数 | linyaps-pica-helper 参数 |
|------------------------|--------------------------|
| `--enable-compact-check` | `--enable_compact_check` |
| `--no-compact-check` | `--enable_compact_check=false` |
| `--enable-layer-export` | `--enable_layer_export` |
| `--no-layer-export` | `--enable_layer_export=false` |
| `--final-missing-csv` | `--final_missing_csv` |
| `--ll-stored-pool` | `--ll_stored_pool` |

## 注意事项

1. **linyaps-pica-helper.sh 位置**
   - 默认路径：`../linyaps-pica-helper/linyaps-pica-helper.sh`
   - 相对于 `scripts/` 目录

2. **降级机制**
   - 当 `linyaps-pica-helper.sh` 不可用时，自动降级
   - 降级后会失去兼容性测试和依赖修复功能

3. **兼容性测试**
   - 默认启用
   - 超时时间：30 秒
   - 超时视为测试通过

4. **Layer 导出**
   - 默认启用
   - 导出格式：zstd 压缩
   - 存储位置：`--ll-stored-pool` 指定的目录

5. **依赖修复**
   - 最多尝试 3 次
   - 如果所有尝试都失败，执行最终构建（跳过测试）

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

# 包格式转换说明

当输入对象已经是现成的软件包，而不是源码项目时，参考这份说明。

## 封装的命令

封装脚本会根据输入类型调用对应命令：

- `deb`：使用内置的 `scripts/deb_converter.py`（基于 linyaps-pica-helper 的完整功能）
- `appimage`：`ll-pica appimage convert`
- `flatpak`：`ll-pica flatpak convert`

如果系统中没有 `ll-pica`，或者当前 `ll-pica` 不支持对应子命令，应停止操作，并提示用户安装或升级 `linglong-pica`。`ll-pica` 由 `linglong-pica` 包提供。

## Deb 包转换

### 转换流程

Deb 包转换使用内置的 `deb_converter.py` 脚本，提供完整的兼容性测试和依赖修复功能：

```
Phase 1: ll-pica convert
    ↓
Phase 2: 初始构建 (ll-builder build)
    ↓
Phase 3: 兼容性测试 (ll-builder run)
    ↓
检测失败？ → 否：Phase 7: 导出 Layer → 完成
    ↓ 是
Phase 4: 依赖修复尝试
    ↓
分析缺失依赖 (apt-file)
    ↓
下载并安装依赖 或 扫描非标准目录库
    ↓
Phase 5: 重建 (ll-builder build)
    ↓
Phase 6: 兼容性测试 (ll-builder run)
    ↓
检测失败？ → 否：Phase 7: 导出 Layer → 完成
    ↓ 是
修复次数 < 3？ → 是：返回 Phase 4
    ↓ 否
最终构建 (ll-builder build --skip-output-check)
    ↓
Phase 7: 导出 Layer → 完成
```

### 使用示例

```bash
# 基本转换
bash scripts/convert_package.sh deb ./demo.deb --workdir /tmp/pica-work

# 启用兼容性测试和 layer 导出
bash scripts/convert_package.sh deb ./demo.deb \
  --workdir /tmp/pica-work \
  --enable-compact-check \
  --enable-layer-export

# 使用 final-missing CSV 文件更新包信息
bash scripts/convert_package.sh deb ./demo.deb \
  --workdir /tmp/pica-work \
  --final-missing-csv /path/to/final-missing.csv \
  --ll-stored-pool /path/to/StoredPool

# 禁用兼容性测试
bash scripts/convert_package.sh deb ./demo.deb \
  --workdir /tmp/pica-work \
  --no-compact-check

# 自定义兼容性测试超时时间
bash scripts/convert_package.sh deb ./demo.deb \
  --workdir /tmp/pica-work \
  --compact-check-timeout 60
```

### Deb 转换选项

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--workdir <dir>` | 工作目录 | ./pica-work |
| `--enable-compact-check` | 启用兼容性测试 | 启用 |
| `--no-compact-check` | 禁用兼容性测试 | - |
| `--compact-check-timeout <s>` | 兼容性测试超时时间（秒） | 30 |
| `--enable-layer-export` | 启用 layer 导出 | 启用 |
| `--no-layer-export` | 禁用 layer 导出 | - |
| `--final-missing-csv <path>` | final-missing CSV 文件路径 | - |
| `--ll-stored-pool <dir>` | layer 存储目录 | ./StoredPool |
| `--verbose` | 显示详细输出 | - |

### 输出文件

- `missing_deps.csv`：缺失的依赖列表
- `missing-libs.packages`：匹配的包列表
- `nonStrDir_found_libs.csv`：非标准目录中的库
- `files.tar.zst`：应用文件的压缩归档
- `compat-check-errors/run-error.log`：兼容性测试错误日志
- `*_binary.layer`：导出的 layer 文件

### Layer 存储位置

- 如果兼容性测试通过：存储在 `--ll-stored-pool` 指定的目录
- 如果兼容性测试未执行或失败：存储在 `--ll-stored-pool/forceTested` 目录

## AppImage 转换

### 使用示例

```bash
bash scripts/convert_package.sh appimage ./demo.AppImage \
  --id io.github.demo.app \
  --version 1.0.0.0 \
  --build
```

### AppImage 转换选项

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--id <appid>` | 应用 ID（必需） | - |
| `--version <ver>` | 版本（必需） | - |
| `--name <name>` | 应用名称 | - |
| `--description <text>` | 描述 | - |
| `--workdir <dir>` | 工作目录 | - |
| `--build` | 转换后构建 | - |

## Flatpak 转换

### 使用示例

```bash
bash scripts/convert_package.sh flatpak org.kde.kate --build
```

### Flatpak 转换选项

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--base <base>` | 基础包 | - |
| `--base-version <ver>` | 基础包版本 | - |
| `--version <ver>` | 版本 | - |
| `--build` | 转换后构建 | - |
| `--layer` | 导出 layer | - |

## 失败后的排查顺序

遇到转换失败时，建议按以下顺序排查：

1. 直接重跑脚本打印出的底层命令，并根据需要补充 `--help` 或其他调试参数。
2. 确认系统中安装的 `linglong-pica` 是否包含对应的转换能力。
3. 如果转换对象是 Flatpak，再额外确认 `flatpak` 和 `ostree` 是否可用。
4. 对于 Deb 包转换，检查 `apt-file` 是否已安装并更新：`apt-file update`
5. 检查 Python 依赖是否已安装：`pip3 install pyyaml`
6. 使用 `--verbose` 选项查看详细输出以定位问题。

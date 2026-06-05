# 输出级别控制实现

## 实现日期
2026-04-02

## 需求

添加输出级别控制功能，让用户可以选择：
- **quiet**：只显示最终结果
- **normal**：显示简要的进度信息（默认）
- **verbose**：显示详细的调试信息

## 实现内容

### 1. scripts/deb_converter.py

#### 新增方法：`_print()`

在 `DebConverter` 类中添加了 `_print()` 方法，用于根据输出级别控制消息显示：

```python
def _print(self, message: str, level: str = "normal") -> None:
    """
    根据输出级别打印消息
    
    Args:
        message: 要打印的消息
        level: 消息级别（quiet/normal/verbose）
    """
    if self.output_level == "quiet":
        # quiet 模式：只打印最终结果
        return
    elif self.output_level == "normal":
        # normal 模式：打印 normal 和 quiet 级别的消息
        if level in ["normal", "quiet"]:
            print(message)
    elif self.output_level == "verbose":
        # verbose 模式：打印所有级别的消息
        print(message)
```

#### 修改方法：`__init__()`

添加了 `quiet` 参数和 `output_level` 属性：

```python
def __init__(
    self,
    deb_file: Path,
    workdir: Path,
    enable_compact_check: bool = True,
    compact_check_timeout: int = 30,
    enable_layer_export: bool = True,
    ll_stored_pool: Optional[Path] = None,
    final_missing_csv: Optional[Path] = None,
    verbose: bool = False,
    quiet: bool = False  # 新增
):
    # ... 现有代码 ...
    self.verbose = verbose
    self.quiet = quiet
    
    # 输出级别：quiet < normal < verbose
    self.output_level = "quiet" if quiet else ("verbose" if verbose else "normal")
```

#### 修改方法：`convert()`

将所有 `print()` 语句替换为 `self._print()`，并添加适当的级别：

```python
# Phase 2: 初始构建
self._print("\n" + "=" * 60, "normal")
self._print("Phase 2: Initial Build (skip output check)", "normal")
self._print("=" * 60, "normal")

# ... 其他代码 ...

self._print(f"\n✓ Build successful", "normal")
```

#### 修改方法：`main()`

添加了 `--quiet` 命令行参数：

```python
parser.add_argument(
    "--quiet",
    action="store_true",
    help="只显示最终结果"
)

# ... 现有代码 ...

converter = DebConverter(
    # ... 现有参数 ...
    verbose=args.verbose,
    quiet=args.quiet  # 新增
)
```

### 2. scripts/convert_package.sh

#### 修改内容

1. 在 `usage()` 函数中添加 `--quiet` 选项说明：

```bash
Deb conversion options:
  --workdir <dir>              Working directory (default: ./pica-work)
  --enable-compact-check       Enable compact check after build (default: true)
  --no-compact-check           Disable compact check
  --compact-check-timeout <s>  Compact check timeout in seconds (default: 30)
  --enable-layer-export        Export layer if build passes (default: true)
  --no-layer-export            Disable layer export
  --final-missing-csv <path>   Path to final-missing CSV file for package info lookup
  --ll-stored-pool <dir>       Directory to store exported layers (default: ./StoredPool)
  --verbose                    Show verbose output
  --quiet                      Show only final results  # 新增
```

2. 在 `deb_convert()` 函数中添加 `quiet` 参数：

```bash
deb_convert() {
  local deb_file="$1"
  local workdir="$2"
  local enable_compact_check="$3"
  local compact_check_timeout="$4"
  local enable_layer_export="$5"
  local final_missing_csv="$6"
  local ll_stored_pool="$7"
  local verbose="$8"
  local quiet="$9"  # 新增
```

3. 在 `deb_convert()` 函数中传递 `--quiet` 参数：

```bash
if [ "${quiet}" = "true" ]; then
  python_cmd+=(--quiet)
fi
```

4. 在参数解析中添加 `--quiet` 选项：

```bash
--verbose)
  verbose="true"
  shift
  ;;
--quiet)
  quiet="true"
  shift
  ;;
```

5. 在调用 `deb_convert()` 时传递 `quiet` 参数：

```bash
deb_convert \
  "${target}" \
  "${workdir}" \
  "${enable_compact_check}" \
  "${compact_check_timeout}" \
  "${enable_layer_export}" \
  "${final_missing_csv}" \
  "${ll_stored_pool}" \
  "${verbose}" \
  "${quiet}"  # 新增
```

## 使用示例

### Normal 模式（默认）

```bash
python3 scripts/deb_converter.py demo.deb --workdir ./workdir
```

**输出**：
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

============================================================
Conversion Summary
============================================================
Result: Conversion completed successfully
Build Status: passed
Compat Check Status: passed
Layer Export Status: passed
```

### Quiet 模式

```bash
python3 scripts/deb_converter.py demo.deb --workdir ./workdir --quiet
```

**输出**：
```
============================================================
Final Status
============================================================
Build Status: passed
Compat Check Status: passed
Layer Export Status: passed

============================================================
Conversion Summary
============================================================
Result: Conversion completed successfully
Build Status: passed
Compat Check Status: passed
Layer Export Status: passed
```

### Verbose 模式

```bash
python3 scripts/deb_converter.py demo.deb --workdir ./workdir --verbose
```

**输出**：
```
============================================================
Phase 1: ll-pica convert
============================================================
Executing: ll-pica convert -c demo.deb -w ./workdir/pica-work
Working directory: ./workdir/pica-work
✓ ll-pica convert successful

============================================================
Phase 2: Initial Build (skip output check)
============================================================
Executing: ll-builder build --skip-output-check
Working directory: ./workdir/pica-work/package/demo
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

============================================================
Conversion Summary
============================================================
Result: Conversion completed successfully
Build Status: passed
Compat Check Status: passed
Layer Export Status: passed
```

### 使用 convert_package.sh

```bash
# Normal 模式（默认）
bash scripts/convert_package.sh deb demo.deb --workdir ./workdir

# Quiet 模式
bash scripts/convert_package.sh deb demo.deb --workdir ./workdir --quiet

# Verbose 模式
bash scripts/convert_package.sh deb demo.deb --workdir ./workdir --verbose
```

## 输出级别说明

### quiet 模式
- 只显示最终结果（Final Status 和 Conversion Summary）
- 适合脚本自动化和 CI/CD 环境
- 减少输出噪音，便于日志分析

### normal 模式（默认）
- 显示简要的进度信息（Phase 标题和关键结果）
- 适合一般使用和交互式操作
- 提供足够的反馈，但不会过于冗长

### verbose 模式
- 显示所有详细信息，包括命令执行和详细错误
- 适合问题排查和调试
- 提供完整的执行过程信息

## 向后兼容性

- 默认行为保持不变（normal 模式）
- 所有现有命令行参数保持不变
- 只是新增了 `--quiet` 选项
- API 接口保持兼容（`quiet` 参数有默认值 `False`）

## 测试建议

1. **测试 normal 模式**：验证默认输出是否正确显示进度信息
2. **测试 quiet 模式**：验证是否只显示最终结果
3. **测试 verbose 模式**：验证是否显示所有详细信息
4. **测试错误情况**：验证错误信息在所有模式下都能正确显示
5. **测试 convert_package.sh**：验证 shell 脚本是否正确传递参数

## 预期效果

1. **更好的用户体验**：用户可以根据需要选择输出级别
2. **更适合自动化**：quiet 模式适合脚本和 CI/CD 环境
3. **更好的调试体验**：verbose 模式提供详细的调试信息
4. **保持向后兼容**：默认行为不变，不影响现有用户

## 相关文档

- [SKILL.md](../SKILL.md) - 玲珑打包技能主文档
- [scripts/deb_converter.py](../scripts/deb_converter.py) - Deb 包转换器实现
- [scripts/convert_package.sh](../scripts/convert_package.sh) - 包格式转换脚本

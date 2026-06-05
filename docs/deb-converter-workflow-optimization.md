# Deb 转换器工作流程优化

## 优化日期
2026-04-02

## 问题描述

原有的 deb 转换工作流程存在以下问题：

1. **第一次构建过于严格**：使用标准构建（`ll-builder build`），可能因为一些非必要的库或插件导致构建失败
2. **触发条件不合理**：基于构建退出码（255）来触发依赖修复，而不是基于实际的运行时测试结果
3. **工作流程不够灵活**：无法处理那些在非标准目录中的库或可选插件

## 优化方案

### 核心改进

1. **第一次构建使用 `--skip-output-check`**：跳过输出检查，确保构建能够成功完成
2. **通过运行时测试验证**：构建成功后通过 `ll-builder run` 进行兼容性测试，这是更真实的验证方式
3. **修复触发条件更合理**：只有当兼容性测试失败时才触发依赖修复流程

### 新的工作流程

```
Phase 1: ll-pica convert
    ↓
Phase 2: 初始构建 (ll-builder build --skip-output-check)
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
Phase 7: 最终构建 (ll-builder build --skip-output-check)
    ↓
Phase 8: 导出 Layer → 完成
```

## 修改的文件

### 1. scripts/deb_converter.py

#### 修改位置：`convert()` 方法（约第 753-783 行）

**修改前**：
```python
# Phase 2: 初始构建
print("\n" + "=" * 60)
print("Phase 2: Initial Build")
print("=" * 60)

build_success, build_msg = self._execute_build(skip_output_check=False)

if not build_success:
    print(f"\n✗ Initial build failed: {build_msg}")
    return False, build_msg

print(f"\n✓ Build successful")

# Phase 3: 兼容性测试
if self.enable_compact_check:
    print("\n" + "=" * 60)
    print("Phase 3: Compat Check")
    print("=" * 60)
    
    check_success, check_msg = self.compat_checker.check()
    self.compact_check_status = self.compat_checker.get_status()
    
    if check_success:
        print(f"\n✓ Compat check passed: {check_msg}")
    else:
        print(f"\n✗ Compat check failed: {check_msg}")
        # 如果构建失败（退出码 255），尝试依赖修复
        if self.build_status == "failed":
            return self._attempt_dependency_fix()
else:
    print("\nCompat check disabled, skipping")
```

**修改后**：
```python
# Phase 2: 初始构建（跳过输出检查，避免因非必要库导致构建失败）
print("\n" + "=" * 60)
print("Phase 2: Initial Build (skip output check)")
print("=" * 60)

build_success, build_msg = self._execute_build(skip_output_check=True)

if not build_success:
    print(f"\n✗ Initial build failed: {build_msg}")
    return False, build_msg

print(f"\n✓ Build successful")

# Phase 3: 兼容性测试
if self.enable_compact_check:
    print("\n" + "=" * 60)
    print("Phase 3: Compat Check")
    print("=" * 60)
    
    check_success, check_msg = self.compat_checker.check()
    self.compact_check_status = self.compat_checker.get_status()
    
    if check_success:
        print(f"\n✓ Compat check passed: {check_msg}")
    else:
        print(f"\n✗ Compat check failed: {check_msg}")
        # 兼容性测试失败，触发依赖修复流程
        return self._attempt_dependency_fix()
else:
    print("\nCompat check disabled, skipping")
```

#### 修改位置：`_attempt_dependency_fix()` 方法（约第 421-470 行）

**修改内容**：
- Phase 编号从 3/4/5 改为 4/5/6，以匹配新的工作流程

#### 修改位置：`_attempt_final_build()` 方法（约第 472-490 行）

**修改内容**：
- Phase 编号从 6 改为 7

### 2. SKILL.md

#### 修改位置：Deb 包转换完整流程（约第 100-130 行）

**修改内容**：
- 更新了工作流程图，反映新的 Phase 编号和构建参数
- 添加了关键改进说明

#### 修改位置：注意事项（约第 240-250 行）

**修改内容**：
- 添加了关于第一次构建使用 `--skip-output-check` 的说明
- 添加了关于修复触发条件的说明

## 关键改进点

1. **Phase 2 标题更新**：从 "Initial Build" 改为 "Initial Build (skip output check)"，明确说明跳过输出检查

2. **构建参数修改**：将 `skip_output_check=False` 改为 `skip_output_check=True`，第一次构建使用 `--skip-output-check` 参数

3. **触发条件修改**：移除了 `if self.build_status == "failed":` 的判断，现在只要兼容性测试失败就触发依赖修复流程

4. **Phase 编号调整**：调整了所有 Phase 的编号，使其与新的工作流程保持一致

## 预期效果

1. **更高的构建成功率**：第一次构建使用 `--skip-output-check`，避免因非必要库或插件导致构建失败

2. **更准确的验证**：通过运行时测试验证应用是否能正常启动，这是更真实的验证方式

3. **更合理的修复触发**：只有当兼容性测试失败时才触发依赖修复，而不是基于构建退出码

4. **更好的用户体验**：减少了不必要的失败，提高了转换效率

## 测试建议

1. **测试正常情况**：使用一个依赖完整的 deb 包，验证第一次构建和兼容性测试都能通过

2. **测试依赖缺失情况**：使用一个缺少必要依赖的 deb 包，验证依赖修复流程能够正常工作

3. **测试非标准目录库**：使用一个库文件在非标准目录中的 deb 包，验证软链接修复功能

4. **测试多次修复**：使用一个需要多次修复才能成功的 deb 包，验证最多 3 次修复尝试的限制

## 向后兼容性

- 所有命令行参数保持不变
- 所有输出文件格式保持不变
- 所有 API 接口保持不变
- 只是内部工作流程的优化，不影响外部使用

## 相关文档

- [SKILL.md](../SKILL.md) - 玲珑打包技能主文档
- [scripts/deb_converter.py](../scripts/deb_converter.py) - Deb 包转换器实现
- [references/compatibility-check-workflow.md](../references/compatibility-check-workflow.md) - 兼容性测试工作流

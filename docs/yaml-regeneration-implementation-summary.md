# YAML 重新生成功能实现总结

## 实现日期
2026-04-02

## 问题描述

### 问题1：files 目录未从最新的 files.tar.zst 重新解压
在依赖修复流程中，每次修复尝试没有从最新的 `files.tar.zst` 重新解压 `files` 目录，导致后续修复可能使用过时的文件内容。

**具体表现**：
- `scan_non_std_dir_libraries()` 只在 `files` 目录**不存在**时才解压 `files.tar.zst`
- 如果 `files` 目录已存在（从上一次修复或构建中），不会重新解压
- 重建后 `_update_files_tar()` 更新了 `files.tar.zst`，但 `files` 目录本身没有被更新
- `merge_dependencies_to_files()` 直接合并到 `files` 目录，不会先解压最新的 `files.tar.zst`

### 问题2：修复后未重新生成 linglong.yaml
按照 pica-helper 设计，每次修复后应该生成新的 linglong.yaml，但当前实现中多次构建使用的还是第一次构建的版本。

**具体表现**：
- 没有实现 `rebuildWorkdirGen()` 的等效功能
- 没有模板文件用于生成新的 yaml
- 每次修复后只是修改现有的 yaml，而不是生成新的 yaml
- 没有提取原始 yaml 信息的函数

## 解决方案

### 1. 创建模板文件

#### templates/linglong-rebuild.yaml
包含 runtime 字段的重建模板，用于有 runtime 的应用。

```yaml
# SPDX-FileCopyrightText: 2023 UnionTech Software Technology Co., Ltd.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

version: "${orig_yaml_version}"

package:
  id: ${orig_yaml_id}
  name: "${orig_yaml_name}"
  version: ${orig_yaml_version}
  kind: app
  description: |
    ${orig_yaml_description}

base: ${orig_yaml_base}
runtime: ${orig_yaml_runtime}

command:
  - ${orig_yaml_command}

source:
  - kind: local
    name: "${orig_yaml_name}"

build: |
  ##Extract res
  cp -rf /project/files/* $PREFIX/
```

#### templates/linglong-rebuild-WithoutRuntime.yaml
不包含 runtime 字段的重建模板，用于没有 runtime 的应用。

```yaml
# SPDX-FileCopyrightText: 2023 UnionTech Software Technology Co., Ltd.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

version: "${orig_yaml_version}"

package:
  id: ${orig_yaml_id}
  name: "${orig_yaml_name}"
  version: ${orig_yaml_version}
  kind: app
  description: |
    ${orig_yaml_description}

base: ${orig_yaml_base}

command:
  - ${orig_yaml_command}

source:
  - kind: local
    name: "${orig_yaml_name}"

build: |
  ##Extract res
  cp -rf /project/files/* $PREFIX/
```

### 2. 修改 dependency_fixer.py

#### 新增方法

##### `_extract_yaml_info(yaml_file: Path) -> dict`
提取 linglong.yaml 的信息，包括 id、name、version、kind、description、base、runtime、command。

**功能**：
- 读取 yaml 文件
- 提取 package 信息
- 提取 base 和 runtime
- 提取 command（支持数组和字符串格式）

**返回值**：包含所有 yaml 信息的字典

##### `_generate_rebuild_yaml(origin_yaml, target_yaml, depends, buildext_depends) -> bool`
生成重建用的 linglong.yaml。

**功能**：
- 提取原始 yaml 信息
- 根据是否有 runtime 字段选择模板
- 替换模板中的变量
- 添加 depends（如果提供）
- 添加 buildext.apt.depends（如果提供）
- 写入目标文件

**参数**：
- `origin_yaml`: 原始 yaml 文件路径
- `target_yaml`: 目标 yaml 文件路径
- `depends`: 运行时依赖列表（可选）
- `buildext_depends`: 构建时依赖列表（可选）

**返回值**：是否成功

##### `ensure_fresh_files_dir(target_dir: Optional[Path] = None) -> bool`
确保使用最新的 files 目录（删除现有目录并重新解压）。

**功能**：
- 删除现有的 files 目录
- 从 files.tar.zst 重新解压

**参数**：
- `target_dir`: 目标 files 目录（可选，默认为 build_dir/files）

**返回值**：是否成功

#### 修改方法

##### `scan_non_std_dir_libraries(app_installed_files_dir: Optional[Path] = None)`
**修改内容**：
- 将原来的条件解压逻辑（只在 files 目录不存在时解压）改为调用 `ensure_fresh_files_dir()`
- 确保每次扫描都使用最新的 files 目录

**修改前**：
```python
# 检查 files.tar.zst 并解压
if not app_installed_files_dir.exists() and self.files_tar.exists():
    print(f"Extracting files.tar.zst to {app_installed_files_dir}...")
    self._extract_files_tar(app_installed_files_dir)
```

**修改后**：
```python
# 确保使用最新的 files 目录（删除现有目录并重新解压）
if not self.ensure_fresh_files_dir(app_installed_files_dir):
    return False, []
```

##### `merge_dependencies_to_files(extracted_deps_dir: Path, target_files_dir: Path)`
**修改内容**：
- 在合并依赖前调用 `ensure_fresh_files_dir()` 确保使用最新的 files 目录
- 避免基于过时的 files 目录进行合并

**修改前**：
```python
target_files_dir.mkdir(parents=True, exist_ok=True)
print(f"\nMerging dependencies to {target_files_dir}...")
```

**修改后**：
```python
# 确保使用最新的 files 目录（删除现有目录并重新解压）
if not self.ensure_fresh_files_dir(target_files_dir):
    return False, []

target_files_dir.mkdir(parents=True, exist_ok=True)
print(f"\nMerging dependencies to {target_files_dir}...")
```

### 3. 修改 deb_converter.py

#### 新增方法

##### `_regenerate_yaml_after_fix(mode: int) -> bool`
修复后重新生成 linglong.yaml。

**功能**：
- 根据修复模式确定依赖信息
- 模式0：从 yaml 读取 depends
- 模式1：从 yaml 读取 buildext.apt.depends
- 调用 `_generate_rebuild_yaml()` 生成新的 yaml
- 备份原始 yaml
- 替换原始 yaml

**参数**：
- `mode`: 修复模式（0/1/2）

**返回值**：是否成功

#### 修改方法

##### `_attempt_dependency_fix()`
**修改内容**：
- 在修复尝试前调用 `ensure_fresh_files_dir()` 确保使用最新的 files 目录
- 在修复成功后调用 `_regenerate_yaml_after_fix()` 重新生成 linglong.yaml

**修改前**：
```python
# 根据尝试次数选择模式
mode = (self.fix_attempts - 1) % 3

# 执行依赖分析和修复（只尝试指定的模式）
fix_success, fix_msg = self._analyze_and_fix_dependencies(mode=mode)

if not fix_success:
    print(f"\n✗ Dependency fix failed: {fix_msg}")
    # ...
    return self._attempt_dependency_fix()

# 执行重建（使用标准构建，因为已经添加了依赖）
print("\n" + "=" * 60)
print(f"Phase 5: Rebuild After Fix {self.fix_attempts}")
print("=" * 60)
print("# BUILD_START")
```

**修改后**：
```python
# 确保使用最新的 files 目录（从最新的 files.tar.zst 重新解压）
print("Ensuring fresh files directory from latest files.tar.zst...")
if not self.dependency_fixer.ensure_fresh_files_dir(self.app_build_dir / "files"):
    print("Warning: Failed to ensure fresh files directory, continuing anyway")

# 根据尝试次数选择模式
mode = (self.fix_attempts - 1) % 3

# 执行依赖分析和修复（只尝试指定的模式）
fix_success, fix_msg = self._analyze_and_fix_dependencies(mode=mode)

if not fix_success:
    print(f"\n✗ Dependency fix failed: {fix_msg}")
    # ...
    return self._attempt_dependency_fix()

# 修复成功后，重新生成 linglong.yaml
print("\nRegenerating linglong.yaml after fix...")
yaml_regen_success = self._regenerate_yaml_after_fix(mode)
if not yaml_regen_success:
    print("Warning: Failed to regenerate linglong.yaml, continuing anyway")

# 执行重建（使用标准构建，因为已经添加了依赖）
print("\n" + "=" * 60)
print(f"Phase 5: Rebuild After Fix {self.fix_attempts}")
print("=" * 60)
print("# BUILD_START")
```

## 修改文件清单

### 新增文件
1. `templates/linglong-rebuild.yaml` - 包含 runtime 字段的重建模板
2. `templates/linglong-rebuild-WithoutRuntime.yaml` - 不包含 runtime 字段的重建模板

### 修改文件
1. `scripts/dependency_fixer.py`
   - 添加 `_extract_yaml_info()` 方法
   - 添加 `_generate_rebuild_yaml()` 方法
   - 添加 `ensure_fresh_files_dir()` 方法
   - 修改 `scan_non_std_dir_libraries()` 方法
   - 修改 `merge_dependencies_to_files()` 方法

2. `scripts/deb_converter.py`
   - 添加 `_regenerate_yaml_after_fix()` 方法
   - 修改 `_attempt_dependency_fix()` 方法

## 验证步骤

### 测试场景1：模式2修复后 yaml 重新生成
1. 执行 deb 转换，触发模式2修复
2. 检查修复后是否生成了新的 linglong.yaml
3. 验证新的 yaml 包含正确的软链接信息
4. 检查是否有备份文件 linglong.yaml.backup

### 测试场景2：模式0修复后 yaml 重新生成
1. 执行 deb 转换，触发模式0修复
2. 检查修复后是否生成了新的 linglong.yaml
3. 验证新的 yaml 包含正确的 depends 字段
4. 检查 depends 是否包含所有添加的依赖

### 测试场景3：模式1修复后 yaml 重新生成
1. 执行 deb 转换，触发模式1修复
2. 检查修复后是否生成了新的 linglong.yaml
3. 验证新的 yaml 包含正确的 buildext.apt.depends 字段
4. 检查 buildext.apt.depends 是否包含所有添加的依赖

### 测试场景4：多次修复后 yaml 版本
1. 执行 deb 转换，触发多次修复
2. 检查每次修复后 yaml 是否被更新
3. 验证最终的 yaml 包含所有修复的依赖信息
4. 检查 files 目录是否每次都从最新的 files.tar.zst 重新解压

### 测试场景5：文件丢失场景
1. 模拟 `files` 目录中文件丢失的情况
2. 执行修复
3. 验证是否从 `files.tar.zst` 恢复了丢失的文件
4. 检查修复后的 files 目录内容是否完整

## 预期效果

### 问题1的预期效果
- ✅ 每次修复尝试前都会删除现有的 `files` 目录
- ✅ 从最新的 `files.tar.zst` 重新解压 `files` 目录
- ✅ 确保每次修复都基于最新的文件状态
- ✅ 避免因 `files` 目录过时导致的修复失败
- ✅ 提高修复流程的可靠性和一致性

### 问题2的预期效果
- ✅ 每次修复后都会生成新的 linglong.yaml
- ✅ 新的 yaml 基于模板生成，结构清晰一致
- ✅ 新的 yaml 包含最新的依赖信息（depends, buildext.apt.depends）
- ✅ 修复后的 yaml 与 pica-helper 生成的 yaml 一致
- ✅ 提高修复流程的可靠性和一致性
- ✅ 解决多次构建中 yaml 版本不一致的问题

## 风险评估

### 问题1的风险
- **低风险**：修改主要是确保每次修复都使用最新的文件状态，不会改变修复逻辑本身
- **性能影响**：每次修复前需要重新解压 `files.tar.zst`，会增加少量时间，但这是必要的代价
- **兼容性**：修改向后兼容，不会影响现有功能

### 问题2的风险
- **中等风险**：需要创建新的模板文件，确保模板结构与 pica-helper 一致
- **兼容性**：修改向后兼容，不会影响现有功能
- **性能影响**：每次修复后需要重新生成 yaml，会增加少量时间，但这是必要的代价

## 与 pica-helper 的对比

### 相同点
1. 使用模板文件生成新的 yaml
2. 根据是否有 runtime 字段选择不同的模板
3. 每次修复后都重新生成 yaml
4. 每次修复前都从最新的 files.tar.zst 重新解压 files 目录

### 不同点
1. pica-helper 使用 bash 和 envsubst，linyaps-packager-skill 使用 Python 和 yaml 库
2. pica-helper 的模板使用 `${variable}` 语法，linyaps-packager-skill 使用字符串替换
3. pica-helper 的变量提取使用 grep 和 awk，linyaps-packager-skill 使用 yaml 库

## 总结

本次实现解决了两个关键问题：

1. **files 目录未从最新的 files.tar.zst 重新解压**：通过添加 `ensure_fresh_files_dir()` 方法，确保每次修复前都从最新的 files.tar.zst 重新解压 files 目录，避免使用过时的文件内容。

2. **修复后未重新生成 linglong.yaml**：通过添加模板文件和 yaml 重新生成方法，确保每次修复后都生成新的 linglong.yaml，与 pica-helper 的设计保持一致。

这些修改提高了依赖修复流程的可靠性和一致性，解决了多次构建中文件和 yaml 版本不一致的问题。

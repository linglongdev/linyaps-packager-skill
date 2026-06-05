# Deb 包转换器 Skill 设置同步总结

## 修改日期
2026年4月2日

## 修改目的
同步 SKILL.md 文档设置，确保调用此技能转换 deb 包时可以按预期流程处理。

## 修改内容

### 1. SKILL.md 主要修改

#### 1.1 更新参数名称
- 将 `--enable-compat-check` 改为 `--enable-compact-check`
- 将 `--no-compat-check` 改为 `--no-compact-check`
- 将 `--compat-check-timeout` 改为 `--compact-check-timeout`
- 移除 `--max-fix-attempts` 参数（代码中硬编码为3次）
- 新增 `--enable-layer-export` 参数
- 新增 `--no-layer-export` 参数
- 新增 `--final-missing-csv` 参数
- 新增 `--ll-stored-pool` 参数
- 新增 `--verbose` 参数

#### 1.2 更新工作流程图
- 添加了完整的 Deb 包转换 7 阶段流程图
- 明确了每个阶段的执行顺序和条件判断
- 区分了 Deb 包转换和源码项目构建的不同流程

#### 1.3 更新命令示例
- 添加了 Deb 包转换的详细命令示例
- 展示了各种参数的使用场景
- 保留了源码项目构建的命令示例

#### 1.4 更新输出文件说明
- 添加了 Deb 包转换的输出文件列表
- 说明了 Layer 文件的存储位置规则
- 区分了兼容性测试通过和失败时的存储位置

#### 1.5 更新注意事项
- 添加了 Deb 包转换的专门注意事项
- 说明了 Deb 包转换使用内置脚本而非直接调用 ll-pica
- 说明了 Layer 存储规则

#### 1.6 更新前置要求
- 添加了 Deb 包转换的前置要求
- 说明了需要安装的工具和 Python 依赖

#### 1.7 更新目录约定
- 添加了 `scripts/deb_converter.py` 到目录约定
- 添加了 `references/compatibility-check-workflow.md` 到目录约定

### 2. references/pica-convert-workflow.md 主要修改

#### 2.1 更新封装命令说明
- 明确说明 Deb 包转换使用内置的 `deb_converter.py`
- AppImage 和 Flatpak 仍使用 `ll-pica` 的对应子命令

#### 2.2 添加 Deb 包转换详细说明
- 添加了完整的 7 阶段转换流程图
- 添加了详细的使用示例
- 添加了 Deb 转换选项表格
- 添加了输出文件说明
- 添加了 Layer 存储位置说明

#### 2.3 更新失败排查顺序
- 添加了 Deb 包转换的专门排查步骤
- 添加了 apt-file 和 Python 依赖的检查步骤

### 3. references/compatibility-check-workflow.md 主要修改

#### 3.1 更新配置参数表格
- 添加了 `--enable-layer-export` 参数
- 添加了 `--no-layer-export` 参数
- 添加了 `--final-missing-csv` 参数
- 添加了 `--ll-stored-pool` 参数
- 添加了 `--verbose` 参数
- 添加了关于最大修复尝试次数的说明

### 4. 文件清理

- 删除了重复的 `references/compat-check-workflow.md` 文件
- 保留 `references/compatibility-check-workflow.md` 作为唯一文档

## Deb 包转换完整流程

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

## 核心功能模块

### 1. DebConverter (scripts/deb_converter.py)
- 封装完整的 deb 包转换流程
- 集成兼容性测试、依赖分析和修复功能
- 支持 layer 导出和存储

### 2. CompatChecker (scripts/compat_checker.py)
- 执行运行时测试
- 检测应用是否能正常启动
- 记录测试状态和错误日志

### 3. DependencyAnalyzer (scripts/dependency_analyzer.py)
- 分析缺失的动态库依赖
- 使用 apt-file 查找包含缺失库的包
- 匹配缺失库到对应的 Debian 包

### 4. DependencyFixer (scripts/dependency_fixer.py)
- 扫描非标准目录中的库
- 为库创建软链接到标准位置
- 下载并安装缺失的依赖包
- 合并依赖到应用文件目录
- 管理 files.tar.zst 归档

## 使用示例

### 基本转换
```bash
bash scripts/convert_package.sh deb ./demo.deb --workdir /tmp/pica-work
```

### 启用兼容性测试和 layer 导出
```bash
bash scripts/convert_package.sh deb ./demo.deb \
  --workdir /tmp/pica-work \
  --enable-compact-check \
  --enable-layer-export
```

### 使用 final-missing CSV 文件更新包信息
```bash
bash scripts/convert_package.sh deb ./demo.deb \
  --workdir /tmp/pica-work \
  --final-missing-csv /path/to/final-missing.csv \
  --ll-stored-pool /path/to/StoredPool
```

### 禁用兼容性测试
```bash
bash scripts/convert_package.sh deb ./demo.deb \
  --workdir /tmp/pica-work \
  --no-compact-check
```

### 自定义兼容性测试超时时间
```bash
bash scripts/convert_package.sh deb ./demo.deb \
  --workdir /tmp/pica-work \
  --compact-check-timeout 60
```

## 验证结果

- ✅ SKILL.md 参数名称与实际 Python 脚本一致
- ✅ 工作流程图准确反映了实际执行流程
- ✅ 命令示例完整且可执行
- ✅ 输出文件说明准确
- ✅ 前置要求完整
- ✅ convert_package.sh 帮助信息正确显示
- ✅ 删除了重复的文档文件

## 注意事项

1. Deb 包转换使用内置的 `deb_converter.py` 脚本，不直接调用 `ll-pica deb convert`
2. 转换流程包含完整的兼容性测试和依赖修复功能
3. 支持通过 `--final-missing-csv` 参数更新包的 ID 和名称
4. Layer 文件会根据兼容性测试结果存储到不同目录
5. AppImage 和 Flatpak 转换仍使用 `ll-pica` 的对应子命令
6. 最大修复尝试次数（3次）在代码中硬编码，不可通过命令行参数配置

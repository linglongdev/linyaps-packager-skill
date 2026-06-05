# Changelog

本文档记录 linyaps-packager-skill 的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 计划中
- 添加依赖修复模式0：向 `linglong.yaml` 的 `depends` 字段追加运行时依赖
- 实现完整的3模式依赖修复流程（模式2 → 模式0 → 模式1）
  - 模式2（最轻量）：扫描非标准目录中的库，创建软链接 - 不增加体积，提高运行库复用率
  - 模式0（中等）：向 `linglong.yaml` 的 `depends` 字段追加运行时依赖 - 不增加体积，但依赖运行时环境
  - 模式1（最重）：下载并安装依赖包，更新 `buildext.apt.depends` - 增加包体积，但确保依赖可用

## [2.0.0] - 2026-04-01

### 新增
- 完整的 deb 包转换流程，使用内置 Python 模块 `deb_converter.py`
- 兼容性测试功能（`compat_checker.py`）
- 依赖分析功能（`dependency_analyzer.py`）
- 依赖修复功能（`dependency_fixer.py`）
- Layer 导出和存储功能
- 输出级别控制（normal/quiet/verbose）
- final-missing CSV 文件支持，用于更新包信息

### 变更
- 移除对外部 `linyaps-pica-helper.sh` 脚本的依赖
- 使用内置 Python 模块替代外部脚本
- 优化 deb 转换流程，分离构建和测试阶段
- 改进错误处理和日志记录

### 修复
- 修复兼容性测试超时处理（退出码 124 视为通过）
- 修复依赖修复后的重建逻辑

### 移除
- 移除 `--build` 参数（deb 转换自动执行构建）

## [1.0.0] - 2026-04-01

### 新增
- 初始版本，使用 `linyaps-pica-helper.sh` 进行 deb 转换
- 源码项目打包功能（`build_from_project.py`）
- AppImage 和 Flatpak 转换功能
- 基础的 linglong.yaml 生成功能

---

## 版本说明

### [Unreleased]
正在开发中的版本，包含计划中的功能和变更。

### [2.0.0] - 2026-04-01
将 linyaps-pica-helper 功能迁移到内置 Python 模块，实现完全自包含的 deb 转换流程。

### [1.0.0] - 2026-04-01
初始版本，依赖外部 linyaps-pica-helper.sh 脚本。

---

## 变更类型

- **新增** - 新功能
- **变更** - 现有功能的变更
- **弃用** - 即将移除的功能
- **移除** - 已移除的功能
- **修复** - Bug 修复
- **安全** - 安全相关的修复

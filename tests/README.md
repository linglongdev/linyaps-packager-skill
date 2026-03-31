# 测试说明

## 运行测试

### 运行单元测试

```bash
cd linyaps-packager-skill/tests
python3 test_compat_check_modules.py
```

### 运行原始测试

```bash
cd linyaps-packager-skill/tests
python3 test_build_from_project.py
```

## 测试覆盖

### test_compat_check_modules.py

测试 compat-check（兼容性测试）和依赖修复模块：

- `TestCompatChecker` - 测试兼容性测试器
  - 测试初始化
  - 测试禁用兼容性测试
  - 测试构建目录不存在的情况

- `TestDependencyAnalyzer` - 测试依赖分析器
  - 测试初始化
  - 测试 ELF 标签检测
  - 测试解析 missing_deps.csv
  - 测试保存和加载匹配的包

- `TestDependencyFixer` - 测试依赖修复器
  - 测试初始化
  - 测试库文件名匹配
  - 测试解析 missing_deps.csv
  - 测试在非标准目录中查找库
  - 测试过滤标准目录

- `TestBuildFlowController` - 测试构建流程控制器
  - 测试初始化
  - 测试状态获取方法
  - 测试与各模块的集成

### test_build_from_project.py

原始的构建脚本测试。

## 测试要求

运行测试需要：

1. Python 3.6+
2. 以下 Python 包：
   - `pyyaml`
   - `zstandard`（可选）

安装依赖：

```bash
pip install pyyaml
pip install zstandard  # 可选
```

## 添加新测试

添加新测试时，遵循以下步骤：

1. 在对应的测试类中添加测试方法
2. 方法名以 `test_` 开头
3. 使用 `assert` 语句验证结果
4. 使用 `setUp()` 和 `tearDown()` 管理测试环境

示例：

```python
def test_new_feature(self):
    """测试新功能"""
    # 准备测试数据
    test_data = ...
    
    # 执行测试
    result = ...
    
    # 验证结果
    self.assertEqual(result, expected)
    self.assertTrue(condition)
```

## 测试覆盖率

当前的测试覆盖：

- ✓ CompactChecker 基本功能
- ✓ DependencyAnalyzer 基本功能
- ✓ DependencyFixer 基本功能
- ✓ BuildFlowController 基本功能
- ✗ 端到端集成测试（需要实际环境）
- ✗ 性能测试
- ✗ 错误恢复测试

## 贡献指南

欢迎添加更多测试用例！在提交测试时，请确保：

1. 所有现有测试通过
2. 新测试覆盖了新增功能
3. 测试名称清晰描述测试内容
4. 添加必要的注释和文档

## 故障排查

### 导入错误

如果看到导入错误，请确保：

1. 在 `linyaps-packager-skill` 目录下运行测试
2. 所有模块文件存在于 `scripts/` 目录
3. Python 版本 >= 3.6

### 依赖缺失

如果看到依赖缺失错误，请安装：

```bash
pip install pyyaml
```

### 权限错误

如果看到权限错误，请确保：

1. 对工作目录有读写权限
2. 对测试目录有创建临时文件的权限

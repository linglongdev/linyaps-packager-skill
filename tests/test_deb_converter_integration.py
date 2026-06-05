#!/usr/bin/env python3
"""
Deb 包转换器集成测试
测试 deb_converter.py 的基本功能和参数解析
"""
import sys
import subprocess
from pathlib import Path


def test_help():
    """测试帮助信息"""
    print("Testing deb_converter.py help...")
    result = subprocess.run(
        ["python3", "scripts/deb_converter.py", "--help"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✓ Help command successful")
        print("\nHelp output:")
        print(result.stdout)
        
        # 检查关键参数是否存在
        required_params = [
            "--enable-compact-check",
            "--no-compact-check",
            "--compact-check-timeout",
            "--enable-layer-export",
            "--no-layer-export",
            "--final-missing-csv",
            "--ll-stored-pool",
            "--verbose"
        ]
        
        missing_params = []
        for param in required_params:
            if param not in result.stdout:
                missing_params.append(param)
        
        if missing_params:
            print(f"\n✗ Missing parameters: {', '.join(missing_params)}")
            return False
        else:
            print("\n✓ All required parameters present")
            return True
    else:
        print(f"✗ Help command failed with exit code {result.returncode}")
        print(f"Error: {result.stderr}")
        return False


def test_module_imports():
    """测试模块导入"""
    print("\nTesting module imports...")
    
    # 添加 scripts 目录到 Python 路径
    import sys
    scripts_dir = Path(__file__).parent.parent / "scripts"
    sys.path.insert(0, str(scripts_dir))
    
    modules = [
        "compat_checker",
        "dependency_analyzer",
        "dependency_fixer",
        "deb_converter"
    ]
    
    all_success = True
    for module in modules:
        try:
            __import__(module)
            print(f"✓ {module} imported successfully")
        except ImportError as e:
            print(f"✗ Failed to import {module}: {e}")
            all_success = False
    
    return all_success


def test_convert_package_script():
    """测试 convert_package.sh 脚本"""
    print("\nTesting convert_package.sh script...")
    
    result = subprocess.run(
        ["bash", "scripts/convert_package.sh", "-h"],
        capture_output=True,
        text=True
    )
    
    # 脚本使用 -h 参数时返回退出码 0，使用 --help 时返回退出码 1
    # 但两种方式都会显示帮助信息
    if result.returncode in [0, 1] and "Usage:" in result.stdout:
        print("✓ convert_package.sh help successful")
        
        # 检查关键选项是否存在
        required_options = [
            "--enable-compact-check",
            "--no-compact-check",
            "--compact-check-timeout",
            "--enable-layer-export",
            "--no-layer-export",
            "--final-missing-csv",
            "--ll-stored-pool",
            "--verbose"
        ]
        
        missing_options = []
        for option in required_options:
            if option not in result.stdout:
                missing_options.append(option)
        
        if missing_options:
            print(f"\n✗ Missing options: {', '.join(missing_options)}")
            return False
        else:
            print("\n✓ All required options present")
            return True
    else:
        print(f"✗ convert_package.sh help failed with exit code {result.returncode}")
        print(f"Error: {result.stderr}")
        return False


def test_documentation_consistency():
    """测试文档一致性"""
    print("\nTesting documentation consistency...")
    
    # 检查 SKILL.md
    skill_md = Path("SKILL.md")
    if not skill_md.exists():
        print("✗ SKILL.md not found")
        return False
    
    skill_content = skill_md.read_text(encoding="utf-8")
    
    # 检查关键参数是否在文档中
    required_params = [
        "--enable-compact-check",
        "--no-compact-check",
        "--compact-check-timeout",
        "--enable-layer-export",
        "--no-layer-export",
        "--final-missing-csv",
        "--ll-stored-pool"
    ]
    
    missing_params = []
    for param in required_params:
        if param not in skill_content:
            missing_params.append(param)
    
    if missing_params:
        print(f"✗ SKILL.md missing parameters: {', '.join(missing_params)}")
        return False
    else:
        print("✓ SKILL.md contains all required parameters")
    
    # 检查 references/pica-convert-workflow.md
    pica_workflow = Path("references/pica-convert-workflow.md")
    if not pica_workflow.exists():
        print("✗ references/pica-convert-workflow.md not found")
        return False
    
    pica_content = pica_workflow.read_text(encoding="utf-8")
    
    # 检查关键内容
    required_content = [
        "deb_converter.py",
        "Phase 1: ll-pica convert",
        "Phase 2: 初始构建",
        "Phase 3: 兼容性测试",
        "Phase 4: 依赖修复尝试",
        "Phase 5: 重建",
        "Phase 6: 兼容性测试",
        "Phase 7: 导出 Layer"
    ]
    
    missing_content = []
    for content in required_content:
        if content not in pica_content:
            missing_content.append(content)
    
    if missing_content:
        print(f"✗ pica-convert-workflow.md missing content: {', '.join(missing_content)}")
        return False
    else:
        print("✓ pica-convert-workflow.md contains all required content")
    
    return True


def main():
    """主测试函数"""
    print("=" * 60)
    print("Deb 包转换器集成测试")
    print("=" * 60)
    
    tests = [
        ("Help Information", test_help),
        ("Module Imports", test_module_imports),
        ("Convert Package Script", test_convert_package_script),
        ("Documentation Consistency", test_documentation_consistency)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'=' * 60}")
        print(f"Test: {test_name}")
        print(f"{'=' * 60}")
        success = test_func()
        results.append((test_name, success))
    
    # 打印总结
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    all_passed = True
    for test_name, success in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        print(f"{test_name}: {status}")
        if not success:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())

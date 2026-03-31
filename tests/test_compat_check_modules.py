#!/usr/bin/env python3
"""
测试脚本 - 验证 compat-check 和依赖修复模块
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 添加 scripts 目录到路径
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

try:
    from compat_checker import CompatChecker
    from dependency_analyzer import DependencyAnalyzer
    from dependency_fixer import DependencyFixer
    from build_flow_controller import BuildFlowController
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保所有模块文件存在")
    sys.exit(1)


class TestCompatChecker(unittest.TestCase):
    """测试 CompatChecker 模块"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """清理测试环境"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_init(self):
        """测试初始化"""
        checker = CompatChecker(self.temp_dir, enable_compat_check=True)
        self.assertEqual(checker.build_dir, self.temp_dir)
        self.assertTrue(checker.enable_compat_check)
        self.assertEqual(checker.compat_checking_status, "N/A")

    def test_disabled_check(self):
        """测试禁用兼容性测试"""
        checker = CompatChecker(self.temp_dir, enable_compat_check=False)
        success, msg = checker.check()
        self.assertTrue(success)
        self.assertEqual(checker.compat_checking_status, "N/A")
    
    def test_build_dir_not_exists(self):
        """测试构建目录不存在的情况"""
        non_existent_dir = self.temp_dir / "non-existent"
        checker = CompatChecker(non_existent_dir, enable_compat_check=True)
        success, msg = checker.check()
        self.assertFalse(success)
        self.assertEqual(checker.compat_checking_status, "failed")


class TestDependencyAnalyzer(unittest.TestCase):
    """测试 DependencyAnalyzer 模块"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = Path(tempfile.mkdtemp())
        
    def tearDown(self):
        """清理测试环境"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_init(self):
        """测试初始化"""
        analyzer = DependencyAnalyzer(self.temp_dir, verbose=False)
        self.assertEqual(analyzer.build_dir, self.temp_dir)
        self.assertFalse(analyzer.verbose)
        self.assertIsInstance(analyzer.matched_packages, list)
    
    def test_detect_elf_tag(self):
        """测试 ELF 标签检测"""
        analyzer = DependencyAnalyzer(self.temp_dir, verbose=True)
        elf_tag = analyzer._detect_elf_tag()
        self.assertIsNotNone(elf_tag)
        self.assertTrue(isinstance(elf_tag, str))
        self.assertIn("-linux-gnu", elf_tag)
        
    def test_parse_missing_deps_csv(self):
        """测试解析 missing_deps.csv"""
        analyzer = DependencyAnalyzer(self.temp_dir, verbose=False)
        
        # 创建测试 CSV 文件
        csv_file = self.temp_dir / "missing_deps.csv"
        csv_file.write_text(
            "library_name,file_path\n"
            "libc.so.6,/usr/lib/x86_64-linux-gnu/libc.so.6\n"
            "libssl.so.1.1,/usr/lib/x86_64-linux-gnu/libssl.so.1.1\n",
            encoding="utf-8"
        )
        
        missing_libs = analyzer._parse_missing_deps_csv(csv_file)
        self.assertEqual(len(missing_libs), 2)
        self.assertIn("libc.so.6", missing_libs)
        self.assertIn("libssl.so.1.1", missing_libs)
    
    def test_parse_empty_csv(self):
        """测试解析空 CSV 文件"""
        analyzer = DependencyAnalyzer(self.temp_dir, verbose=False)
        
        csv_file = self.temp_dir / "empty.csv"
        csv_file.write_text("", encoding="utf-8")
        
        missing_libs = analyzer._parse_missing_deps_csv(csv_file)
        self.assertEqual(len(missing_libs), 0)
    
    def test_save_and_load_matched_packages(self):
        """测试保存和加载匹配的包"""
        analyzer = DependencyAnalyzer(self.temp_dir, verbose=False)
        
        # 设置测试包列表
        analyzer.matched_packages = ["package1", "package2", "package3"]
        
        # 保存
        output_file = self.temp_dir / "packages.txt"
        success = analyzer.save_matched_packages(output_file)
        self.assertTrue(success)
        self.assertTrue(output_file.exists())
        
        # 加载
        loaded_packages = analyzer.load_matched_packages(output_file)
        self.assertEqual(len(loaded_packages), 3)
        self.assertIn("package1", loaded_packages)
        self.assertIn("package2", loaded_packages)
        self.assertIn("package3", loaded_packages)


class TestDependencyFixer(unittest.TestCase):
    """测试 DependencyFixer 模块"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = Path(tempfile.mkdtemp())
        
    def tearDown(self):
        """清理测试环境"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_init(self):
        """测试初始化"""
        fixer = DependencyFixer(self.temp_dir, verbose=False)
        self.assertEqual(fixer.build_dir, self.temp_dir)
        self.assertFalse(fixer.verbose)
    
    def test_library_matches(self):
        """测试库文件名匹配"""
        fixer = DependencyFixer(self.temp_dir, verbose=False)
        
        # 精确匹配
        self.assertTrue(fixer._library_matches("libc.so.6", "libc.so.6"))
        
        # 通配符匹配
        self.assertTrue(fixer._library_matches("libcdio.so.19", "libcdio.so.19.0.0"))
        self.assertTrue(fixer._library_matches("libssl.so.1.1", "libssl.so.1.1.0"))
        
        # 不匹配
        self.assertFalse(fixer._library_matches("libc.so.6", "libssl.so.1.1"))
        self.assertFalse(fixer._library_matches("libcdio.so.19", "libcdio.so.20"))
    
    def test_parse_missing_deps_csv(self):
        """测试解析 missing_deps.csv"""
        fixer = DependencyFixer(self.temp_dir, verbose=False)
        
        # 创建测试 CSV 文件
        csv_file = self.temp_dir / "missing_deps.csv"
        csv_file.write_text(
            "library_name,file_path\n"
            "libc.so.6,/path/to/libc.so.6\n"
            "libssl.so.1.1,/path/to/libssl.so.1.1\n"
            "non-so-file.txt,/path/to/file.txt\n",
            encoding="utf-8"
        )
        
        missing_libs = fixer._parse_missing_deps_csv(csv_file)
        # 只应该包含 .so 文件
        self.assertEqual(len(missing_libs), 2)
        self.assertIn("libc.so.6", missing_libs)
        self.assertIn("libssl.so.1.1", missing_libs)
        self.assertNotIn("non-so-file.txt", missing_libs)

    def test_find_library_in_non_std_dir(self):
        """测试在非标准目录中查找库"""
        fixer = DependencyFixer(self.temp_dir, verbose=False)
        
        # 创建测试文件结构
        third_party_dir = self.temp_dir / "files" / "third-party"
        third_party_dir.mkdir(parents=True)
        
        # 创建测试库文件
        test_lib = third_party_dir / "libtest.so.1"
        test_lib.write_text("fake library content", encoding="utf-8")
        
        # 查找库
        found_paths = fixer._find_library_in_non_std_dir(
            self.temp_dir / "files",
            "libtest.so.1"
        )
        
        self.assertEqual(len(found_paths), 1)
        self.assertEqual(found_paths[0], test_lib)
    
    def test_find_library_in_std_dir(self):
        """测试在标准目录中查找库（应该被过滤）"""
        fixer = DependencyFixer(self.temp_dir, verbose=False)
        
        # 创建标准库目录
        std_lib_dir = self.temp_dir / "files" / "lib"
        std_lib_dir.mkdir(parents=True)
        
        # 创建测试库文件
        test_lib = std_lib_dir / "libtest.so.1"
        test_lib.write_text("fake library content", encoding="utf-8")
        
        # 查找库（应该返回空，因为是标准目录）
        found_paths = fixer._find_library_in_non_std_dir(
            self.temp_dir / "files",
            "libtest.so.1"
        )
        
        self.assertEqual(len(found_paths), 0)


class TestBuildFlowController(unittest.TestCase):
    """测试 BuildFlowController 模块"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = Path(tempfile.mkdtemp())
        
    def tearDown(self):
        """清理测试环境"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_init(self):
        """测试初始化"""
        controller = BuildFlowController(
            build_dir=self.temp_dir,
            enable_compat_check=True,
            compat_check_timeout=30,
            verbose=False
        )
        
        self.assertEqual(controller.build_dir, self.temp_dir)
        self.assertTrue(controller.enable_compat_check)
        self.assertEqual(controller.compat_check_timeout, 30)
        self.assertEqual(controller.build_status, "not-started")
        self.assertEqual(controller.compat_check_status, "N/A")
        self.assertEqual(controller.fix_attempts, 0)
    
    def test_get_status_methods(self):
        """测试状态获取方法"""
        controller = BuildFlowController(self.temp_dir)
        
        self.assertEqual(controller.get_build_status(), "not-started")
        self.assertEqual(controller.get_compat_check_status(), "N/A")
        self.assertEqual(controller.get_fix_attempts(), 0)
    
    def test_compat_checker_integration(self):
        """测试与 CompatChecker 的集成"""
        controller = BuildFlowController(
            build_dir=self.temp_dir,
            enable_compat_check=True,
            verbose=False
        )
        
        self.assertIsNotNone(controller.compat_checker)
        self.assertIsInstance(controller.compat_checker, CompatChecker)
    
    def test_dependency_analyzer_integration(self):
        """测试与 DependencyAnalyzer 的集成"""
        controller = BuildFlowController(self.temp_dir, verbose=False)
        
        self.assertIsNotNone(controller.dependency_analyzer)
        self.assertIsInstance(controller.dependency_analyzer, DependencyAnalyzer)
    
    def test_dependency_fixer_integration(self):
        """测试与 DependencyFixer 的集成"""
        controller = BuildFlowController(self.temp_dir, verbose=False)
        
        self.assertIsNotNone(controller.dependency_fixer)
        self.assertIsInstance(controller.dependency_fixer, DependencyFixer)
    
    def test_disabled_compat_check(self):
        """测试禁用兼容性测试"""
        controller = BuildFlowController(
            build_dir=self.temp_dir,
            enable_compat_check=False,
            verbose=False
        )
        
        self.assertFalse(controller.enable_compat_check)
        self.assertFalse(controller.compat_checker.enable_compat_check)


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加所有测试类
    suite.addTests(loader.loadTestsFromTestCase(TestCompatChecker))
    suite.addTests(loader.loadTestsFromTestCase(TestDependencyAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(TestDependencyFixer))
    suite.addTests(loader.loadTestsFromTestCase(TestBuildFlowController))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出摘要
    print("\n" + "=" * 60)
    print("测试摘要")
    print("=" * 60)
    print(f"运行测试: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print("=" * 60)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("开始测试 compact-check 和依赖修复模块...")
    success = run_tests()
    sys.exit(0 if success else 1)

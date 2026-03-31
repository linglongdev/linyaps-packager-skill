#!/usr/bin/env python3
"""
构建流程控制器 - 整合 compact-check、依赖分析和修复流程
基于 linyaps-pica-helper 的完整构建流程
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from compact_checker import CompatChecker
from dependency_analyzer import DependencyAnalyzer
from dependency_fixer import DependencyFixer


class BuildFlowController:
    """构建流程控制器"""
    
    def __init__(
        self,
        build_dir: Path,
        enable_compat_check: bool = True,
        compat_check_timeout: int = 30,
        verbose: bool = False
    ):
        """
        初始化构建流程控制器
        
        Args:
            build_dir: 构建目录
            enable_compat_check: 是否启用兼容性测试
            compat_check_timeout: 兼容性测试超时时间（秒）
            verbose: 是否显示详细输出
        """
        self.build_dir = Path(build_dir).resolve()
        self.enable_compat_check = enable_compat_check
        self.compat_check_timeout = compat_check_timeout
        self.verbose = verbose
        
        # 状态跟踪
        self.build_status = "not-started"
        self.compat_check_status = "N/A"
        self.fix_attempts = 0
        self.max_fix_attempts = 3
        
        # 初始化子模块
        self.compat_checker = CompatChecker(
            build_dir,
            enable_compat_check,
            compat_check_timeout
        )
        
        self.dependency_analyzer = DependencyAnalyzer(build_dir, verbose)
        self.dependency_fixer = DependencyFixer(build_dir, verbose)
        
    def build_with_compat_check_and_auto_fix(
        self,
        skip_output_check: bool = False
    ) -> Tuple[bool, str]:
        """
        执行构建、兼容性测试和自动修复
        
        Args:
            skip_output_check: 是否跳过输出检查
            
        Returns:
            (成功状态, 状态描述)
        """
        print("\n" + "=" * 60)
        print("Phase 1: Initial Build")
        print("=" * 60)
        
        # 执行初始构建
        build_success, build_msg = self._execute_build(skip_output_check)
        
        if not build_success:
            print(f"\n✗ Initial build failed: {build_msg}")
            return False, build_msg
        
        print(f"\n✓ Build successful")
        
        # 如果启用兼容性测试，执行兼容性测试
        if self.enable_compat_check:
            print("\n" + "=" * 60)
            print("Phase 2: Compat Check")
            print("=" * 60)
            
            check_success, check_msg = self.compat_checker.check()
            self.compat_check_status = self.compat_checker.get_status()
            
            if check_success:
                print(f"\n✓ Compat check passed: {check_msg}")
                return True, "Build and compat check passed"
            else:
                print(f"\n✗ Compat check failed: {check_msg}")
                return self._attempt_dependency_fix()
        else:
            print("\nCompat check disabled, skipping")
            return True, "Build successful (compat check disabled)"
    
    def _attempt_dependency_fix(self) -> Tuple[bool, str]:
        """
        尝试依赖修复
        
        Returns:
            (成功状态, 状态描述)
        """
        self.fix_attempts += 1
        print("\n" + "=" * 60)
        print(f"Phase 3: Dependency Fix Attempt {self.fix_attempts}")
        print("=" * 60)
        
        # 检查超过最大尝试次数
        if self.fix_attempts > self.max_fix_attempts:
            print(f"\n✗ Exceeded maximum fix attempts ({self.max_fix_attempts})")
            return False, "Exceeded maximum fix attempts"
        
        # 执行依赖分析和修复
        fix_success, fix_msg = self._analyze_and_fix_dependencies()
        
        if not fix_success:
            print(f"\n✗ Dependency fix failed: {fix_msg}")
            return self._attempt_final_build()
        
        # 执行重建
        print("\n" + "=" * 60)
        print(f"Phase 4: Rebuild After Fix {self.fix_attempts}")
        print("=" * 60)
        
        rebuild_success, rebuild_msg = self._execute_build(skip_output_check=False)
        
        if not rebuild_success:
            print(f"\n✗ Rebuild failed: {rebuild_msg}")
            return self._attempt_final_build()
        
        # 再次执行兼容性测试
        if self.enable_compat_check:
            print("\n" + "=" * 60)
            print(f"Phase 5: Compat Check After Fix {self.fix_attempts}")
            print("=" * 60)
            
            check_success, check_msg = self.compat_checker.check()
            self.compat_check_status = self.compat_checker.get_status()
            
            if check_success:
                print(f"\n✓ Compat check passed after fix: {check_msg}")
                return True, f"Build and compat check passed after {self.fix_attempts} fix attempt(s)"
            else:
                print(f"\n✗ Compat check still failed: {check_msg}")
                # 尝试下一轮修复
                return self._attempt_dependency_fix()
        else:
            print("\nCompat check disabled, skipping")
            return True, f"Rebuild successful after {self.fix_attempts} fix attempt(s)"
    
    def _attempt_final_build(self) -> Tuple[bool, str]:
        """
        执行最终构建（无输出检查）
        
        Returns:
            (成功状态, 状态描述)
        """
        print("\n" + "=" * 60)
        print("Phase 6: Final Build Without Test")
        print("=" * 60)
        
        # 执行无测试的最终构建
        build_success, build_msg = self._execute_build(skip_output_check=True)
        
        if build_success:
            print(f"\n✓ Final build successful")
            return True, "Final build successful (compat check bypassed)"
        else:
            print(f"\n✗ Final build failed: {build_msg}")
            return False, f"All fix attempts failed. Final error: {build_msg}"
    
    def _execute_build(self, skip_output_check: bool = False) -> Tuple[bool, str]:
        """
        执行构建
        
        Args:
            skip_output_check: 是否跳过输出检查
            
        Returns:
            (成功状态, 状态描述)
        """
        try:
            cmd = ["ll-builder", "build"]
            if skip_output_check:
                cmd.append("--skip-output-check")
            
            print(f"Executing: {' '.join(cmd)}")
            print(f"Working directory: {self.build_dir}")
            
            result = subprocess.run(
                cmd,
                cwd=self.build_dir,
                capture_output=not self.verbose,
                text=True,
                timeout=3600  # 1小时超时
            )
            
            if result.returncode == 0:
                self.build_status = "passed"
                
                # 更新 files.tar.zst 归档
                self._update_files_tar()
                
                return True, "Build successful"
            else:
                self.build_status = "failed"
                
                error_msg = result.stderr or result.stdout or f"exit code {result.returncode}"
                
                # 特殊处理退出码 255（可能是依赖问题）
                if result.returncode == 255:
                    print(f"✗ Build failed with exit code 255 (likely dependency issue)")
                    return False, f"Build failed (exit code 255)"
                else:
                    print(f"✗ Build failed with exit code {result.returncode}")
                    if error_msg.strip():
                        print(f"  Error: {error_msg[:300]}...")
                    return False, f"Build failed (exit code {result.returncode})"
                
        except subprocess.TimeoutExpired:
            self.build_status = "timeout"
            print(f"✗ Build timed out (1 hour)")
            return False, "Build timed out"
        except FileNotFoundError:
            print(f"✗ ll-builder command not found")
            return False, "ll-builder not found"
        except Exception as e:
            self.build_status = "error"
            print(f"✗ Build error: {e}")
            return False, f"Build error: {e}"
    
    def _analyze_and_fix_dependencies(self) -> Tuple[bool, str]:
        """
        分析并修复依赖
        
        Returns:
            (成功状态, 状态描述)
        """
        print("\nAnalyzing missing dependencies...")
        
        # 分析缺失的依赖
        analyze_success, packages = self.dependency_analyzer.analyze_missing_deps(
            force_update_cache=True
        )
        
        if not analyze_success:
            return False, "Dependency analysis failed"
        
        if not packages:
            print("No missing packages found, trying alternative fix methods...")
            # 尝试扫描非标准目录中的库
            return self._fix_non_std_dir_libraries()
        
        print(f"\nFound {len(packages)} missing packages")
        
        # 下载并安装依赖
        download_success, extracted_dir = self.dependency_fixer.download_and_install_dependencies(packages)
        
        if not download_success:
            return False, "Failed to download dependencies"
        
        # 合并依赖到 files 目录
        merge_success, added_files = self.dependency_fixer.merge_dependencies_to_files(
            extracted_dir,
            self.build_dir / "files"
        )
        
        if not merge_success:
            return False, "Failed to merge dependencies"
        
        # 更新 linglong.yaml
        yaml_update_success = self._update_yaml_with_dependencies(packages)
        
        if not yaml_update_success:
            print("Warning: Failed to update linglong.yaml with dependencies")
        
        # 更新 files.tar.zst
        tar_update_success = self.dependency_fixer.create_files_tar()
        
        if not tar_update_success:
            print("Warning: Failed to update files.tar.zst")
        
        return True, f"Fixed {len(packages)} dependencies"
    
    def _fix_non_std_dir_libraries(self) -> Tuple[bool, str]:
        """
        修复非标准目录中的库
        
        Returns:
            (成功状态, 状态描述)
        """
        print("\nScanning for libraries in non-standard directories...")
        
        # 扫描非标准目录中的库
        scan_success, libraries = self.dependency_fixer.scan_non_std_dir_libraries()
        
        if not scan_success:
            return False, "Failed to scan for libraries"
        
        if not libraries:
            return False, "No libraries found in non-standard directories"
        
        print(f"\nFound {len(libraries)} libraries in non-standard directories")
        
        # 创建软链接
        symlink_success, symlinks = self.dependency_fixer.create_symlinks_for_libraries(
            libraries,
            self.build_dir / "files",
            self.build_dir / "files" / "lib"
        )
        
        if not symlink_success:
            return False, "Failed to create symlinks"
        
        # 更新 files.tar.zst
        tar_update_success = self.dependency_fixer.create_files_tar()
        
        if not tar_update_success:
            print("Warning: Failed to update files.tar.zst")
        
        return True, f"Fixed {len(libraries)} libraries with symlinks"
    
    def _update_yaml_with_dependencies(self, packages: list) -> bool:
        """
        更新 linglong.yaml 中的依赖
        
        Args:
            packages: 包列表
            
        Returns:
            是否成功
        """
        yaml_path = self.build_dir / "linglong.yaml"
        
        if not yaml_path.exists():
            print(f"✗ linglong.yaml not found: {yaml_path}")
            return False
        
        try:
            import yaml
            
            with open(yaml_path, "r", encoding="utf-8") as f:
                manifest = yaml.safe_load(f)
            
            # 添加 buildext.apt.depends
            if "buildext" not in manifest:
                manifest["buildext"] = {}
            if "apt" not in manifest["buildext"]:
                manifest["buildext"]["apt"] = {}
            
            # 合并现有的 depends
            existing_depends = manifest["buildext"]["apt"].get("depends", [])
            if isinstance(existing_depends, str):
                existing_depends = [existing_depends]
            
            # 去重并添加新依赖
            all_depends = list(set(existing_depends + packages))
            manifest["buildext"]["apt"]["depends"] = all_depends
            
            # 写回文件
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(manifest, f, default_flow_style=False, allow_unicode=True)
            
            print(f"✓ Updated linglong.yaml with {len(packages)} dependencies")
            return True
        except ImportError:
            print("✗ PyYAML not installed. Install with: pip install pyyaml")
            return False
        except Exception as e:
            print(f"✗ Failed to update linglong.yaml: {e}")
            return False
    
    def _update_files_tar(self) -> bool:
        """
        更新 files.tar.zst 归档
        
        Returns:
            是否成功
        """
        built_files_dir = self.build_dir / "linglong" / "output" / "binary" / "files"
        
        if not built_files_dir.exists() or not any(built_files_dir.iterdir()):
            print("No built files found")
            return False
        
        try:
            print(f"Updating files.tar.zst from {built_files_dir}...")
            tar_update_success = self.dependency_fixer.create_files_tar(built_files_dir)
            return tar_update_success
        except Exception as e:
            print(f"✗ Failed to update files.tar.zst: {e}")
            return False
    
    def get_build_status(self) -> str:
        """获取构建状态"""
        return self.build_status

    def get_compat_check_status(self) -> str:
        """获取兼容性测试状态"""
        return self.compat_check_status

    def get_fix_attempts(self) -> int:
        """获取修复尝试次数"""
        return self.fix_attempts

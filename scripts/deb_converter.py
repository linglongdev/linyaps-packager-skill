#!/usr/bin/env python3
"""
Deb 包转换器 - 基于 linyaps-pica-helper 的核心功能
封装 ll-pica convert、构建、兼容性测试、依赖修复等完整流程
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from compat_checker import CompatChecker
from dependency_analyzer import DependencyAnalyzer
from dependency_fixer import DependencyFixer


class DebConverter:
    """Deb 包转换器 - 完整的转换流程"""
    
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
        quiet: bool = False
    ):
        """
        初始化 Deb 包转换器
        
        Args:
            deb_file: deb 文件路径
            workdir: 工作目录
            enable_compact_check: 是否启用兼容性测试
            compact_check_timeout: 兼容性测试超时时间（秒）
            enable_layer_export: 是否启用 layer 导出
            ll_stored_pool: layer 存储目录
            final_missing_csv: final-missing CSV 文件路径
            verbose: 是否显示详细输出
            quiet: 是否只显示最终结果
        """
        self.deb_file = Path(deb_file).resolve()
        self.workdir = Path(workdir).resolve()
        self.enable_compact_check = enable_compact_check
        self.compact_check_timeout = compact_check_timeout
        self.enable_layer_export = enable_layer_export
        self.ll_stored_pool = Path(ll_stored_pool).resolve() if ll_stored_pool else None
        self.final_missing_csv = Path(final_missing_csv).resolve() if final_missing_csv else None
        self.verbose = verbose
        self.quiet = quiet
        
        # 输出级别：quiet < normal < verbose
        self.output_level = "quiet" if quiet else ("verbose" if verbose else "normal")
        
        # 包信息
        self._deb_id = ""
        self._deb_version = ""
        self._deb_arch = ""
        
        # 先获取包信息
        self._deb_id, self._deb_version, self._deb_arch = self._get_deb_info()
        
        # 派生目录
        self.pica_workdir = self.workdir / "pica-work"
        self.app_build_dir = self.pica_workdir / "package" / self._deb_id
        self.ll_stored_pool = self.ll_stored_pool or (self.workdir / "StoredPool")
        
        # 状态跟踪
        self.build_status = "not-started"
        self.compact_check_status = "N/A"
        self.layer_export_status = "N/A"
        self.fix_attempts = 0
        self.max_fix_attempts = 3
        
        # 初始化子模块
        self.compat_checker = CompatChecker(
            self.app_build_dir,
            enable_compact_check,
            compact_check_timeout,
            verbose
        )
        self.dependency_analyzer = DependencyAnalyzer(self.app_build_dir, verbose)
        self.dependency_fixer = DependencyFixer(self.app_build_dir, verbose)
    
    @property
    def deb_id(self) -> str:
        """获取 deb 包 ID"""
        return self._deb_id
    
    @property
    def deb_version(self) -> str:
        """获取 deb 包版本"""
        return self._deb_version
    
    @property
    def deb_arch(self) -> str:
        """获取 deb 包架构"""
        return self._deb_arch
    
    def _get_deb_info(self) -> Tuple[str, str, str]:
        """
        获取 deb 包信息
        
        Returns:
            (包名, 版本, 架构)
        """
        try:
            # 使用 apt show 获取包信息
            result = subprocess.run(
                ["apt", "show", str(self.deb_file)],
                capture_output=True,
                text=True,
                check=True
            )
            
            deb_id = ""
            deb_version = ""
            
            for line in result.stdout.split('\n'):
                if line.startswith('Package:'):
                    deb_id = line.split(':', 1)[1].strip()
                elif line.startswith('Version:'):
                    deb_version = line.split(':', 1)[1].strip()
            
            # 使用 dpkg -I 获取架构
            result = subprocess.run(
                ["dpkg", "-I", str(self.deb_file)],
                capture_output=True,
                text=True,
                check=True
            )
            
            deb_arch = ""
            for line in result.stdout.split('\n'):
                if line.strip().startswith('Architecture:'):
                    deb_arch = line.split(':', 1)[1].strip()
                    break
            
            return deb_id, deb_version, deb_arch
            
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to get deb info: {e}")
            return "", "", ""
    
    def _check_requirements(self) -> bool:
        """
        检查前置要求
        
        Returns:
            是否满足要求
        """
        # 检查必需的命令
        required_commands = ["ll-pica", "ll-builder", "apt-cache"]
        for cmd in required_commands:
            if not shutil.which(cmd):
                print(f"✗ Required command '{cmd}' not found")
                return False
        
        # 检查 deb 文件是否存在
        if not self.deb_file.exists():
            print(f"✗ Deb file not found: {self.deb_file}")
            return False
        
        return True
    
    def _parse_final_missing_csv(self) -> Tuple[str, str, str, str]:
        """
        解析 final-missing CSV 文件
        
        Returns:
            (origName, origDebID, origDebVer, newID)
        """
        if not self.final_missing_csv or not self.final_missing_csv.exists():
            return "", "", "", ""
        
        try:
            with open(self.final_missing_csv, 'r', encoding='utf-8') as f:
                for line in f:
                    # 跳过表头
                    if line.startswith('DEB应用名称'):
                        continue
                    
                    # 解析 CSV 行
                    parts = line.strip().split('^')
                    if len(parts) >= 4:
                        orig_name, orig_deb_id, orig_deb_ver, new_id = parts[:4]
                        # 匹配 deb_id
                        if orig_deb_id == self.deb_id:
                            return orig_name, orig_deb_id, orig_deb_ver, new_id
            
            return "", "", "", ""
            
        except Exception as e:
            print(f"✗ Failed to parse final-missing CSV: {e}")
            return "", "", "", ""
    
    def _update_yaml_id_and_name(
        self,
        yaml_file: Path,
        new_id: str,
        new_name: str,
        orig_deb_id: str
    ) -> bool:
        """
        更新 linglong.yaml 的 id 和 name 字段
        
        Args:
            yaml_file: yaml 文件路径
            new_id: 新的 ID
            new_name: 新的名称
            orig_deb_id: 原始 deb ID
            
        Returns:
            是否成功
        """
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 更新 id 字段
            if new_id:
                content = re.sub(
                    r'^(\s*)id:\s*\S+',
                    f'\\1id: {new_id}',
                    content,
                    flags=re.MULTILINE
                )
            
            # 更新 name 字段
            if new_name:
                content = re.sub(
                    r'^(\s*)name:\s*\S+',
                    f'\\1name: {new_name}',
                    content,
                    flags=re.MULTILINE
                )
            
            # 更新 command 和 build 中的 deb_id 引用
            if orig_deb_id and new_id:
                # 更新 command 字段
                content = re.sub(
                    r'^(\s*-\s*)' + re.escape(orig_deb_id),
                    f'\\1{new_id}',
                    content,
                    flags=re.MULTILINE
                )
                
                # 更新 build 段中的引用（跳过 EXTERNAL 前缀）
                lines = content.split('\n')
                in_build = False
                build_indent = 0
                
                for i, line in enumerate(lines):
                    # 检测 build 段开始
                    if re.match(r'^\s*build:\s*[|>]', line):
                        in_build = True
                        build_indent = len(line) - len(line.lstrip())
                        continue
                    
                    # 检测 build 段结束
                    if in_build and line and not line.startswith(' ' * (build_indent + 1)):
                        in_build = False
                        continue
                    
                    # 在 build 段中替换
                    if in_build:
                        # 跳过 EXTERNAL 前缀的引用
                        if not re.search(r'\$EXTERNAL|\$\{EXTERNAL', line):
                            lines[i] = re.sub(
                                re.escape(orig_deb_id),
                                new_id,
                                line
                            )
                
                content = '\n'.join(lines)
            
            # 写回文件
            with open(yaml_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✓ Updated linglong.yaml: id={new_id}, name={new_name}")
            return True
            
        except Exception as e:
            print(f"✗ Failed to update linglong.yaml: {e}")
            return False
    
    def _execute_pica_convert(self) -> bool:
        """
        执行 ll-pica convert
        
        Returns:
            是否成功
        """
        print("\n" + "=" * 60)
        print("Phase 1: ll-pica convert")
        print("=" * 60)
        
        try:
            # 创建工作目录
            self.pica_workdir.mkdir(parents=True, exist_ok=True)
            
            # 执行 ll-pica convert
            cmd = [
                "ll-pica",
                "convert",
                "-c", str(self.deb_file),
                "-w", str(self.pica_workdir)
            ]
            
            print(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=not self.verbose,
                text=True,
                timeout=3600  # 1小时超时
            )
            
            if result.returncode == 0:
                print("✓ ll-pica convert successful")
                return True
            else:
                print(f"✗ ll-pica convert failed (exit code: {result.returncode})")
                if result.stderr:
                    print(f"  Error: {result.stderr[:300]}...")
                return False
                
        except subprocess.TimeoutExpired:
            print("✗ ll-pica convert timed out (1 hour)")
            return False
        except FileNotFoundError:
            print("✗ ll-pica command not found")
            return False
        except Exception as e:
            print(f"✗ ll-pica convert error: {e}")
            return False
    
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
            print(f"Working directory: {self.app_build_dir}")
            
            result = subprocess.run(
                cmd,
                cwd=self.app_build_dir,
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
    
    def _update_files_tar(self) -> bool:
        """
        更新 files.tar.zst 归档
        
        Returns:
            是否成功
        """
        built_files_dir = self.app_build_dir / "linglong" / "output" / "binary" / "files"
        
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
    
    def _attempt_dependency_fix(self) -> Tuple[bool, str]:
        """
        尝试依赖修复
        
        Returns:
            (成功状态, 状态描述)
        """
        self.fix_attempts += 1
        print("\n" + "=" * 60)
        print(f"Phase 4: Dependency Fix Attempt {self.fix_attempts}")
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
        
        # 执行重建（使用标准构建，因为已经添加了依赖）
        print("\n" + "=" * 60)
        print(f"Phase 5: Rebuild After Fix {self.fix_attempts}")
        print("=" * 60)
        print("# BUILD_START")
        
        rebuild_success, rebuild_msg = self._execute_build(skip_output_check=False)
        
        if not rebuild_success:
            print(f"\n✗ Rebuild failed: {rebuild_msg}")
            print("# BUILD_END")
            return self._attempt_final_build()
        
        print(f"\n✓ Rebuild successful")
        print("# BUILD_END")
        
        # 再次执行兼容性测试
        if self.enable_compact_check:
            print("\n" + "=" * 60)
            print(f"Phase 6: Compat Check After Fix {self.fix_attempts}")
            print("=" * 60)
            print("# COMPAT_START")
            
            check_success, check_msg = self.compat_checker.check()
            self.compact_check_status = self.compat_checker.get_status()
            
            if check_success:
                print(f"\n✓ Compat check passed after fix: {check_msg}")
                print("# COMPAT_END")
                return True, f"Build and compat check passed after {self.fix_attempts} fix attempt(s)"
            else:
                print(f"\n✗ Compat check still failed: {check_msg}")
                # 尝试下一轮修复
                print("# COMPAT_END")
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
        print("Phase 7: Final Build Without Test")
        print("=" * 60)
        
        # 执行无测试的最终构建
        build_success, build_msg = self._execute_build(skip_output_check=True)
        
        if build_success:
            print(f"\n✓ Final build successful")
            return True, "Final build successful (compat check bypassed)"
        else:
            print(f"\n✗ Final build failed: {build_msg}")
            return False, f"All fix attempts failed. Final error: {build_msg}"
    
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
            self.app_build_dir / "files"
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
            self.app_build_dir / "files",
            self.app_build_dir / "files" / "lib"
        )
        
        if not symlink_success:
            return False, "Failed to create symlinks"
        
        # 更新 files.tar.zst
        tar_update_success = self.dependency_fixer.create_files_tar()
        
        if not tar_update_success:
            print("Warning: Failed to update files.tar.zst")
        
        return True, f"Fixed {len(libraries)} libraries with symlinks"
    
    def _update_yaml_with_dependencies(self, packages: List[str]) -> bool:
        """
        更新 linglong.yaml 中的依赖
        
        Args:
            packages: 包列表
            
        Returns:
            是否成功
        """
        yaml_path = self.app_build_dir / "linglong.yaml"
        
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
    
    def _export_layer(self) -> bool:
        """
        导出 layer
        
        Returns:
            是否成功
        """
        if not self.enable_layer_export:
            print("Layer export disabled, skipping")
            return True
        
        print("\n" + "=" * 60)
        print("Phase 7: Export Layer")
        print("=" * 60)
        
        try:
            cmd = [
                "ll-builder",
                "export",
                "--no-develop",
                "--layer",
                "-z", "zstd"
            ]
            
            print(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                cwd=self.app_build_dir,
                capture_output=not self.verbose,
                text=True,
                timeout=3600  # 1小时超时
            )
            
            if result.returncode == 0:
                self.layer_export_status = "passed"
                print("✓ Layer export successful")
                return True
            else:
                self.layer_export_status = "failed"
                print(f"✗ Layer export failed (exit code: {result.returncode})")
                if result.stderr:
                    print(f"  Error: {result.stderr[:300]}...")
                return False
                
        except subprocess.TimeoutExpired:
            self.layer_export_status = "timeout"
            print("✗ Layer export timed out (1 hour)")
            return False
        except FileNotFoundError:
            print("✗ ll-builder command not found")
            return False
        except Exception as e:
            self.layer_export_status = "error"
            print(f"✗ Layer export error: {e}")
            return False
    
    def _store_layer(self) -> bool:
        """
        存储 layer
        
        Returns:
            是否成功
        """
        if self.layer_export_status != "passed":
            print("Layer export failed, skipping layer storage")
            return False
        
        # 查找 layer 文件
        layer_files = list(self.app_build_dir.glob("*_binary.layer"))
        if not layer_files:
            print("✗ Layer file not found")
            return False
        
        layer_file = layer_files[0]
        
        # 确定目标目录
        if self.compact_check_status == "passed":
            target_dir = self.ll_stored_pool
            print(f"Storing layer to {target_dir} (compact check passed)")
        else:
            target_dir = self.ll_stored_pool / "forceTested"
            print(f"Storing layer to {target_dir} (compact check N/A)")
        
        # 创建目标目录并移动 layer 文件
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(layer_file), str(target_dir))
            print(f"✓ Layer stored at {target_dir / layer_file.name}")
            return True
        except Exception as e:
            print(f"✗ Failed to store layer: {e}")
            return False
    
    def convert(self) -> Tuple[bool, str]:
        """
        执行完整的转换流程
        
        Returns:
            (成功状态, 状态描述)
        """
        # 检查前置要求
        if not self._check_requirements():
            return False, "Requirements check failed"
        
        # Phase 1: ll-pica convert
        if not self._execute_pica_convert():
            return False, "ll-pica convert failed"
        
        # 解析 final-missing CSV 文件
        orig_name, orig_deb_id, orig_deb_ver, new_id = self._parse_final_missing_csv()
        if new_id and orig_name:
            yaml_file = self.app_build_dir / "linglong.yaml"
            if yaml_file.exists():
                self._print("Updating linglong.yaml with CSV data...", "normal")
                self._update_yaml_id_and_name(yaml_file, new_id, orig_name, orig_deb_id)
        
        # Phase 2: 初始构建（跳过输出检查，避免因非必要库导致构建失败）
        self._print("\n" + "=" * 60, "normal")
        self._print("Phase 2: Initial Build (skip output check)", "normal")
        self._print("=" * 60, "normal")
        print("# BUILD_START")
        
        build_success, build_msg = self._execute_build(skip_output_check=True)
        
        if not build_success:
            self._print(f"\n✗ Initial build failed: {build_msg}", "normal")
            print("# BUILD_END")
            return False, build_msg
        
        self._print(f"\n✓ Build successful", "normal")
        print("# BUILD_END")
        
        # Phase 3: 兼容性测试（独立步骤）
        if self.enable_compact_check:
            self._print("\n" + "=" * 60, "normal")
            self._print("Phase 3: Compat Check", "normal")
            self._print("=" * 60, "normal")
            print("# COMPAT_START")
            
            check_success, check_msg = self.compat_checker.check()
            self.compact_check_status = self.compat_checker.get_status()
            
            if check_success:
                self._print(f"\n✓ Compat check passed: {check_msg}", "normal")
            else:
                self._print(f"\n✗ Compat check failed: {check_msg}", "normal")
                # 兼容性测试失败，触发依赖修复流程
                print("# COMPAT_END")
                return self._attempt_dependency_fix()
            
            print("# COMPAT_END")
        else:
            self._print("\nCompat check disabled, skipping", "normal")
        
        # Phase 4: 导出 layer
        if self.enable_layer_export:
            self._export_layer()
            self._store_layer()
        
        # 打印最终状态（在所有模式下都显示）
        print("\n" + "=" * 60)
        print("Final Status")
        print("=" * 60)
        print(f"Build Status: {self.build_status}")
        print(f"Compat Check Status: {self.compact_check_status}")
        if self.fix_attempts > 0:
            print(f"Fix Attempts: {self.fix_attempts}")
        print(f"Layer Export Status: {self.layer_export_status}")
        
        return True, "Conversion completed successfully"
    
    def get_build_status(self) -> str:
        """获取构建状态"""
        return self.build_status
    
    def get_compat_check_status(self) -> str:
        """获取兼容性测试状态"""
        return self.compact_check_status
    
    def get_layer_export_status(self) -> str:
        """获取 layer 导出状态"""
        return self.layer_export_status
    
    def get_fix_attempts(self) -> int:
        """获取修复尝试次数"""
        return self.fix_attempts


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="Deb 包转换器 - 基于 linyaps-pica-helper 的核心功能"
    )
    
    parser.add_argument(
        "deb_file",
        type=str,
        help="deb 文件路径"
    )
    
    parser.add_argument(
        "--workdir",
        type=str,
        default=None,
        help="工作目录（默认：./pica-work）"
    )
    
    parser.add_argument(
        "--enable-compact-check",
        action="store_true",
        default=True,
        help="启用兼容性测试（默认：true）"
    )
    
    parser.add_argument(
        "--no-compact-check",
        action="store_true",
        help="禁用兼容性测试"
    )
    
    parser.add_argument(
        "--compact-check-timeout",
        type=int,
        default=30,
        help="兼容性测试超时时间（秒，默认：30）"
    )
    
    parser.add_argument(
        "--enable-layer-export",
        action="store_true",
        default=True,
        help="启用 layer 导出（默认：true）"
    )
    
    parser.add_argument(
        "--no-layer-export",
        action="store_true",
        help="禁用 layer 导出"
    )
    
    parser.add_argument(
        "--final-missing-csv",
        type=str,
        default=None,
        help="final-missing CSV 文件路径"
    )
    
    parser.add_argument(
        "--ll-stored-pool",
        type=str,
        default=None,
        help="layer 存储目录（默认：./StoredPool）"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="显示详细输出"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="只显示最终结果"
    )
    
    args = parser.parse_args()
    
    # 处理布尔参数
    enable_compact_check = args.enable_compact_check and not args.no_compact_check
    enable_layer_export = args.enable_layer_export and not args.no_layer_export
    
    # 创建转换器
    converter = DebConverter(
        deb_file=Path(args.deb_file),
        workdir=Path(args.workdir) if args.workdir else Path("./pica-work"),
        enable_compact_check=enable_compact_check,
        compact_check_timeout=args.compact_check_timeout,
        enable_layer_export=enable_layer_export,
        ll_stored_pool=Path(args.ll_stored_pool) if args.ll_stored_pool else None,
        final_missing_csv=Path(args.final_missing_csv) if args.final_missing_csv else None,
        verbose=args.verbose,
        quiet=args.quiet
    )
    
    # 执行转换
    success, message = converter.convert()
    
    # 打印最终状态（在所有模式下都显示）
    print("\n" + "=" * 60)
    print("Conversion Summary")
    print("=" * 60)
    print(f"Result: {message}")
    print(f"Build Status: {converter.get_build_status()}")
    print(f"Compat Check Status: {converter.get_compat_check_status()}")
    print(f"Layer Export Status: {converter.get_layer_export_status()}")
    if converter.get_fix_attempts() > 0:
        print(f"Fix Attempts: {converter.get_fix_attempts()}")
    
    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

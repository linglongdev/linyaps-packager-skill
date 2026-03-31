#!/usr/bin/env python3
"""
依赖分析模块 - 用于分析缺失的依赖库
基于 linyaps-pica-helper 的 analyzeMissingDeps() 功能
"""
import os
import re
import subprocess
from pathlib import Path
from typing import List, Tuple


class DependencyAnalyzer:
    """依赖分析器 - 分析缺失的依赖库"""
    
    def __init__(self, build_dir: Path, verbose: bool = False):
        """
        初始化依赖分析器
        
        Args:
            build_dir: 构建目录
            verbose: 是否显示详细输出
        """
        self.build_dir = Path(build_dir).resolve()
        self.verbose = verbose
        self.matched_packages: List[str] = []
        self.missing_deps_csv = self.build_dir / "missing_deps.csv"
        
        # 检测系统架构
        self.elf_tag = self._detect_elf_tag()
        
    def _detect_elf_tag(self) -> str:
        """
        检测 ELF 标签
        
        Returns:
            ELF 标签（如 x86_64-linux-gnu 或 aarch64-linux-gnu）
        """
        try:
            result = subprocess.run(
                ["dpkg", "--print-architecture"],
                capture_output=True,
                text=True,
                check=True
            )
            dpkg_arch = result.stdout.strip()
            
            # 映射 dpkg 架构到 ELF 标签
            arch_map = {
                "amd64": "x86_64-linux-gnu",
                "arm64": "aarch64-linux-gnu",
                "i386": "i386-linux-gnu",
                "riscv64": "riscv64-linux-gnu",
                "loongarch64": "loongarch64-linux-gnu"
            }
            
            return arch_map.get(dpkg_arch, dpkg_arch + "-linux-gnu")
        except Exception as e:
            if self.verbose:
                print(f"Warning: Failed to detect ELF tag: {e}, using default")
            return "x86_64-linux-gnu"
    
    def _check_apt_file(self) -> bool:
        """
        检查 apt-file 命令是否可用
        
        Returns:
            是否可用
        """
        if subprocess.run(["which", "apt-file"], capture_output=True).returncode != 0:
            print("✗ apt-file command not found")
            print("  Please install binutils package: apt-get install apt-file")
            print("  Then run: apt-file update")
            return False
        return True
    
    def _update_apt_file_cache(self) -> bool:
        """
        更新 apt-file 缓存
        
        Returns:
            是否成功
        """
        try:
            print("Updating apt-file cache...")
            subprocess.run(
                ["apt-file", "update"],
                check=True,
                capture_output=not self.verbose,
                timeout=300
            )
            print("✓ apt-file cache updated")
            return True
        except subprocess.TimeoutExpired:
            print("✗ apt-file update timed out (5 minutes)")
            return False
        except subprocess.CalledProcessError as e:
            print(f"✗ apt-file update failed: {e}")
            return False
    
    def _search_package_for_library(self, library_name: str) -> List[str]:
        """
        搜索包含指定库的包
        
        Args:
            library_name: 库名（如 libc.so.6）
            
        Returns:
            包列表
        """
        try:
            # 使用 apt-file search 查找包含该库的包
            result = subprocess.run(
                ["apt-file", "search", library_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            packages = set()
            for line in result.stdout.splitlines():
                # 格式: package-name: /path/to/library
                if ":" not in line:
                    continue
                
                package, path = line.split(":", 1)
                package = package.strip()
                path = path.strip()
                
                # 过滤 /usr/lib/<elf_tag> 路径
                if f"/usr/lib/{self.elf_tag}" in path:
                    packages.add(package)
            
            return sorted(packages)
        except subprocess.TimeoutExpired:
            if self.verbose:
                print(f"✗ apt-file search timed out for: {library_name}")
            return []
        except Exception as e:
            if self.verbose:
                print(f"✗ apt-file search error for {library_name}: {e}")
            return []
    
    def analyze_missing_deps(
        self,
        missing_deps_csv_path: Path = None,
        force_update_cache: bool = False
    ) -> Tuple[bool, List[str]]:
        """
        分析缺失的依赖
        
        Args:
            missing_deps_csv_path: missing_deps.csv 文件路径
            force_update_cache: 是否强制更新缓存
            
        Returns:
            (成功状态, 匹配的包列表)
        """
        # 设置 CSV 文件路径
        if missing_deps_csv_path is None:
            missing_deps_csv_path = self.missing_deps_csv
        
        missing_deps_csv_path = Path(missing_deps_csv_path).resolve()
        
        # 检查 apt-file 命令
        if not self._check_apt_file():
            return False, []
        
        # 更新 apt-file 缓存
        if force_update_cache:
            if not self._update_apt_file_cache():
                return False, []
        
        # 检查 missing_deps.csv 文件
        if not missing_deps_csv_path.exists():
            print(f"✗ Missing dependencies file not found: {missing_deps_csv_path}")
            return False, []
        
        # 读取缺失的依赖
        missing_libs = self._parse_missing_deps_csv(missing_deps_csv_path)
        if not missing_libs:
            print("No missing dependencies found in CSV file")
            return True, []
        
        print(f"\nAnalyzing {len(missing_libs)} missing dependencies...")
        all_packages = set()
        
        # 并行处理所有缺失依赖（简化版本，使用顺序处理）
        for i, lib in enumerate(missing_libs, 1):
            if self.verbose:
                print(f"[{i}/{len(missing_libs)}] Searching for: {lib}")
            else:
                print(f"[{i}/{len(missing_libs)}]", end="\r")
            
            packages = self._search_package_for_library(lib)
            all_packages.update(packages)
            
            if self.verbose and packages:
                print(f"  Found packages: {', '.join(packages)}")
        
        print(f"\n✓ Analysis complete")
        self.matched_packages = sorted(all_packages)
        
        if self.matched_packages:
            print(f"  Found {len(self.matched_packages)} packages:")
            for pkg in self.matched_packages:
                print(f"    - {pkg}")
        else:
            print("  No packages found")
        
        return True, self.matched_packages
    
    def _parse_missing_deps_csv(self, csv_path: Path) -> List[str]:
        """
        解析 missing_deps.csv 文件
        
        Args:
            csv_path: CSV 文件路径
            
        Returns:
            缺失库列表
        """
        missing_libs = []
        
        if not csv_path.exists():
            return missing_libs
        
        try:
            content = csv_path.read_text(encoding="utf-8")
            lines = content.strip().splitlines()
            
            # 跳过表头行
            first_line = True
            for line in lines:
                if first_line:
                    first_line = False
                    continue
                
                if not line.strip():
                    continue
                
                # CSV 格式: library_name, file_path
                parts = line.split(",")
                if len(parts) >= 1:
                    lib = parts[0].strip()
                    # 只处理共享库文件
                    if lib and ".so" in lib:
                        missing_libs.append(lib)
        
        except Exception as e:
            if self.verbose:
                print(f"Warning: Failed to parse CSV file: {e}")
        
        return missing_libs
    
    def save_matched_packages(self, output_file: Path) -> bool:
        """
        保存匹配的包到文件
        
        Args:
            output_file: 输出文件路径
            
        Returns:
            是否成功
        """
        try:
            output_file = Path(output_file).resolve()
            output_file.write_text("\n".join(self.matched_packages) + "\n", encoding="utf-8")
            print(f"✓ Saved {len(self.matched_packages)} packages to: {output_file}")
            return True
        except Exception as e:
            print(f"✗ Failed to save packages: {e}")
            return False
    
    def load_matched_packages(self, input_file: Path) -> List[str]:
        """
        从文件加载匹配的包
        
        Args:
            input_file: 输入文件路径
            
        Returns:
            包列表
        """
        input_file = Path(input_file).resolve()
        if not input_file.exists():
            return []
        
        try:
            content = input_file.read_text(encoding="utf-8")
            self.matched_packages = [line.strip() for line in content.strip().splitlines() if line.strip()]
            print(f"✓ Loaded {len(self.matched_packages)} packages from: {input_file}")
            return self.matched_packages
        except Exception as e:
            if self.verbose:
                print(f"Warning: Failed to load packages: {e}")
            return []
    
    def get_matched_packages(self) -> List[str]:
        """获取匹配的包列表"""
        return self.matched_packages

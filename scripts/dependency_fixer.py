#!/usr/bin/env python3
"""
依赖修复模块 - 用于修复缺失的依赖
基于 linyaps-pica-helper 的依赖修复功能
"""
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import List, Optional


class DependencyFixer:
    """依赖修复器 - 修复缺失的依赖"""
    
    def __init__(self, build_dir: Path, verbose: bool = False):
        """
        初始化依赖修复器
        
        Args:
            build_dir: 构建目录
            verbose: 是否显示详细输出
        """
        self.build_dir = Path(build_dir).resolve()
        self.verbose = verbose
        self.files_tar = self.build_dir / "files.tar.zst"
        self.missing_deps_csv = self.build_dir / "missing_deps.csv"
        
    def scan_non_std_dir_libraries(
        self,
        app_installed_files_dir: Optional[Path] = None
    ) -> Tuple[bool, List[str]]:
        """
        扫描非标准目录中的库
        
        Args:
            app_installed_files_dir: 应用文件目录
            
        Returns:
            (成功状态, 找到的库列表)
        """
        # 设置文件目录
        if app_installed_files_dir is None:
            app_installed_files_dir = self.build_dir / "files"
        else:
            app_installed_files_dir = Path(app_installed_files_dir).resolve()
        
        # 检查 files.tar.zst 并解压
        if not app_installed_files_dir.exists() and self.files_tar.exists():
            print(f"Extracting files.tar.zst to {app_installed_files_dir}...")
            self._extract_files_tar(app_installed_files_dir)
        
        if not app_installed_files_dir.exists():
            print(f"✗ Files directory does not exist: {app_installed_files_dir}")
            return False, []
        
        # 读取缺失的依赖
        if not self.missing_deps_csv.exists():
            print(f"✗ Missing dependencies CSV not found: {self.missing_deps_csv}")
            return False, []
        
        missing_libs = self._parse_missing_deps_csv(self.missing_deps_csv)
        if not missing_libs:
            print("No missing dependencies found")
            return True, []
        
        print(f"\nScanning {len(missing_libs)} missing libraries in non-standard directories...")
        found_libraries = []
        
        for lib in missing_libs:
            # 在非标准目录中查找库
            found_paths = self._find_library_in_non_std_dir(app_installed_files_dir, lib)
            if found_paths:
                found_libraries.append(lib)
                if self.verbose:
                    print(f"  ✓ Found {lib} at: {found_paths}")
                else:
                    print(f"  ✓ Found {lib}")
        
        if found_libraries:
            print(f"\n✓ Found {len(found_libraries)} libraries in non-standard directories")
        else:
            print("\n  No libraries found in non-standard directories")
        
        return True, found_libraries
    
    def _find_library_in_non_std_dir(self, files_dir: Path, library_name: str) -> List[Path]:
        """
        在非标准目录中查找库
        
        Args:
            files_dir: 文件目录
            library_name: 库名
            
        Returns:
            找到的路径列表
        """
        found_paths = []
        
        # 标准库目录
        std_lib_dirs = {
            "lib", "lib64", "usr/lib", "usr/lib64", "usr/lib/x86_64-linux-gnu",
            "usr/local/lib", "usr/local/lib64"
        }
        
        # 在 files_dir 中查找匹配的库文件
        for so_file in files_dir.rglob("*.so*"):
            # 获取相对于 files_dir 的路径
            rel_path = so_file.relative_to(files_dir)
            first_dir = rel_path.parts[0] if rel_path.parts else ""
            
            # 跳过标准库目录
            if first_dir in std_lib_dirs:
                continue
            
            # 检查文件名是否匹配（支持通配符）
            so_filename = so_file.name
            if self._library_matches(library_name, so_filename):
                found_paths.append(so_file)
        
        return found_paths
    
    def _library_matches(self, pattern: str, filename: str) -> bool:
        """
        检查库文件名是否匹配模式
        
        Args:
            pattern: 模式（如 libcdio.so.19）
            filename: 文件名（如 libcdio.so.19.0.0）
            
        Returns:
            是否匹配
        """
        # 移除版本后缀，提取基本名
        pattern_base = re.sub(r'\.so[\d.]*$', '', pattern)
        filename_base = re.sub(r'\.so[\d.]*$', '', filename)
        
        return pattern_base == filename_base
    
    def create_symlinks_for_libraries(
        self,
        libraries: List[str],
        source_dir: Path,
        target_lib_dir: Path
    ) -> Tuple[bool, List[str]]:
        """
        为库创建软链接到 lib 目录
        
        Args:
            libraries: 库列表
            source_dir: 源目录
            target_lib_dir: 目标 lib 目录
            
        Returns:
            (成功状态, 创建的软链接列表)
        """
        target_lib_dir = Path(target_lib_dir).resolve()
        target_lib_dir.mkdir(parents=True, exist_ok=True)
        
        symlinks_created = []
        
        print(f"\nCreating symlinks in {target_lib_dir}...")
        
        for lib in libraries:
            # 在源目录中查找匹配的库文件
            found_files = self._find_library_in_non_std_dir(source_dir, lib)
            
            if not found_files:
                if self.verbose:
                    print(f"  ✗ Library not found: {lib}")
                continue
            
            # 为所有找到的文件创建软链接
            for source_file in found_files:
                # 提取原始库名
                original_lib_name = lib
                
                # 创建软链接目标
                symlink_path = target_lib_dir / original_lib_name
                
                # 如果软链接已存在，跳过
                if symlink_path.exists() or symlink_path.is_symlink():
                    symlink_path.unlink()
                
                # 创建相对软链接
                try:
                    rel_path = os.path.relpath(source_file, symlink_path.parent)
                    symlink_path.symlink_to(rel_path)
                    symlinks_created.append(str(symlink_path))
                    print(f"  ✓ Created symlink: {symlink_path} -> {source_file}")
                except Exception as e:
                    print(f"  ✗ Failed to create symlink for {lib}: {e}")
        
        if symlinks_created:
            print(f"\n✓ Created {len(symlinks_created)} symlinks")
        else:
            print("\n  No symlinks created")
        
        return len(symlinks_created) > 0, symlinks_created
    
    def download_and_install_dependencies(
        self,
        packages: List[str],
        repo_deps_dir: Optional[Path] = None
    ) -> Tuple[bool, Path]:
        """
        下载并安装依赖包
        
        Args:
            packages: 包列表
            repo_deps_dir: 临时下载目录
            
        Returns:
            (成功状态, 解压后的目录)
        """
        # 设置临时下载目录
        if repo_deps_dir is None:
            repo_deps_dir = self.build_dir / ".repo_deps"
        else:
            repo_deps_dir = Path(repo_deps_dir).resolve()
        
        repo_deps_dir.mkdir(parents=True, exist_ok=True)
        deb_dir = repo_deps_dir / "debs"
        extract_dir = repo_deps_dir / "extracted"
        deb_dir.mkdir(parents=True, exist_ok=True)
        extract_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\nDownloading {len(packages)} dependencies...")
        
        # 下载所有 deb 包
        for pkg in packages:
            print(f"  Downloading: {pkg}")
            try:
                subprocess.run(
                    ["apt-get", "download", "-o=Dir::Cache::Archives={}".format(deb_dir), pkg],
                    cwd=deb_dir,
                    check=True,
                    capture_output=not self.verbose
                )
            except subprocess.CalledProcessError as e:
                print(f"  ✗ Failed to download {pkg}: {e}")
                if self.verbose and e.stderr:
                    print(f"    {e.stderr}")
                return False, extract_dir
        
        print(f"✓ Downloaded packages to {deb_dir}")
        
        # 解压所有 deb 包
        print(f"\nExtracting packages...")
        deb_files = list(deb_dir.glob("*.deb"))
        
        for deb_file in deb_files:
            print(f"  Extracting: {deb_file.name}")
            try:
                subprocess.run(
                    ["dpkg", "-x", str(deb_file), str(extract_dir)],
                    check=True,
                    capture_output=not self.verbose
                )
            except subprocess.CalledProcessError as e:
                print(f"  ✗ Failed to extract {deb_file.name}: {e}")
                return False, extract_dir
        
        # 删除 applications 目录（避免冲突）
        apps_dir = extract_dir / "usr" / "share" / "applications"
        if apps_dir.exists():
            shutil.rmtree(apps_dir)
            print("  Removed applications directory")
        
        print(f"✓ Extracted packages to {extract_dir}")
        return True, extract_dir
    
    def merge_dependencies_to_files(
        self,
        extracted_deps_dir: Path,
        target_files_dir: Path
    ) -> Tuple[bool, List[str]]:
        """
        将依赖合并到 files 目录
        
        Args:
            extracted_deps_dir: 解压后的依赖目录
            target_files_dir: 目标 files 目录
            
        Returns:
            (成功状态, 添加的文件列表)
        """
        extracted_deps_dir = Path(extracted_deps_dir).resolve()
        target_files_dir = Path(target_files_dir).resolve()
        target_files_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\nMerging dependencies to {target_files_dir}...")
        
        added_files = []
        
        # 将 usr/ 下的内容复制到 files/ 根目录
        usr_dir = extracted_deps_dir / "usr"
        if usr_dir.exists():
            for item in usr_dir.iterdir():
                dest = target_files_dir / item.name
                
                try:
                    if dest.exists():
                        if dest.is_dir():
                            # 目录已存在，递归复制
                            for sub_item in item.rglob("*"):
                                rel_path = sub_item.relative_to(item)
                                dest_sub = dest / rel_path
                                dest_sub.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(sub_item, dest_sub)
                                added_files.append(str(rel_path))
                        # 如果是已存在的文件，跳过
                    else:
                        shutil.copytree(item, dest, symlinks=True, dirs_exist_ok=False)
                        # 记录复制的文件
                        for copied_file in dest.rglob("*"):
                            rel_path = copied_file.relative_to(target_files_dir)
                            added_files.append(str(rel_path))
                except Exception as e:
                    print(f"  ✗ Failed to merge {item.name}: {e}")
        
        if added_files:
            print(f"✓ Merged {len(added_files)} files")
        else:
            print("  No files merged")
        
        return len(added_files) > 0, added_files
    
    def _extract_files_tar(self, target_dir: Path) -> bool:
        """
        解压 files.tar.zst
        
        Args:
            target_dir: 目标目录
            
        Returns:
            是否成功
        """
        target_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.files_tar.exists():
            print(f"✗ files.tar.zst not found: {self.files_tar}")
            return False
        
        try:
            # 使用 tar + zstd 解压
            subprocess.run(
                ["tar", "-I", "zstd", "-xf", str(self.files_tar), "-C", str(target_dir)],
                check=True,
                capture_output=not self.verbose
            )
            print(f"✓ Extracted files.tar.zst to {target_dir}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to extract files.tar.zst: {e}")
            return False
        except FileNotFoundError:
            # 如果 zstd 不可用，尝试使用 Python
            try:
                import zstandard as zstd
            except ImportError:
                print("✗ zstandard module not installed. Install with: pip install zstandard")
                return False
            
            try:
                with open(self.files_tar, "rb") as f:
                    dctx = zstd.ZstdDecompressor()
                    with tarfile.open(mode="r|*", fileobj=dctx.stream_reader(f)) as tar:
                        tar.extractall(target_dir)
                print(f"✓ Extracted files.tar.zst to {target_dir}")
                return True
            except Exception as e:
                print(f"✗ Failed to extract files.tar.zst with Python: {e}")
                return False
    
    def create_files_tar(self, source_dir: Optional[Path] = None) -> bool:
        """
        创建 files.tar.zst
        
        Args:
            source_dir: 源 files 目录
            
        Returns:
            是否成功
        """
        # 设置源目录
        if source_dir is None:
            source_dir = self.build_dir / "files"
        else:
            source_dir = Path(source_dir).resolve()
        
        if not source_dir.exists():
            print(f"✗ Source directory does not exist: {source_dir}")
            return False
        
        try:
            # 使用 tar + zstd 创建归档
            subprocess.run(
                ["tar", "-I", "zstd", "-cf", str(self.files_tar), "-C", str(source_dir), "."],
                check=True,
                capture_output=not self.verbose
            )
            print(f"✓ Created files.tar.zst: {self.files_tar}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to create files.tar.zst: {e}")
            return False
        except FileNotFoundError:
            # 如果 zstd 不可用，尝试使用 Python
            try:
                import zstandard as zstd
            except ImportError:
                print("✗ zstandard module not installed. Install with: pip install zstandard")
                return False
            
            try:
                with open(self.files_tar, "wb") as f:
                    cctx = zstd.ZstdCompressor()
                    with tarfile.open(mode="w|", fileobj=cctx.stream_writer(f)) as tar:
                        for item in source_dir.rglob("*"):
                            arcname = item.relative_to(source_dir)
                            tar.add(item, arcname=arcname)
                print(f"✓ Created files.tar.zst: {self.files_tar}")
                return True
            except Exception as e:
                print(f"✗ Failed to create files.tar.zst with Python: {e}")
                return False
    
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

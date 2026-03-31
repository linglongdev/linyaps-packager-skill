#!/usr/bin/env python3
"""
兼容性测试模块 - 用于执行运行时测试
基于 linyaps-pica-helper 的 builder_compat_check() 功能
"""
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple


class CompatChecker:
    """兼容性测试器 - 执行运行时测试"""
    
    def __init__(self, build_dir: Path, enable_compat_check: bool = True, timeout: int = 30):
        """
        初始化兼容性测试器
        
        Args:
            build_dir: 构建目录
            enable_compat_check: 是否启用兼容性测试
            timeout: 超时时间（秒）
        """
        self.build_dir = Path(build_dir).resolve()
        self.enable_compat_check = enable_compat_check
        self.timeout = timeout
        self.compat_checking_status = "N/A"
        self.error_log: Optional[Path] = None
        
    def check(self) -> Tuple[bool, str]:
        """
        执行兼容性测试
        
        Returns:
            (成功状态, 状态描述)
        """
        if not self.enable_compat_check:
            self.compat_checking_status = "N/A"
            return True, "Compat check disabled"
        
        if not self.build_dir.exists():
            self.compat_checking_status = "failed"
            return False, f"Build directory does not exist: {self.build_dir}"
        
        print(f"Running compat check with {self.timeout}s timeout...")
        
        try:
            # 使用 timeout 命令执行 ll-builder run
            result = subprocess.run(
                ["timeout", str(self.timeout), "ll-builder", "run"],
                cwd=self.build_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout + 10  # 额外的 10 秒缓冲
            )
            
            # timeout 命令返回 124 表示超时
            if result.returncode == 124:
                self.compat_checking_status = "passed"
                print("✓ Compat check passed (timeout as expected)")
                return True, "Passed (timeout)"
            elif result.returncode == 0:
                self.compat_checking_status = "passed"
                print("✓ Compat check passed")
                return True, "Passed"
            else:
                # 构建运行失败
                self.compat_checking_status = "failed"
                
                # 保存错误日志
                error_dir = self.build_dir / "compat-check-errors"
                error_dir.mkdir(parents=True, exist_ok=True)
                self.error_log = error_dir / "run-error.log"
                
                error_content = result.stderr or result.stdout or "No error output"
                self.error_log.write_text(error_content, encoding="utf-8")
                
                print(f"✗ Compat check failed (exit code: {result.returncode})")
                print(f"  Error log saved to: {self.error_log}")
                if error_content.strip():
                    print(f"  Error output preview: {error_content[:200]}...")
                
                return False, f"Failed (exit code: {result.returncode})"
                
        except subprocess.TimeoutExpired:
            # Python 的 timeout 超时，但 ll-builder run 可能仍在运行
            self.compat_checking_status = "passed"
            print("✓ Compat check passed (Python timeout)")
            return True, "Passed (Python timeout)"
        except FileNotFoundError:
            self.compat_checking_status = "failed"
            print("✗ ll-builder command not found")
            return False, "ll-builder not found"
        except Exception as e:
            self.compat_checking_status = "failed"
            print(f"✗ Compat check error: {e}")
            return False, f"Error: {e}"
    
    def get_status(self) -> str:
        """获取兼容性测试状态"""
        return self.compact_checking_status
    
    def get_error_log_path(self) -> Optional[Path]:
        """获取错误日志路径"""
        return self.error_log
    
    def get_error_log_content(self) -> Optional[str]:
        """获取错误日志内容"""
        if self.error_log and self.error_log.exists():
            return self.error_log.read_text(encoding="utf-8")
        return None

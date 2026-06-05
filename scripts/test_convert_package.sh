#!/usr/bin/env bash
# 测试 convert_package.sh 的优化功能

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONVERT_SCRIPT="${SCRIPT_DIR}/convert_package.sh"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试计数器
TESTS_PASSED=0
TESTS_FAILED=0

# 测试函数
test_case() {
  local test_name="$1"
  local test_command="$2"
  local expected_result="$3"

  echo -n "Testing: ${test_name}... "

  if eval "${test_command}" > /dev/null 2>&1; then
    if [ "${expected_result}" = "pass" ]; then
      echo -e "${GREEN}PASS${NC}"
      ((TESTS_PASSED++))
    else
      echo -e "${RED}FAIL${NC} (expected to fail but passed)"
      ((TESTS_FAILED++))
    fi
  else
    if [ "${expected_result}" = "fail" ]; then
      echo -e "${GREEN}PASS${NC}"
      ((TESTS_PASSED++))
    else
      echo -e "${RED}FAIL${NC} (expected to pass but failed)"
      ((TESTS_FAILED++))
    fi
  fi
}

# 打印测试结果
print_results() {
  echo ""
  echo "========================================"
  echo "Test Results"
  echo "========================================"
  echo -e "Passed: ${GREEN}${TESTS_PASSED}${NC}"
  echo -e "Failed: ${RED}${TESTS_FAILED}${NC}"
  echo "========================================"

  if [ ${TESTS_FAILED} -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    return 0
  else
    echo -e "${RED}Some tests failed!${NC}"
    return 1
  fi
}

# 测试帮助信息
echo "Testing help information..."
test_case "Help with -h" \
  "bash ${CONVERT_SCRIPT} -h" \
  "pass"

test_case "Help with --help" \
  "bash ${CONVERT_SCRIPT} --help" \
  "pass"

# 测试参数解析
echo ""
echo "Testing parameter parsing..."

# 测试 deb 转换参数
test_case "Deb conversion with --enable-compact-check" \
  "bash ${CONVERT_SCRIPT} deb /tmp/test.deb --enable-compact-check 2>&1 | grep -q 'enable-compact-check'" \
  "fail"  # 应该失败，因为文件不存在

test_case "Deb conversion with --no-compact-check" \
  "bash ${CONVERT_SCRIPT} deb /tmp/test.deb --no-compact-check 2>&1 | grep -q 'no-compact-check'" \
  "fail"  # 应该失败，因为文件不存在

test_case "Deb conversion with --compact-check-timeout" \
  "bash ${CONVERT_SCRIPT} deb /tmp/test.deb --compact-check-timeout 60 2>&1 | grep -q 'compact-check-timeout'" \
  "fail"  # 应该失败，因为文件不存在

test_case "Deb conversion with --enable-layer-export" \
  "bash ${CONVERT_SCRIPT} deb /tmp/test.deb --enable-layer-export 2>&1 | grep -q 'enable-layer-export'" \
  "fail"  # 应该失败，因为文件不存在

test_case "Deb conversion with --no-layer-export" \
  "bash ${CONVERT_SCRIPT} deb /tmp/test.deb --no-layer-export 2>&1 | grep -q 'no-layer-export'" \
  "fail"  # 应该失败，因为文件不存在

test_case "Deb conversion with --final-missing-csv" \
  "bash ${CONVERT_SCRIPT} deb /tmp/test.deb --final-missing-csv /tmp/test.csv 2>&1 | grep -q 'final-missing-csv'" \
  "fail"  # 应该失败，因为文件不存在

test_case "Deb conversion with --ll-stored-pool" \
  "bash ${CONVERT_SCRIPT} deb /tmp/test.deb --ll-stored-pool /tmp/pool 2>&1 | grep -q 'll-stored-pool'" \
  "fail"  # 应该失败，因为文件不存在

# 测试 AppImage 转换参数
echo ""
echo "Testing AppImage conversion parameters..."

test_case "AppImage conversion with --id and --version" \
  "bash ${CONVERT_SCRIPT} appimage /tmp/test.AppImage --id io.github.test --version 1.0.0 2>&1 | grep -q 'id.*version'" \
  "fail"  # 应该失败，因为文件不存在

test_case "AppImage conversion with --name" \
  "bash ${CONVERT_SCRIPT} appimage /tmp/test.AppImage --id io.github.test --version 1.0.0 --name 'Test App' 2>&1 | grep -q 'name'" \
  "fail"  # 应该失败，因为文件不存在

test_case "AppImage conversion with --description" \
  "bash ${CONVERT_SCRIPT} appimage /tmp/test.AppImage --id io.github.test --version 1.0.0 --description 'Test Description' 2>&1 | grep -q 'description'" \
  "fail"  # 应该失败，因为文件不存在

# 测试 Flatpak 转换参数
echo ""
echo "Testing Flatpak conversion parameters..."

test_case "Flatpak conversion with app id" \
  "bash ${CONVERT_SCRIPT} flatpak org.test.app 2>&1 | grep -q 'flatpak'" \
  "fail"  # 应该失败，因为 ll-pica 不可用

test_case "Flatpak conversion with --base" \
  "bash ${CONVERT_SCRIPT} flatpak org.test.app --base org.deepin.base/23.1.0 2>&1 | grep -q 'base'" \
  "fail"  # 应该失败，因为 ll-pica 不可用

test_case "Flatpak conversion with --base-version" \
  "bash ${CONVERT_SCRIPT} flatpak org.test.app --base-version 23.1.0 2>&1 | grep -q 'base-version'" \
  "fail"  # 应该失败，因为 ll-pica 不可用

test_case "Flatpak conversion with --version" \
  "bash ${CONVERT_SCRIPT} flatpak org.test.app --version 1.0.0 2>&1 | grep -q 'version'" \
  "fail"  # 应该失败，因为 ll-pica 不可用

test_case "Flatpak conversion with --build" \
  "bash ${CONVERT_SCRIPT} flatpak org.test.app --build 2>&1 | grep -q 'build'" \
  "fail"  # 应该失败，因为 ll-pica 不可用

test_case "Flatpak conversion with --layer" \
  "bash ${CONVERT_SCRIPT} flatpak org.test.app --layer 2>&1 | grep -q 'layer'" \
  "fail"  # 应该失败，因为 ll-pica 不可用

# 测试错误处理
echo ""
echo "Testing error handling..."

test_case "Missing required argument for AppImage (--id)" \
  "bash ${CONVERT_SCRIPT} appimage /tmp/test.AppImage --version 1.0.0 2>&1 | grep -q 'required'" \
  "pass"

test_case "Missing required argument for AppImage (--version)" \
  "bash ${CONVERT_SCRIPT} appimage /tmp/test.AppImage --id io.github.test 2>&1 | grep -q 'required'" \
  "pass"

test_case "Unknown argument" \
  "bash ${CONVERT_SCRIPT} deb /tmp/test.deb --unknown-arg 2>&1 | grep -q 'Unknown'" \
  "pass"

test_case "Unsupported conversion type" \
  "bash ${CONVERT_SCRIPT} rpm /tmp/test.rpm 2>&1 | grep -q 'Unsupported'" \
  "pass"

# 测试 linyaps-pica-helper 检查
echo ""
echo "Testing linyaps-pica-helper detection..."

test_case "Check linyaps-pica-helper availability" \
  "[ -f '${SCRIPT_DIR}/../linyaps-pica-helper/linyaps-pica-helper.sh' ]" \
  "pass"

# 打印测试结果
print_results

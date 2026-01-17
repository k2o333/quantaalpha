# 移除历史下载标记功能实施计划 (App4架构)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在App4架构中移除历史下载标记功能，简化系统架构，依赖更精确的基于数据内容的智能跳过机制。

**Architecture:** App4配置驱动架构，移除历史下载标记相关代码和功能，保留智能跳过机制。

**Tech Stack:** Python, App4架构组件 (ConfigLoader, Downloader, Scheduler, StorageManager, Processor, CoverageManager)

---

### Task 1: 添加新的移除历史标记函数

**Files:**
- Modify: `app4/core/coverage_manager.py`
- Modify: `app4/main.py:350-390`

**Step 1: 在CoverageManager中添加移除历史标记功能**

在 app4/core/coverage_manager.py 文件的 CoverageManager 类中添加以下方法：

```python
    def remove_historical_download_marker(self, interface_name: str):
        """
        移除指定接口的历史下载标记（如果存在）
        """
        import json
        from pathlib import Path
        import os

        # 构建历史下载标记文件路径（为了兼容旧系统）
        cache_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/cache')
        cache_dir.mkdir(exist_ok=True)
        marker_path = cache_dir / 'historical_download_marker.json'

        try:
            if marker_path.exists():
                with open(marker_path, 'r', encoding='utf-8') as f:
                    markers = json.load(f)

                # 如果接口在标记文件中，移除它
                if interface_name in markers:
                    del markers[interface_name]

                    # 如果没有其他标记，删除整个文件
                    if not markers:
                        marker_path.unlink()
                        print(f"已删除空的历史下载标记文件: {marker_path}")
                    else:
                        # 否则更新文件
                        with open(marker_path, 'w', encoding='utf-8') as f:
                            json.dump(markers, f, ensure_ascii=False, indent=2)
                        print(f"已从历史下载标记中移除接口: {interface_name}")

                    return True
            return False
        except Exception as e:
            print(f"移除历史下载标记失败: {e}")
            return False
```

**Step 2: 在CoverageManager中添加批量移除函数**

在 CoverageManager 类中添加以下方法：

```python
    def remove_all_historical_download_markers(self):
        """
        移除所有历史下载标记（如果存在）
        """
        import json
        from pathlib import Path
        import os

        # 构建历史下载标记文件路径
        cache_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/cache')
        marker_path = cache_dir / 'historical_download_marker.json'

        try:
            if marker_path.exists():
                marker_path.unlink()
                print(f"已删除历史下载标记文件: {marker_path}")
                return True
            return False
        except Exception as e:
            print(f"删除历史下载标记文件失败: {e}")
            return False
```

**Step 3: 运行测试以确认修改**

暂无测试，继续下一步。

### Task 2: 更新main.py移除历史标记逻辑

**Files:**
- Modify: `app4/main.py:350-390`

**Step 1: 在main.py中添加清理历史标记的逻辑**

```python
# 在 main() 函数的开始部分添加清理历史标记的逻辑
# 添加在处理参数后

        # 处理参数映射逻辑
        if args.tscode_historical:
            # tscode-historical 模式：使用配置组，获取所有需要股票循环模式的接口
            tscode_historical_group = config_loader.global_config.get('groups', {}).get('tscode_historical', [])
            interfaces_to_run.extend(tscode_historical_group)

        if args.pro_bar_only:
            # pro_bar_only 模式：添加 pro_bar 接口
            interfaces_to_run.append('pro_bar')

        if args.holders_data:
            # holders_data 模式：添加 holders 组
            holders_group = config_loader.global_config.get('groups', {}).get('holders', [])
            interfaces_to_run.extend(holders_group)

        if args.interface:
            # 指定接口
            interfaces_to_run.append(args.interface)

        if args.group:
            # 指定组
            groups = config_loader.global_config.get('groups', {})
            if args.group in groups:
                interfaces_to_run.extend(groups[args.group])
            else:
                logger.error(f"Group '{args.group}' not found")
                return 1

        # 如果没有指定任何参数，使用默认行为
        if not interfaces_to_run:
            # 默认运行所有可用接口（可根据积分限制过滤）
            available_interfaces = config_loader.get_available_interfaces()
            # 过滤掉ts_code依赖的接口和pro_bar
            tscode_historical_group = config_loader.global_config.get('groups', {}).get('tscode_historical', [])
            interfaces_to_run = [iface for iface in available_interfaces if iface not in tscode_historical_group and iface != 'pro_bar']

        logger.info(f"Interfaces to run: {interfaces_to_run}")

        # [新增] 在启动下载前移除所有历史下载标记文件
        from core.coverage_manager import CoverageManager
        coverage_manager = CoverageManager()
        coverage_manager.remove_all_historical_download_markers()
```

**Step 2: 运行测试以确认修改**

暂无测试，继续下一步。

### Task 3: 创建移除历史标记的命令行选项

**Files:**
- Modify: `app4/main.py:92-122`

**Step 1: 在命令行参数中添加移除历史标记的选项**

```python
    # 新增通用参数
    parser.add_argument('--interface', type=str,
                        help='指定接口名称')
    parser.add_argument('--group', type=str,
                        help='指定接口组名称')
    parser.add_argument('--concurrency', type=int, default=4,  # [修改] 从 8 改为 4
                        help='并发数')
    parser.add_argument('--log-level', type=str, default='INFO',
                        help='日志级别')
    parser.add_argument('--ts_code', type=str,
                        help='指定股票代码 (如: 000001.SZ)')
    # [新增] 添加移除历史标记的命令行选项
    parser.add_argument('--remove-historical-markers', action='store_true',
                        help='移除所有历史下载标记文件')

    args = parser.parse_args()
```

**Step 2: 在main函数中处理新参数**

```python
        # [新增] 如果指定了移除历史标记选项，执行移除并退出
        if args.remove_historical_markers:
            from core.coverage_manager import CoverageManager
            coverage_manager = CoverageManager()
            if coverage_manager.remove_all_historical_download_markers():
                print("已成功移除所有历史下载标记文件")
            else:
                print("未找到历史下载标记文件")
            return 0
```

**Step 3: 运行测试以确认修改**

暂无测试，继续下一步。

### Task 4: 更新文档说明

**Files:**
- Modify: `app4/README.md`
- Create: `app4/docs/remove_historical_markers.md`

**Step 1: 更新README.md添加新功能说明**

在README.md中找到命令行参数说明部分，添加新参数的说明：

```
- `--remove-historical-markers`: 移除所有历史下载标记文件
```

**Step 2: 创建专门的文档说明**

```markdown
# 移除历史下载标记功能

## 概述

App4架构现在提供了移除历史下载标记的功能，以简化系统架构并依赖更精确的基于数据内容的智能跳过机制。

## 使用方法

```bash
# 移除所有历史下载标记文件
python main.py --remove-historical-markers

# 或在下载数据的同时自动移除历史标记
python main.py --tscode-historical
```

## 背景

在早期的aspipe架构中，使用历史下载标记文件(`historical_download_marker.json`)来记录哪些接口已完成全历史下载。然而，系统现在已经具备了更先进的基于数据内容的智能跳过机制，历史下载标记功能变得多余且可能导致不必要的重复下载。

## 优势

1. **简化系统架构**：移除多余的功能，减少代码复杂度
2. **提高准确性**：依赖更精确的基于数据内容的智能跳过机制
3. **更好的维护性**：减少需要维护的代码量和状态文件
4. **避免冲突**：消除历史标记与智能跳过机制之间的潜在冲突
```

**Step 3: 运行测试以确认修改**

暂无测试，继续下一步。

### Task 5: 创建清理遗留文件的脚本

**Files:**
- Create: `app4/scripts/cleanup_historical_markers.py`

**Step 1: 创建清理脚本**

```python
#!/usr/bin/env python3
"""
清理历史下载标记文件的独立脚本
"""
import json
import os
from pathlib import Path


def remove_historical_download_markers():
    """移除所有历史下载标记文件"""
    # 确定缓存目录路径
    script_dir = Path(__file__).parent.parent
    cache_dir = script_dir / 'cache'

    # 构建历史下载标记文件路径
    marker_path = cache_dir / 'historical_download_marker.json'

    if marker_path.exists():
        try:
            # 读取当前标记文件
            with open(marker_path, 'r', encoding='utf-8') as f:
                markers = json.load(f)

            print(f"发现历史下载标记文件，包含 {len(markers)} 个接口的标记:")
            for interface in markers:
                print(f"  - {interface}")

            # 删除文件
            marker_path.unlink()
            print(f"已删除历史下载标记文件: {marker_path}")
            return True

        except Exception as e:
            print(f"删除历史下载标记文件失败: {e}")
            return False
    else:
        print("未找到历史下载标记文件")
        return False


if __name__ == "__main__":
    success = remove_historical_download_markers()
    if success:
        print("清理完成")
    else:
        print("清理失败或无需清理")
```

**Step 2: 运行测试以确认修改**

暂无测试，继续下一步。

### Task 6: 更新测试文件移除相关测试

**Files:**
- Modify: `app4/test/test_coverage_manager.py`
- Create: `app4/test/test_remove_historical_markers.py`

**Step 1: 在CoverageManager测试中添加新功能测试**

```python
import unittest
import os
import json
from pathlib import Path
from app4.core.coverage_manager import CoverageManager


class TestCoverageManager(unittest.TestCase):
    def setUp(self):
        self.coverage_manager = CoverageManager()

    def test_remove_historical_download_marker(self):
        """测试移除历史下载标记功能"""
        # 创建一个测试标记文件
        cache_dir = Path('cache')
        cache_dir.mkdir(exist_ok=True)
        marker_path = cache_dir / 'historical_download_marker.json'

        # 创建测试数据
        test_markers = {
            'test_interface': '2024-01-01 12:00:00',
            'daily': '2024-01-01 13:00:00'
        }

        with open(marker_path, 'w', encoding='utf-8') as f:
            json.dump(test_markers, f, ensure_ascii=False, indent=2)

        # 测试移除指定接口的标记
        result = self.coverage_manager.remove_historical_download_marker('test_interface')
        self.assertTrue(result)

        # 验证标记文件内容
        with open(marker_path, 'r', encoding='utf-8') as f:
            remaining_markers = json.load(f)

        self.assertEqual(len(remaining_markers), 1)
        self.assertIn('daily', remaining_markers)
        self.assertNotIn('test_interface', remaining_markers)

        # 清理测试文件
        marker_path.unlink()

    def test_remove_all_historical_download_markers(self):
        """测试移除所有历史下载标记功能"""
        # 创建一个测试标记文件
        cache_dir = Path('cache')
        cache_dir.mkdir(exist_ok=True)
        marker_path = cache_dir / 'historical_download_marker.json'

        # 创建测试数据
        test_markers = {
            'test_interface': '2024-01-01 12:00:00',
            'daily': '2024-01-01 13:00:00'
        }

        with open(marker_path, 'w', encoding='utf-8') as f:
            json.dump(test_markers, f, ensure_ascii=False, indent=2)

        # 测试移除所有标记
        result = self.coverage_manager.remove_all_historical_download_markers()
        self.assertTrue(result)

        # 验证文件已被删除
        self.assertFalse(marker_path.exists())


if __name__ == '__main__':
    unittest.main()
```

**Step 2: 创建专门的移除功能测试**

```python
import unittest
import os
import json
from pathlib import Path
from app4.scripts.cleanup_historical_markers import remove_historical_download_markers


class TestRemoveHistoricalMarkers(unittest.TestCase):
    def test_remove_historical_markers(self):
        """测试清理脚本功能"""
        # 创建一个测试标记文件
        cache_dir = Path('cache')
        cache_dir.mkdir(exist_ok=True)
        marker_path = cache_dir / 'historical_download_marker.json'

        # 创建测试数据
        test_markers = {
            'test_interface': '2024-01-01 12:00:00',
            'daily': '2024-01-01 13:00:00'
        }

        with open(marker_path, 'w', encoding='utf-8') as f:
            json.dump(test_markers, f, ensure_ascii=False, indent=2)

        # 测试清理函数
        result = remove_historical_download_markers()
        self.assertTrue(result)

        # 验证文件已被删除
        self.assertFalse(marker_path.exists())


if __name__ == '__main__':
    unittest.main()
```

**Step 3: 运行测试以确认修改**

暂无测试，继续下一步。

### Task 7: 验证和测试完整功能

**Files:**
- Test: `app4/test/test_remove_historical_markers.py`
- Test: `app4/test/test_coverage_manager.py`

**Step 1: 创建测试运行脚本**

```python
# 运行CoverageManager相关测试
import unittest
from app4.test.test_coverage_manager import TestCoverageManager
from app4.test.test_remove_historical_markers import TestRemoveHistoricalMarkers

if __name__ == '__main__':
    # 创建测试套件
    suite = unittest.TestSuite()

    # 添加测试用例
    suite.addTest(unittest.makeSuite(TestCoverageManager))
    suite.addTest(unittest.makeSuite(TestRemoveHistoricalMarkers))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 输出结果
    if result.wasSuccessful():
        print("\n所有测试通过!")
    else:
        print(f"\n测试失败: {len(result.failures)} 失败, {len(result.errors)} 错误")
```

**Step 2: 运行测试以确认功能正常**

运行: `python -m pytest app4/test/test_remove_historical_markers.py -v`
预期: PASS

**Step 3: 提交更改**

```bash
git add app4/core/coverage_manager.py app4/main.py app4/README.md app4/docs/remove_historical_markers.md app4/scripts/cleanup_historical_markers.py app4/test/test_remove_historical_markers.py
git commit -m "feat: 移除历史下载标记功能，简化系统架构"
```
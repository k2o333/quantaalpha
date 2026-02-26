#!/usr/bin/env python3
"""
反向日期范围增量下载功能测试验证脚本
根据 /home/quan/testdata/aspipe_v4/p/2026-2-21/reverse_date_range增量下载.md 的测试方案实施
"""

import os
import sys
import subprocess
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple
import polars as pl

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app4.core.storage import StorageManager
from app4.core.config_loader import ConfigLoader


class TestValidator:
    """测试验证器"""

    def __init__(self, storage_dir: str = "../data"):
        self.storage_dir = storage_dir
        self.storage_manager = StorageManager(storage_dir=storage_dir)
        self.config_loader = ConfigLoader()
        self.test_results = []

    def cleanup_interface_data(self, interface_name: str) -> bool:
        """清空指定接口的数据"""
        interface_path = os.path.join(self.storage_dir, interface_name)
        if os.path.exists(interface_path):
            import shutil
            shutil.rmtree(interface_path)
            print(f"✓ 已清空 {interface_name} 数据")
            return True
        print(f"✗ {interface_name} 数据目录不存在")
        return False

    def count_distinct_dates(self, interface_name: str, date_column: str = "trade_date") -> int:
        """统计接口中不同的日期数量"""
        try:
            df = self.storage_manager.read_interface_data(interface_name, columns=[date_column])
            if df.is_empty():
                return 0
            return df[date_column].n_unique()
        except Exception as e:
            print(f"✗ 统计日期失败: {e}")
            return 0

    def count_records(self, interface_name: str) -> int:
        """统计接口中的记录总数"""
        try:
            df = self.storage_manager.read_interface_data(interface_name)
            if df.is_empty():
                return 0
            return len(df)
        except Exception as e:
            print(f"✗ 统计记录数失败: {e}")
            return 0

    def run_download_command(self, interface_name: str, start_date: str, end_date: str, 
                           ts_code: str = None) -> Tuple[bool, str]:
        """运行下载命令"""
        cmd = ["python", "app4/main.py", "--update", "--interface", interface_name, 
               "--start_date", start_date, "--end_date", end_date]
        if ts_code:
            cmd.extend(["--ts_code", ts_code])
        
        print(f"\n执行命令: {' '.join(cmd)}")
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            elapsed_time = time.time() - start_time
            
            if result.returncode == 0:
                print(f"✓ 下载成功，耗时 {elapsed_time:.2f} 秒")
                return True, result.stdout
            else:
                print(f"✗ 下载失败，返回码: {result.returncode}")
                print(f"错误输出: {result.stderr}")
                return False, result.stderr
        except subprocess.TimeoutExpired:
            print(f"✗ 下载超时（>300秒）")
            return False, "Timeout"
        except Exception as e:
            print(f"✗ 下载异常: {e}")
            return False, str(e)

    def test_reverse_date_range_incremental(self) -> Dict:
        """测试反向日期范围增量下载（cyq_perf）"""
        print("\n" + "="*80)
        print("测试 1: 反向日期范围增量下载（cyq_perf）")
        print("="*80)
        
        interface_name = "cyq_perf"
        test_result = {
            "test_name": "反向日期范围增量下载",
            "interface": interface_name,
            "steps": [],
            "passed": False
        }
        
        # 步骤 1: 清空数据
        print("\n步骤 1: 清空数据")
        self.cleanup_interface_data(interface_name)
        test_result["steps"].append({"step": "清空数据", "status": "completed"})
        
        # 步骤 2: 第一次下载（较小日期范围）
        print("\n步骤 2: 第一次下载（20260201-20260210）")
        success, output = self.run_download_command(interface_name, "20260201", "20260210")
        if not success:
            test_result["steps"].append({"step": "第一次下载", "status": "failed", "error": output})
            test_result["passed"] = False
            self.test_results.append(test_result)
            return test_result
        
        count1 = self.count_distinct_dates(interface_name)
        records1 = self.count_records(interface_name)
        print(f"第一次下载后: {count1} 个不同日期, {records1} 条记录")
        test_result["steps"].append({
            "step": "第一次下载",
            "status": "completed",
            "dates": count1,
            "records": records1
        })
        
        # 步骤 3: 第二次下载（较大日期范围）
        print("\n步骤 3: 第二次下载（20260125-20260215）")
        success, output = self.run_download_command(interface_name, "20260125", "20260215")
        if not success:
            test_result["steps"].append({"step": "第二次下载", "status": "failed", "error": output})
            test_result["passed"] = False
            self.test_results.append(test_result)
            return test_result
        
        count2 = self.count_distinct_dates(interface_name)
        records2 = self.count_records(interface_name)
        print(f"第二次下载后: {count2} 个不同日期, {records2} 条记录")
        test_result["steps"].append({
            "step": "第二次下载",
            "status": "completed",
            "dates": count2,
            "records": records2
        })
        
        # 验证增量下载是否生效
        new_dates = count2 - count1
        new_records = records2 - records1
        print(f"\n新增: {new_dates} 个日期, {new_records} 条记录")
        
        # 检查是否有覆盖率跳过日志
        has_skip_log = "Skipping" in output or "skip" in output.lower()
        print(f"覆盖率跳过日志: {'是' if has_skip_log else '否'}")
        
        # 预期：第二次下载应该只下载新增的日期（20260125-20260131 和 20260211-20260215）
        # 约 7 + 5 = 12 个交易日
        expected_new_dates = 12  # 估算值
        test_result["steps"].append({
            "step": "验证增量下载",
            "status": "completed",
            "expected_new_dates": expected_new_dates,
            "actual_new_dates": new_dates,
            "has_skip_log": has_skip_log
        })
        
        # 判断测试是否通过
        test_result["passed"] = (new_dates > 0 and new_dates <= expected_new_dates + 2)  # 允许一定误差
        
        print(f"\n测试结果: {'✓ 通过' if test_result['passed'] else '✗ 失败'}")
        self.test_results.append(test_result)
        return test_result

    def test_stock_loop_no_cross_stock_error(self) -> Dict:
        """测试 Stock Loop 接口，验证不会发生跨股票误判（top10_holders）"""
        print("\n" + "="*80)
        print("测试 2: Stock Loop 接口跨股票误判验证（top10_holders）")
        print("="*80)
        
        interface_name = "top10_holders"
        test_result = {
            "test_name": "Stock Loop 跨股票误判验证",
            "interface": interface_name,
            "steps": [],
            "passed": False
        }
        
        # 步骤 1: 清空数据
        print("\n步骤 1: 清空数据")
        self.cleanup_interface_data(interface_name)
        test_result["steps"].append({"step": "清空数据", "status": "completed"})
        
        # 步骤 2: 下载第一只股票
        print("\n步骤 2: 下载 000001.SZ（20260201-20260210）")
        success, output = self.run_download_command(interface_name, "20260201", "20260210", "000001.SZ")
        if not success:
            test_result["steps"].append({"step": "下载第一只股票", "status": "failed", "error": output})
            test_result["passed"] = False
            self.test_results.append(test_result)
            return test_result
        
        count1 = self.count_records(interface_name)
        print(f"第一只股票下载后: {count1} 条记录")
        test_result["steps"].append({
            "step": "下载第一只股票",
            "status": "completed",
            "records": count1
        })
        
        # 步骤 3: 下载第二只股票（相同日期范围）
        print("\n步骤 3: 下载 000002.SZ（20260201-20260210）")
        success, output = self.run_download_command(interface_name, "20260201", "20260210", "000002.SZ")
        if not success:
            test_result["steps"].append({"step": "下载第二只股票", "status": "failed", "error": output})
            test_result["passed"] = False
            self.test_results.append(test_result)
            return test_result
        
        count2 = self.count_records(interface_name)
        print(f"第二只股票下载后: {count2} 条记录")
        test_result["steps"].append({
            "step": "下载第二只股票",
            "status": "completed",
            "records": count2
        })
        
        # 验证第二只股票的数据是否被下载
        new_records = count2 - count1
        print(f"\n新增记录: {new_records} 条")
        
        # 验证两只股票都有数据
        try:
            df = self.storage_manager.read_interface_data(interface_name)
            if not df.is_empty():
                stock1_count = len(df.filter(pl.col("ts_code") == "000001.SZ"))
                stock2_count = len(df.filter(pl.col("ts_code") == "000002.SZ"))
                print(f"000001.SZ: {stock1_count} 条记录")
                print(f"000002.SZ: {stock2_count} 条记录")
                
                test_result["steps"].append({
                    "step": "验证两只股票数据",
                    "status": "completed",
                    "stock1_records": stock1_count,
                    "stock2_records": stock2_count
                })
                
                # 判断测试是否通过：两只股票都应该有数据
                test_result["passed"] = (stock1_count > 0 and stock2_count > 0)
            else:
                test_result["passed"] = False
        except Exception as e:
            print(f"✗ 验证失败: {e}")
            test_result["passed"] = False
        
        print(f"\n测试结果: {'✓ 通过' if test_result['passed'] else '✗ 失败'}")
        self.test_results.append(test_result)
        return test_result

    def test_normal_date_range_mode(self) -> Dict:
        """测试普通日期范围模式（daily）"""
        print("\n" + "="*80)
        print("测试 3: 普通日期范围模式（daily）")
        print("="*80)
        
        interface_name = "daily"
        test_result = {
            "test_name": "普通日期范围模式",
            "interface": interface_name,
            "steps": [],
            "passed": False
        }
        
        # 步骤 1: 清空数据
        print("\n步骤 1: 清空数据")
        self.cleanup_interface_data(interface_name)
        test_result["steps"].append({"step": "清空数据", "status": "completed"})
        
        # 步骤 2: 第一次下载
        print("\n步骤 2: 第一次下载（20260201-20260210）")
        success, output = self.run_download_command(interface_name, "20260201", "20260210")
        if not success:
            test_result["steps"].append({"step": "第一次下载", "status": "failed", "error": output})
            test_result["passed"] = False
            self.test_results.append(test_result)
            return test_result
        
        count1 = self.count_distinct_dates(interface_name)
        print(f"第一次下载后: {count1} 个不同日期")
        test_result["steps"].append({
            "step": "第一次下载",
            "status": "completed",
            "dates": count1
        })
        
        # 步骤 3: 第二次下载（扩大日期范围）
        print("\n步骤 3: 第二次下载（20260125-20260215）")
        success, output = self.run_download_command(interface_name, "20260125", "20260215")
        if not success:
            test_result["steps"].append({"step": "第二次下载", "status": "failed", "error": output})
            test_result["passed"] = False
            self.test_results.append(test_result)
            return test_result
        
        count2 = self.count_distinct_dates(interface_name)
        print(f"第二次下载后: {count2} 个不同日期")
        test_result["steps"].append({
            "step": "第二次下载",
            "status": "completed",
            "dates": count2
        })
        
        # 验证增量下载是否生效
        new_dates = count2 - count1
        print(f"\n新增日期: {new_dates} 个")
        
        test_result["steps"].append({
            "step": "验证增量下载",
            "status": "completed",
            "new_dates": new_dates
        })
        
        # 判断测试是否通过：应该有新增日期
        test_result["passed"] = (new_dates > 0)
        
        print(f"\n测试结果: {'✓ 通过' if test_result['passed'] else '✗ 失败'}")
        self.test_results.append(test_result)
        return test_result

    def test_different_date_anchor_types(self) -> Dict:
        """测试不同日期锚点类型（disclosure_date）"""
        print("\n" + "="*80)
        print("测试 4: 不同日期锚点类型（disclosure_date）")
        print("="*80)
        
        interface_name = "disclosure_date"
        test_result = {
            "test_name": "不同日期锚点类型",
            "interface": interface_name,
            "steps": [],
            "passed": False
        }
        
        # 步骤 1: 清空数据
        print("\n步骤 1: 清空数据")
        self.cleanup_interface_data(interface_name)
        test_result["steps"].append({"step": "清空数据", "status": "completed"})
        
        # 步骤 2: 第一次下载
        print("\n步骤 2: 第一次下载（20260201-20260210）")
        success, output = self.run_download_command(interface_name, "20260201", "20260210")
        if not success:
            test_result["steps"].append({"step": "第一次下载", "status": "failed", "error": output})
            test_result["passed"] = False
            self.test_results.append(test_result)
            return test_result
        
        count1 = self.count_distinct_dates(interface_name, "ann_date")
        print(f"第一次下载后: {count1} 个不同日期")
        test_result["steps"].append({
            "step": "第一次下载",
            "status": "completed",
            "dates": count1
        })
        
        # 步骤 3: 第二次下载（扩大日期范围）
        print("\n步骤 3: 第二次下载（20260125-20260215）")
        success, output = self.run_download_command(interface_name, "20260125", "20260215")
        if not success:
            test_result["steps"].append({"step": "第二次下载", "status": "failed", "error": output})
            test_result["passed"] = False
            self.test_results.append(test_result)
            return test_result
        
        count2 = self.count_distinct_dates(interface_name, "ann_date")
        print(f"第二次下载后: {count2} 个不同日期")
        test_result["steps"].append({
            "step": "第二次下载",
            "status": "completed",
            "dates": count2
        })
        
        # 验证增量下载是否生效
        new_dates = count2 - count1
        print(f"\n新增日期: {new_dates} 个")
        
        # 检查是否有覆盖率跳过日志
        has_skip_log = "Skipping" in output or "skip" in output.lower()
        print(f"覆盖率跳过日志: {'是' if has_skip_log else '否'}")
        
        test_result["steps"].append({
            "step": "验证增量下载",
            "status": "completed",
            "new_dates": new_dates,
            "has_skip_log": has_skip_log
        })
        
        # 判断测试是否通过：应该有新增日期
        test_result["passed"] = (new_dates > 0)
        
        print(f"\n测试结果: {'✓ 通过' if test_result['passed'] else '✗ 失败'}")
        self.test_results.append(test_result)
        return test_result

    def generate_report(self) -> str:
        """生成测试报告"""
        print("\n" + "="*80)
        print("测试报告")
        print("="*80)
        
        report_lines = []
        report_lines.append("# 反向日期范围增量下载功能测试报告")
        report_lines.append(f"\n生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("\n## 测试摘要\n")
        
        passed_count = sum(1 for r in self.test_results if r["passed"])
        total_count = len(self.test_results)
        
        report_lines.append(f"- 总测试数: {total_count}")
        report_lines.append(f"- 通过: {passed_count}")
        report_lines.append(f"- 失败: {total_count - passed_count}")
        report_lines.append(f"- 通过率: {passed_count/total_count*100:.1f}%")
        
        report_lines.append("\n## 详细测试结果\n")
        
        for i, result in enumerate(self.test_results, 1):
            status_icon = "✓" if result["passed"] else "✗"
            report_lines.append(f"### 测试 {i}: {result['test_name']}")
            report_lines.append(f"- 接口: {result['interface']}")
            report_lines.append(f"- 状态: {status_icon} {'通过' if result['passed'] else '失败'}")
            
            report_lines.append("\n测试步骤:")
            for step in result["steps"]:
                step_status = "✓" if step.get("status") == "completed" else "✗"
                report_lines.append(f"  - {step_status} {step['step']}")
                if "dates" in step:
                    report_lines.append(f"    - 日期数: {step['dates']}")
                if "records" in step:
                    report_lines.append(f"    - 记录数: {step['records']}")
                if "new_dates" in step:
                    report_lines.append(f"    - 新增日期: {step['new_dates']}")
                if "has_skip_log" in step:
                    report_lines.append(f"    - 覆盖率跳过: {step['has_skip_log']}")
                if "error" in step:
                    report_lines.append(f"    - 错误: {step['error']}")
            
            report_lines.append("")
        
        report_text = "\n".join(report_lines)
        print(report_text)
        
        # 保存报告到文件
        report_file = "/home/quan/testdata/aspipe_v4/p/2026-2-21/test_report.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"\n报告已保存到: {report_file}")
        
        return report_text

    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "="*80)
        print("反向日期范围增量下载功能测试验证")
        print("="*80)
        
        # 运行测试
        self.test_reverse_date_range_incremental()
        self.test_stock_loop_no_cross_stock_error()
        self.test_normal_date_range_mode()
        self.test_different_date_anchor_types()
        
        # 生成报告
        self.generate_report()


def main():
    """主函数"""
    validator = TestValidator()
    validator.run_all_tests()


if __name__ == "__main__":
    main()

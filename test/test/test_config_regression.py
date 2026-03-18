"""
配置回归测试

测试目标：
9. A 类接口配置检查（高密度接口）
10. B 类接口配置检查（稀疏接口）

验证：
- 高密度接口都已配置 is_date_anchor: true 和 commit_on_success: true
- 稀疏接口配置了 commit_on_success: true 但没有 is_date_anchor
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import glob
import yaml
import unittest
from typing import Dict, Any, List, Tuple


class TestConfigRegression(unittest.TestCase):
    """配置回归测试"""

    CONFIG_DIR = "/home/quan/testdata/aspipe_v4/app4/config/interfaces"
    
    # A 类接口：高密度日频接口，应该配置 is_date_anchor
    HIGH_DENSITY_INTERFACES = [
        "daily",
        "daily_basic",
        "moneyflow",
        "moneyflow_dc",
        "moneyflow_cnt_ths",
    ]
    
    # B 类接口：稀疏接口，应该配置 commit_on_success 但不应该有 is_date_anchor
    SPARSE_INTERFACES = [
        "repurchase",
        "stock_st",
        "suspend_d",
        "block_trade",
        "stk_surv",
    ]

    def load_config(self, interface_name: str) -> Dict[str, Any]:
        """加载接口配置文件"""
        config_path = os.path.join(self.CONFIG_DIR, f"{interface_name}.yaml")
        if not os.path.exists(config_path):
            self.skipTest(f"配置文件不存在: {config_path}")
        
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def get_offset_commit_on_success(self, config: Dict[str, Any]) -> Tuple[bool, bool]:
        """
        获取 offset 配置
        
        Returns:
            Tuple[has_offset, commit_on_success]
        """
        pagination = config.get("pagination", {})
        
        # 检查新格式
        offset = pagination.get("offset", {})
        if offset:
            return True, offset.get("commit_on_success", False)
        
        return False, False

    def has_date_anchor(self, config: Dict[str, Any]) -> bool:
        """检查是否配置了 is_date_anchor"""
        parameters = config.get("parameters", {})
        for param_name, param_def in parameters.items():
            if param_def.get("is_date_anchor", False):
                return True
        return False

    def get_date_anchor_params(self, config: Dict[str, Any]) -> List[str]:
        """获取所有 is_date_anchor 参数名"""
        anchors = []
        parameters = config.get("parameters", {})
        for param_name, param_def in parameters.items():
            if param_def.get("is_date_anchor", False):
                anchors.append(param_name)
        return anchors

    # =========================================================================
    # 测试9: A 类接口配置检查
    # =========================================================================
    def test_high_density_interfaces_have_date_anchor(self):
        """
        测试9a: 高密度接口都已配置 is_date_anchor: true
        """
        missing_date_anchor = []
        
        for interface_name in self.HIGH_DENSITY_INTERFACES:
            config = self.load_config(interface_name)
            
            if not self.has_date_anchor(config):
                missing_date_anchor.append(interface_name)
        
        self.assertEqual(
            len(missing_date_anchor), 0,
            f"以下高密度接口缺少 is_date_anchor 配置: {missing_date_anchor}"
        )
        
        print("✓ 测试9a通过: 所有高密度接口都配置了 is_date_anchor")

    def test_high_density_interfaces_have_commit_on_success(self):
        """
        测试9b: 高密度接口的 offset 都配置了 commit_on_success: true
        """
        missing_offset = []
        missing_commit = []

        for interface_name in self.HIGH_DENSITY_INTERFACES:
            config = self.load_config(interface_name)
            has_offset, commit_on_success = self.get_offset_commit_on_success(config)

            if not has_offset:
                missing_offset.append(interface_name)
            elif not commit_on_success:
                missing_commit.append(interface_name)

        self.assertEqual(
            len(missing_offset), 0,
            f"以下高密度接口应启用 offset 但未配置: {missing_offset}"
        )

        self.assertEqual(
            len(missing_commit), 0,
            f"以下高密度接口的 offset 缺少 commit_on_success: {missing_commit}"
        )
        
        print("✓ 测试9b通过: 所有高密度接口的 offset 都配置了 commit_on_success")

    def test_high_density_interfaces_detail(self):
        """
        测试9c: 高密度接口详细配置检查
        """
        print("\n高密度接口配置详情:")
        for interface_name in self.HIGH_DENSITY_INTERFACES:
            config = self.load_config(interface_name)
            
            date_anchors = self.get_date_anchor_params(config)
            has_offset, commit_on_success = self.get_offset_commit_on_success(config)
            
            print(f"  {interface_name}:")
            print(f"    - date_anchor 参数: {date_anchors}")
            print(f"    - offset 启用: {has_offset}")
            print(f"    - commit_on_success: {commit_on_success}")

            # 断言
            self.assertTrue(len(date_anchors) > 0, f"{interface_name} 缺少 date_anchor")
            self.assertTrue(has_offset, f"{interface_name} 应启用 offset")
            self.assertTrue(commit_on_success, f"{interface_name} 缺少 commit_on_success")

    # =========================================================================
    # 测试10: B 类接口配置检查
    # =========================================================================
    def test_sparse_interfaces_have_commit_on_success(self):
        """
        测试10a: 稀疏接口的 offset 都配置了 commit_on_success: true
        """
        missing_commit = []
        
        for interface_name in self.SPARSE_INTERFACES:
            config = self.load_config(interface_name)
            has_offset, commit_on_success = self.get_offset_commit_on_success(config)
            
            if has_offset and not commit_on_success:
                missing_commit.append(interface_name)
        
        self.assertEqual(
            len(missing_commit), 0,
            f"以下稀疏接口的 offset 缺少 commit_on_success: {missing_commit}"
        )
        
        print("✓ 测试10a通过: 所有稀疏接口的 offset 都配置了 commit_on_success")

    def test_sparse_interfaces_no_date_anchor(self):
        """
        测试10b: 稀疏接口没有被误改为 date_anchor
        """
        incorrectly_anchored = []
        
        for interface_name in self.SPARSE_INTERFACES:
            config = self.load_config(interface_name)
            
            if self.has_date_anchor(config):
                incorrectly_anchored.append(interface_name)
        
        self.assertEqual(
            len(incorrectly_anchored), 0,
            f"以下稀疏接口不应配置 is_date_anchor: {incorrectly_anchored}"
        )
        
        print("✓ 测试10b通过: 稀疏接口没有误配 is_date_anchor")

    def test_sparse_interfaces_detail(self):
        """
        测试10c: 稀疏接口详细配置检查
        """
        print("\n稀疏接口配置详情:")
        for interface_name in self.SPARSE_INTERFACES:
            config = self.load_config(interface_name)
            
            date_anchors = self.get_date_anchor_params(config)
            has_offset, commit_on_success = self.get_offset_commit_on_success(config)
            pagination = config.get("pagination", {})
            window_size = pagination.get("window_size_days", "N/A")
            
            print(f"  {interface_name}:")
            print(f"    - date_anchor 参数: {date_anchors if date_anchors else '(无)'}")
            print(f"    - offset 启用: {has_offset}")
            print(f"    - commit_on_success: {commit_on_success}")
            print(f"    - window_size_days: {window_size}")
            
            # 断言
            self.assertEqual(len(date_anchors), 0, 
                f"{interface_name} 不应有 date_anchor（稀疏接口）")
            if has_offset:
                self.assertTrue(commit_on_success, f"{interface_name} 缺少 commit_on_success")

    # =========================================================================
    # 综合测试
    # =========================================================================
    def test_all_offset_enabled_interfaces_have_commit_on_success(self):
        """
        测试: 所有启用 offset 的接口都配置了 commit_on_success
        """
        # 获取所有配置文件
        config_files = glob.glob(os.path.join(self.CONFIG_DIR, "*.yaml"))
        
        missing_commit = []
        
        for config_file in config_files:
            interface_name = os.path.basename(config_file).replace(".yaml", "")
            
            with open(config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            
            has_offset, commit_on_success = self.get_offset_commit_on_success(config)
            
            if has_offset and not commit_on_success:
                missing_commit.append(interface_name)
        
        self.assertEqual(
            len(missing_commit), 0,
            f"以下启用 offset 的接口缺少 commit_on_success: {missing_commit}"
        )
        
        print(f"✓ 所有启用 offset 的接口（{len(config_files)} 个）都配置了 commit_on_success")

    def test_config_consistency_summary(self):
        """
        测试: 配置一致性总结
        """
        config_files = glob.glob(os.path.join(self.CONFIG_DIR, "*.yaml"))
        
        stats = {
            "total": 0,
            "with_offset": 0,
            "with_commit_on_success": 0,
            "with_date_anchor": 0,
            "high_density": 0,
            "sparse": 0,
        }
        
        for config_file in config_files:
            interface_name = os.path.basename(config_file).replace(".yaml", "")
            
            with open(config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            
            stats["total"] += 1
            
            has_offset, commit_on_success = self.get_offset_commit_on_success(config)
            has_anchor = self.has_date_anchor(config)
            
            if has_offset:
                stats["with_offset"] += 1
            if commit_on_success:
                stats["with_commit_on_success"] += 1
            if has_anchor:
                stats["with_date_anchor"] += 1
            if interface_name in self.HIGH_DENSITY_INTERFACES:
                stats["high_density"] += 1
            if interface_name in self.SPARSE_INTERFACES:
                stats["sparse"] += 1
        
        print("\n配置统计:")
        print(f"  总接口数: {stats['total']}")
        print(f"  启用 offset: {stats['with_offset']}")
        print(f"  配置 commit_on_success: {stats['with_commit_on_success']}")
        print(f"  配置 is_date_anchor: {stats['with_date_anchor']}")
        print(f"  高密度接口: {stats['high_density']}")
        print(f"  稀疏接口: {stats['sparse']}")


if __name__ == "__main__":
    unittest.main()

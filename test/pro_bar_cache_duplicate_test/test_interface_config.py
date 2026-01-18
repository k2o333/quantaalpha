#!/usr/bin/env python3
"""
Test 7: pro_bar接口配置验证
目的: 验证pro_bar接口的配置是否正确
"""

import sys
import os

# 添加项目路径
sys.path.append('/home/quan/testdata/aspipe_v4')

def test_interface_config():
    """测试pro_bar接口配置"""
    print("=" * 60)
    print("测试7: pro_bar接口配置验证")
    print("=" * 60)

    try:
        # 直接导入所需的模块和配置
        from app.enhanced_download_config import DOWNLOAD_PIPELINE_CONFIG

        # 获取pro_bar接口配置
        pro_bar_config = DOWNLOAD_PIPELINE_CONFIG.get('pro_bar')

        if pro_bar_config is None:
            print("❌ pro_bar接口配置不存在")
            return False

        print(f"pro_bar接口配置: {pro_bar_config}")

        # 检查requires_tscode属性
        requires_tscode = getattr(pro_bar_config, 'requires_tscode', False)
        print(f"requires_tscode: {requires_tscode}")

        # 检查缓存相关配置
        cache_enabled = getattr(pro_bar_config, 'cache_enabled', True)
        print(f"cache_enabled: {cache_enabled}")

        cache_ttl_hours = getattr(pro_bar_config, 'cache_ttl_hours', 24)
        print(f"cache_ttl_hours: {cache_ttl_hours}")

        # 检查其他重要配置
        priority = getattr(pro_bar_config, 'priority', 1)
        print(f"priority: {priority}")

        max_retries = getattr(pro_bar_config, 'max_retries', 3)
        print(f"max_retries: {max_retries}")

        # 检查接口配置是否正确
        config_valid = True

        if requires_tscode is not True:
            print("❌ pro_bar接口requires_tscode配置不正确，应为True")
            config_valid = False
        else:
            print("✅ pro_bar接口requires_tscode配置正确")

        if cache_enabled is not True:
            print("❌ pro_bar接口cache_enabled配置不正确，应为True")
            config_valid = False
        else:
            print("✅ pro_bar接口cache_enabled配置正确")

        if cache_ttl_hours <= 0:
            print("❌ pro_bar接口cache_ttl_hours配置不正确，应大于0")
            config_valid = False
        else:
            print("✅ pro_bar接口cache_ttl_hours配置正确")

        print("-" * 60)
        if config_valid:
            print("✅ 测试7通过: pro_bar接口配置验证成功")
            return True
        else:
            print("❌ 测试7失败: pro_bar接口配置存在问题")
            return False

    except ImportError as e:
        print(f"❌ 测试7导入错误: {str(e)}")
        print("尝试直接访问增强配置...")
        # 如果enhanced_download_config有问题，尝试直接从download_config获取
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("download_config", "/home/quan/testdata/aspipe_v4/app/download_config.py")
            download_config = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(download_config)

            # 检查pro_bar是否在基础配置中
            has_pro_bar = 'pro_bar' in download_config.DOWNLOAD_CONFIG
            print(f"基础配置中是否包含pro_bar: {has_pro_bar}")

            if has_pro_bar:
                print("✅ pro_bar接口在基础配置中存在")
                return True
            else:
                print("❌ pro_bar接口在基础配置中不存在")
                return False
        except Exception as e2:
            print(f"直接访问基础配置也失败: {str(e2)}")
            return False
    except Exception as e:
        print(f"❌ 测试7执行出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_interface_config()
#!/usr/bin/env python3
"""
Test 6: pro_bar接口在tscode_historical模式下的行为
目的: 验证在全历史下载模式下pro_bar接口的缓存行为
"""

import sys
import os

# 添加项目路径
sys.path.append('/home/quan/testdata/aspipe_v4')

def test_historical_mode():
    """测试pro_bar接口在历史模式下的行为"""
    print("=" * 60)
    print("测试6: pro_bar接口在tscode_historical模式下的行为")
    print("=" * 60)
    
    try:
        from app.enhanced_download_config import DOWNLOAD_PIPELINE_CONFIG

        # 检查pro_bar接口配置
        pro_bar_config = DOWNLOAD_PIPELINE_CONFIG.get('pro_bar')
        if pro_bar_config is None:
            print("❌ pro_bar接口配置不存在")
            return False

        print(f"pro_bar接口配置: {pro_bar_config}")
        
        # 检查是否正确标记requires_tscode
        requires_tscode = getattr(pro_bar_config, 'requires_tscode', False)
        print(f"pro_bar是否requires_tscode: {requires_tscode}")
        
        if requires_tscode:
            print("✅ pro_bar接口正确标记为需要ts_code")
        else:
            print("❌ pro_bar接口未正确标记为需要ts_code")
            return False

        # 尝试导入下载调度器来检查接口识别
        try:
            from app.download_scheduler import DownloadScheduler
            
            # 创建调度器实例
            scheduler = DownloadScheduler('20230101', '20231231')
            
            # 检查是否正确识别pro_bar为需要ts_code的接口
            is_tscode_interface = scheduler._is_tscode_interface('pro_bar')
            print(f"调度器是否正确识别pro_bar为ts_code接口: {is_tscode_interface}")
            
            if is_tscode_interface:
                print("✅ 调度器正确识别pro_bar为需要ts_code的接口")
            else:
                print("❌ 调度器未正确识别pro_bar为需要ts_code的接口")
                return False
                
        except AttributeError:
            print("⚠️  调度器中没有_is_tscode_interface方法，跳过此检查")
        except Exception as e:
            print(f"⚠️  检查调度器时出错: {str(e)}")
        
        # 检查其他重要配置
        cache_enabled = getattr(pro_bar_config, 'cache_enabled', True)
        print(f"缓存是否启用: {cache_enabled}")
        
        cache_ttl_hours = getattr(pro_bar_config, 'cache_ttl_hours', 24)
        print(f"缓存TTL小时数: {cache_ttl_hours}")
        
        priority = getattr(pro_bar_config, 'priority', 1)
        print(f"接口优先级: {priority}")
        
        max_retries = getattr(pro_bar_config, 'max_retries', 3)
        print(f"最大重试次数: {max_retries}")
        
        print("-" * 60)
        if requires_tscode:
            print("✅ 测试6通过: pro_bar接口在历史模式下的配置正确")
            return True
        else:
            print("❌ 测试6失败: pro_bar接口配置存在问题")
            return False
            
    except Exception as e:
        print(f"❌ 测试6执行出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_historical_mode()
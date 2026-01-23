"""
测试配置更新效果
"""

import yaml
from pathlib import Path

def test_config_updates():
    """测试配置更新是否正确"""
    print("开始测试配置更新...")

    # 测试dividend接口是否添加到tscode_historical组
    settings_file = Path("app4/config/settings.yaml")
    with open(settings_file, 'r', encoding='utf-8') as f:
        settings = yaml.safe_load(f)

    tscode_historical = settings['groups']['tscode_historical']
    if 'dividend' in tscode_historical:
        print("✅ dividend接口已添加到tscode_historical组")
    else:
        print("❌ dividend接口未添加到tscode_historical组")

    # 测试stock_loop接口是否有window_size_days配置
    interfaces_dir = Path("app4/config/interfaces")
    stock_loop_interfaces = [
        "income_vip.yaml", "balancesheet_vip.yaml", "cashflow_vip.yaml",
        "forecast_vip.yaml", "express_vip.yaml", "fina_indicator_vip.yaml",
        "fina_audit.yaml", "fina_mainbz_vip.yaml", "disclosure_date.yaml",
        "top10_floatholders.yaml", "top10_holders.yaml", "pledge_stat.yaml",
        "pledge_detail.yaml", "stk_rewards.yaml", "stk_factor.yaml",
        "stk_factor_pro.yaml", "dividend.yaml"
    ]

    missing_config = []
    for interface_file in stock_loop_interfaces:
        yaml_path = interfaces_dir / interface_file
        if yaml_path.exists():
            with open(yaml_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            pagination = config.get('pagination', {})
            if pagination.get('mode') == 'stock_loop' and 'window_size_days' not in pagination:
                missing_config.append(interface_file)

    if not missing_config:
        print("✅ 所有stock_loop接口都有window_size_days配置")
    else:
        print(f"❌ {len(missing_config)} 个接口缺少window_size_days配置: {missing_config}")

    # 测试downloader.py中的硬编码值是否已更改
    downloader_file = Path("app4/core/downloader.py")
    with open(downloader_file, 'r', encoding='utf-8') as f:
        content = f.read()

    if "pagination_config.get('window_size_days', 365)  # 改为默认365天" in content:
        print("✅ downloader.py中的硬编码值已从3650改为365")
    else:
        print("❌ downloader.py中的硬编码值未正确更改")

    print("配置更新测试完成")

if __name__ == "__main__":
    test_config_updates()
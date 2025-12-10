#!/usr/bin/env python3
"""
Test script for the 16 missing interfaces implementation
Tests the integration with all downloader components
"""
import logging
import sys
import os

# Add app directory to Python path
app_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app')
sys.path.insert(0, app_dir)

from config import TUSHARE_POINTS
from tushare_api import TuShareDownloader
from score_based_downloader import ScoreBasedDownloader
from date_range_downloader import DateRangeDownloader
from enhanced_main_downloader import EnhancedMainDownloader

def setup_logging():
    """Setup logging for test script"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

def test_tushare_api_methods():
    """Test that all new methods exist in TuShareDownloader"""
    print("\n" + "="*60)
    print("TESTING TUSHARE API DOWNLOADER")
    print("="*60)
    
    downloader = TuShareDownloader()
    
    # List of new methods to test
    new_methods = [
        'download_stock_st',
        'download_bak_basic',
        'download_moneyflow_dc',
        'download_moneyflow_ths',
        'download_moneyflow_ind_dc',
        'download_moneyflow_mkt_dc',
        'download_moneyflow_cnt_ths',
        'download_moneyflow_ind_ths',
        'download_top10_floatholders',
        'download_stk_factor',
        'download_stk_factor_pro',
        'download_cyq_perf',
        'download_cyq_chips',
        'download_report_rc',
        'download_stk_surv',
        'download_broker_recommend'
    ]
    
    print(f"Current user points: {TUSHARE_POINTS}")
    print("\nChecking if new methods exist...")
    
    missing_methods = []
    for method in new_methods:
        if hasattr(downloader, method):
            print(f"✅ {method}: Method exists")
        else:
            print(f"❌ {method}: Method missing")
            missing_methods.append(method)
    
    if missing_methods:
        print(f"\nMissing methods: {missing_methods}")
        return False
    else:
        print("\n✅ All 16 new methods successfully added to TuShareDownloader")
        return True

def test_score_config():
    """Test that score config includes new interfaces"""
    print("\n" + "="*60)
    print("TESTING SCORE CONFIG")
    print("="*60)
    
    from score_config import SCORE_REQUIREMENTS, get_available_data_types
    
    # Check if new interfaces are properly categorized
    expected_interfaces = {
        3000: {
            'basic': ['stock_st'],
            'holders': ['top10_floatholders']
        },
        5000: {
            'basic': ['bak_basic'],
            'daily': ['stk_factor', 'stk_factor_pro'],
            'market_structure': ['cyq_perf', 'cyq_chips'],
            'funds': ['moneyflow_dc', 'moneyflow_ths', 'moneyflow_ind_dc', 'moneyflow_mkt_dc', 
                     'moneyflow_cnt_ths', 'moneyflow_ind_ths'],
            'research': ['report_rc', 'stk_surv', 'broker_recommend'],
            'others': ['broker_recommend']
        },
        2000: {
            'others': ['broker_recommend']
        }
    }
    
    all_found = True
    
    for score, categories in expected_interfaces.items():
        print(f"\nChecking score level {score}:")
        for category, interfaces in categories.items():
            if score not in SCORE_REQUIREMENTS:
                print(f"  ❌ Score level {score} not defined")
                all_found = False
                continue
                
            if category not in SCORE_REQUIREMENTS[score]:
                print(f"  ❌ Category {category} not defined for score {score}")
                all_found = False
                continue
            
            for interface in interfaces:
                if interface in SCORE_REQUIREMENTS[score][category]:
                    print(f"    ✅ {interface}: Found in {category}")
                else:
                    print(f"    ❌ {interface}: Missing from {category}")
                    all_found = False
    
    # Test get_available_data_types
    print("\nTesting get_available_data_types...")
    available = get_available_data_types(TUSHARE_POINTS)
    
    # Check if some new interfaces are available based on current score
    expected_available = []
    if TUSHARE_POINTS >= 5000:
        expected_available.extend(['stock_st', 'bak_basic', 'stk_factor', 'stk_factor_pro', 
                              'cyq_perf', 'cyq_chips', 'moneyflow_dc', 'moneyflow_ths',
                              'moneyflow_ind_dc', 'moneyflow_mkt_dc', 'moneyflow_cnt_ths',
                              'moneyflow_ind_ths', 'report_rc', 'stk_surv', 'broker_recommend'])
    elif TUSHARE_POINTS >= 3000:
        expected_available.extend(['stock_st', 'broker_recommend'])
    elif TUSHARE_POINTS >= 2000:
        expected_available.extend(['broker_recommend'])
    
    found_available = 0
    for interface in expected_available:
        for category_types in available.values():
            if interface in category_types:
                found_available += 1
                print(f"    ✅ {interface}: Available for {TUSHARE_POINTS} points")
                break
    
    print(f"\n{found_available}/{len(expected_available)} expected interfaces are available")
    
    return all_found

def test_downloaders_integration():
    """Test that all downloaders can handle new interfaces"""
    print("\n" + "="*60)
    print("TESTING DOWNLOADERS INTEGRATION")
    print("="*60)
    
    # Test ScoreBasedDownloader
    print("\n1. Testing ScoreBasedDownloader...")
    try:
        score_downloader = ScoreBasedDownloader()
        available = score_downloader.get_available_data_types()
        
        # Check if download methods exist for new interfaces
        new_interfaces = ['stock_st', 'bak_basic', 'moneyflow_dc', 'moneyflow_ths', 
                         'moneyflow_ind_dc', 'moneyflow_mkt_dc', 'moneyflow_cnt_ths', 
                         'moneyflow_ind_ths', 'top10_floatholders', 'stk_factor', 
                         'stk_factor_pro', 'cyq_perf', 'cyq_chips', 'report_rc', 
                         'stk_surv', 'broker_recommend']
        
        missing_methods = []
        for interface in new_interfaces:
            if hasattr(score_downloader, f'download_{interface}'):
                print(f"    ✅ download_{interface}: Method exists")
            else:
                print(f"    ❌ download_{interface}: Method missing")
                missing_methods.append(interface)
        
        if missing_methods:
            print(f"  Missing methods in ScoreBasedDownloader: {missing_methods}")
            return False
        else:
            print("  ✅ All new download methods exist in ScoreBasedDownloader")
    except Exception as e:
        print(f"  ❌ Error testing ScoreBasedDownloader: {e}")
        return False
    
    # Test DateRangeDownloader
    print("\n2. Testing DateRangeDownloader...")
    try:
        date_downloader = DateRangeDownloader('20231201', '20231202')
        # Test _create_download_task_list
        tasks = date_downloader._create_download_task_list()
        task_names = [task[0] for task in tasks]
        
        # Check if new interfaces are included
        expected_in_tasks = []
        if TUSHARE_POINTS >= 5000:
            expected_in_tasks.extend(['stock_st', 'bak_basic', 'moneyflow_dc', 'moneyflow_ths', 
                                   'moneyflow_ind_dc', 'moneyflow_mkt_dc', 'moneyflow_cnt_ths', 
                                   'moneyflow_ind_ths', 'top10_floatholders', 'stk_factor', 
                                   'stk_factor_pro', 'cyq_perf', 'cyq_chips'])
        elif TUSHARE_POINTS >= 3000:
            expected_in_tasks.extend(['stock_st'])
        
        found_in_tasks = 0
        for interface in expected_in_tasks:
            if interface in task_names:
                found_in_tasks += 1
                print(f"    ✅ {interface}: Included in download tasks")
            else:
                print(f"    ❌ {interface}: Not in download tasks")
        
        print(f"  {found_in_tasks}/{len(expected_in_tasks)} expected interfaces in task list")
        
    except Exception as e:
        print(f"  ❌ Error testing DateRangeDownloader: {e}")
        return False
    
    # Test EnhancedMainDownloader
    print("\n3. Testing EnhancedMainDownloader...")
    try:
        enhanced_downloader = EnhancedMainDownloader()
        tasks = enhanced_downloader._create_download_task_list()
        task_names = [task[0] for task in tasks]
        
        # Check if new interfaces are included
        found_in_enhanced = 0
        for interface in expected_in_tasks:
            if interface in task_names:
                found_in_enhanced += 1
                print(f"    ✅ {interface}: Included in enhanced downloader tasks")
            else:
                print(f"    ❌ {interface}: Not in enhanced downloader tasks")
        
        print(f"  {found_in_enhanced}/{len(expected_in_tasks)} expected interfaces in enhanced downloader")
        
    except Exception as e:
        print(f"  ❌ Error testing EnhancedMainDownloader: {e}")
        return False
    
    return True

def main():
    """Main test function"""
    setup_logging()
    
    print(f"\n{'='*60}")
    print(f"MISSING INTERFACES IMPLEMENTATION TEST")
    print(f"{'='*60}")
    print(f"Current TuShare Points: {TUSHARE_POINTS}")
    
    # Run all tests
    api_test = test_tushare_api_methods()
    config_test = test_score_config()
    integration_test = test_downloaders_integration()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"TuShare API Methods Test: {'PASS' if api_test else 'FAIL'}")
    print(f"Score Config Test: {'PASS' if config_test else 'FAIL'}")
    print(f"Downloaders Integration Test: {'PASS' if integration_test else 'FAIL'}")
    
    if api_test and config_test and integration_test:
        print("\n✅ All tests PASSED! Implementation is complete.")
        return 0
    else:
        print("\n❌ Some tests FAILED. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
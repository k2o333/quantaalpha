"""
Enhanced main orchestrator for score-based Tushare data downloads
with smart error handling and prioritization
"""
import logging
from typing import Dict, List, Tuple
import pandas as pd
from config import TUSHARE_POINTS
from tushare_api import TuShareDownloader
from score_based_downloader import ScoreBasedDownloader
from data_storage import save_to_parquet
from score_config import get_available_data_types
from download_config import DOWNLOAD_CONFIG
import time


class EnhancedMainDownloader:
    def __init__(self):
        self.downloader = TuShareDownloader()
        self.score_downloader = ScoreBasedDownloader()
        self.logger = logging.getLogger(__name__)

        # Initialize StockListManager to avoid duplicate stock_basic calls
        from stock_list_manager import init_stock_manager
        self.stock_manager = init_stock_manager(
            downloader=self.downloader,
            cache_dir="cache",
            max_cache_age_hours=24
        )

        self.logger.info(f"EnhancedMainDownloader initialized with {TUSHARE_POINTS} points")
        self.available_types = self.score_downloader.get_available_data_types()
        self.logger.info(f"Available data types: {self.available_types}")

    def download_all_score_appropriate_data(self) -> Dict[str, int]:
        """
        Download all data appropriate for the user's score level,
        with smart error handling and prioritization
        """
        results = {}

        self.logger.info("Starting download of all score-appropriate data with smart prioritization...")

        # Create a priority queue of download tasks
        download_tasks = self._create_download_task_list()

        # Track failed attempts and completed tasks
        failed_attempts = {}
        completed_tasks = set()

        original_task_count = len(download_tasks)
        consecutive_failed_cycles = 0  # Track if we're in a loop with no progress

        while len(completed_tasks) < original_task_count:
            if not download_tasks:
                break

            # Check if all remaining tasks have reached max retries
            all_max_retries_reached = True
            for task_name, _, max_retries in download_tasks:
                if failed_attempts.get(task_name, 0) < max_retries:
                    all_max_retries_reached = False
                    break

            if all_max_retries_reached:
                # All remaining tasks have reached max retries, exit
                self.logger.info("All remaining tasks have reached max retry attempts, exiting.")
                break

            task_name, download_func, max_retries = download_tasks[0]

            # Check if this interface has already failed max_retries times
            if failed_attempts.get(task_name, 0) >= max_retries:
                # Move to end since it's already failed max retries
                download_tasks.append(download_tasks.pop(0))
                continue

            task_completed = False

            try:
                self.logger.info(f"Attempting to download {task_name}...")
                df = download_func()

                if not df.empty:
                    # Generate filename based on task type
                    filename = self._generate_filename(task_name)
                    file_path = save_to_parquet(df, filename)
                    results[task_name] = len(df)
                    self.logger.info(f"Successfully saved {task_name} data to {file_path}")
                    task_completed = True
                else:
                    self.logger.warning(f"Downloaded empty data for {task_name}")
                    task_completed = True  # Consider empty as completed, not failed

            except Exception as e:
                # Increment failed attempts for this interface
                failed_attempts[task_name] = failed_attempts.get(task_name, 0) + 1
                self.logger.error(f"Error downloading {task_name} (attempt {failed_attempts[task_name]}/{max_retries}): {e}")

                if failed_attempts[task_name] >= max_retries:
                    self.logger.warning(f"Max retries reached for {task_name}, moving to end of queue permanently")

                # Always move to end after an error (whether max retries reached or not)
                download_tasks.append(download_tasks.pop(0))

            finally:
                if task_completed:
                    completed_tasks.add(task_name)
                    # Remove from the front of the queue
                    download_tasks.pop(0)

        self.logger.info(f"Download completed. Results: {results}")
        return results

    def _create_download_task_list(self) -> List[Tuple[str, callable, int]]:
        """
        Create a list of download tasks with their associated functions and retry limits
        """
        tasks = []

        # Basic information downloads (high priority)
        if ('stock_basic' in self.available_types.get('basic', []) and
            DOWNLOAD_CONFIG.get('stock_basic', True)):
            tasks.append(('stock_basic', self.downloader.download_stock_basic, 3))

        if ('trade_cal' in self.available_types.get('basic', []) and
            DOWNLOAD_CONFIG.get('trade_cal', True)):
            tasks.append(('trade_cal', self._download_trade_cal, 3))

        if ('new_share' in self.available_types.get('basic', []) and
            DOWNLOAD_CONFIG.get('new_share', True)):
            tasks.append(('new_share', self.downloader.download_new_share, 3))

        # Add new basic interfaces
        if ('stock_st' in self.available_types.get('basic', []) and
            DOWNLOAD_CONFIG.get('stock_st', True)):
            tasks.append(('stock_st', self.downloader.download_stock_st, 3))

        if ('bak_basic' in self.available_types.get('basic', []) and
            DOWNLOAD_CONFIG.get('bak_basic', True)):
            tasks.append(('bak_basic', self.downloader.download_bak_basic, 3))

        # Daily data downloads (high priority)
        if ('daily_basic' in self.available_types.get('daily', []) and
            DOWNLOAD_CONFIG.get('daily_basic', True)):
            tasks.append(('daily_basic', self.downloader.download_daily_basic, 3))

        # Financial data downloads (medium priority - can be problematic)
        if ('income' in self.available_types.get('financial', []) and
            DOWNLOAD_CONFIG.get('income', True)):
            tasks.append(('income', self._download_income_safe, 3))

        if ('balancesheet' in self.available_types.get('financial', []) and
            DOWNLOAD_CONFIG.get('balancesheet', True)):
            tasks.append(('balancesheet', self._download_balancesheet_safe, 3))

        if ('cashflow' in self.available_types.get('financial', []) and
            DOWNLOAD_CONFIG.get('cashflow', True)):
            tasks.append(('cashflow', self._download_cashflow_safe, 3))

        if ('fina_indicator' in self.available_types.get('financial', []) and
            DOWNLOAD_CONFIG.get('fina_indicator', True)):
            tasks.append(('fina_indicator', self._download_fina_indicator_safe, 3))

        # Money flow data downloads
        if ('moneyflow' in self.available_types.get('funds', []) and
            DOWNLOAD_CONFIG.get('moneyflow', True)):
            tasks.append(('moneyflow', self._download_moneyflow_safe, 3))

        # Add new money flow interfaces
        money_flow_types = ['moneyflow_dc', 'moneyflow_ths', 'moneyflow_ind_dc', 'moneyflow_mkt_dc',
                           'moneyflow_cnt_ths', 'moneyflow_ind_ths']
        for mf_type in money_flow_types:
            if (mf_type in self.available_types.get('funds', []) and
                DOWNLOAD_CONFIG.get(mf_type, True)):
                tasks.append((mf_type, getattr(self.downloader, f'download_{mf_type}'), 3))

        # Holder data downloads
        if ('top10_holders' in self.available_types.get('holders', []) and
            DOWNLOAD_CONFIG.get('top10_holders', True)):
            tasks.append(('top10_holders', self._download_top10_holders_safe, 3))

        if ('top10_floatholders' in self.available_types.get('holders', []) and
            DOWNLOAD_CONFIG.get('top10_floatholders', True)):
            tasks.append(('top10_floatholders', self._download_top10_floatholders_safe, 3))

        # Technical analysis and market structure data
        # Check both daily and market_structure categories for these interfaces
        tech_types = ['stk_factor', 'stk_factor_pro', 'cyq_perf', 'cyq_chips']
        for tech_type in tech_types:
            if ((tech_type in self.available_types.get('market_structure', []) or
                 tech_type in self.available_types.get('daily', [])) and
                DOWNLOAD_CONFIG.get(tech_type, True)):
                tasks.append((tech_type, getattr(self.downloader, f'download_{tech_type}'), 3))

        # Research data downloads
        research_types = ['report_rc', 'stk_surv', 'broker_recommend']
        for research_type in research_types:
            if (research_type in self.available_types.get('research', []) and
                DOWNLOAD_CONFIG.get(research_type, True)):
                if research_type == 'broker_recommend':
                    tasks.append((research_type, self._download_broker_recommend_safe, 3))
                else:
                    tasks.append((research_type, getattr(self.downloader, f'download_{research_type}'), 3))

        # Other data downloads
        if ('stk_rewards' in self.available_types.get('others', []) and
            DOWNLOAD_CONFIG.get('stk_rewards', True)):
            tasks.append(('stk_rewards', self._download_stk_rewards_safe, 3))

        if ('stk_managers' in self.available_types.get('others', []) and
            DOWNLOAD_CONFIG.get('stk_managers', True)):
            tasks.append(('stk_managers', self._download_stk_managers_safe, 3))

        if ('namechange' in self.available_types.get('others', []) and
            DOWNLOAD_CONFIG.get('namechange', True)):
            tasks.append(('namechange', self._download_namechange_safe, 3))

        # Stock company info
        if ('stock_company' in self.available_types.get('basic', []) and
            DOWNLOAD_CONFIG.get('stock_company', True)):
            tasks.append(('stock_company', self._download_stock_company_combined, 3))

        # Log which interfaces will be skipped due to configuration
        for data_type in DOWNLOAD_CONFIG:
            if not DOWNLOAD_CONFIG[data_type]:
                self.logger.info(f"Skipping interface {data_type} (configured as not to download)")

        return tasks

    def _download_trade_cal(self) -> pd.DataFrame:
        """Helper to download trade calendar"""
        return self.downloader.download_trade_cal()

    def _download_income_safe(self) -> pd.DataFrame:
        """Safe download of income with error handling"""
        # Try with a specific stock code if possible, otherwise just with period
        try:
            return self.downloader.download_income(period='20231231', ts_code='000001.SZ')
        except Exception:
            # If specific stock fails, try with just period
            try:
                return self.downloader.download_income(period='20231231')
            except Exception:
                return pd.DataFrame()

    def _download_balancesheet_safe(self) -> pd.DataFrame:
        """Safe download of balance sheet with error handling"""
        try:
            return self.downloader.download_balancesheet(period='20231231', ts_code='000001.SZ')
        except Exception:
            # If specific stock fails, try with just period
            try:
                return self.downloader.download_balancesheet(period='20231231')
            except Exception:
                return pd.DataFrame()

    def _download_cashflow_safe(self) -> pd.DataFrame:
        """Safe download of cashflow with error handling"""
        try:
            return self.downloader.download_cashflow(period='20231231', ts_code='000001.SZ')
        except Exception:
            # If specific stock fails, try with just period
            try:
                return self.downloader.download_cashflow(period='20231231')
            except Exception:
                return pd.DataFrame()

    def _download_fina_indicator_safe(self) -> pd.DataFrame:
        """Safe download of financial indicators with error handling"""
        try:
            return self.downloader.download_fina_indicator(period='20231231', ts_code='000001.SZ')
        except Exception:
            # If specific stock fails, try with just period
            try:
                return self.downloader.download_fina_indicator(period='20231231')
            except Exception:
                return pd.DataFrame()
    
    def _download_top10_holders_safe(self) -> pd.DataFrame:
        """Safe download of top10_holders with error handling"""
        # Get a sample stock
        from stock_list_manager import StockListManager
        stock_df = StockListManager().get_stock_basic()
        if not stock_df.empty and len(stock_df) > 0:
            ts_code = stock_df.iloc[0]['ts_code']
            return self.downloader.download_top10_holders(ts_code=ts_code, period='20231231')
        else:
            return pd.DataFrame()
    
    def _download_top10_floatholders_safe(self) -> pd.DataFrame:
        """Safe download of top10_floatholders with error handling"""
        # Get a sample stock
        from stock_list_manager import StockListManager
        stock_df = StockListManager().get_stock_basic()
        if not stock_df.empty and len(stock_df) > 0:
            ts_code = stock_df.iloc[0]['ts_code']
            return self.downloader.download_top10_floatholders(ts_code=ts_code, period='20231231')
        else:
            return pd.DataFrame()
    
    def _download_broker_recommend_safe(self) -> pd.DataFrame:
        """Safe download of broker_recommend with error handling"""
        # Use a specific month instead of date range
        return self.downloader.download_broker_recommend(month='202311')
    
    def _download_moneyflow_safe(self) -> pd.DataFrame:
        """Safe download of moneyflow with error handling"""
        return self.downloader.download_moneyflow(trade_date='20231201')
    
    def _download_stk_rewards_safe(self) -> pd.DataFrame:
        """Safe download of stk_rewards with error handling"""
        # Need to first get a stock code to download
        from stock_list_manager import StockListManager
        stock_df = StockListManager().get_stock_basic()
        if not stock_df.empty and len(stock_df) > 0:
            ts_code = stock_df.iloc[0]['ts_code']
            return self.downloader.download_stk_rewards(ts_code=ts_code)
        else:
            return pd.DataFrame()
    
    def _download_stk_managers_safe(self) -> pd.DataFrame:
        """Safe download of stk_managers with error handling"""
        # Get a sample stock
        from stock_list_manager import StockListManager
        stock_df = StockListManager().get_stock_basic()
        if not stock_df.empty and len(stock_df) > 0:
            ts_code = stock_df.iloc[0]['ts_code']
            return self.downloader.download_stk_managers(ts_code=ts_code)
        else:
            return pd.DataFrame()
    
    def _download_namechange_safe(self) -> pd.DataFrame:
        """Safe download of namechange with error handling"""
        # Get a sample stock
        from stock_list_manager import StockListManager
        stock_df = StockListManager().get_stock_basic()
        if not stock_df.empty and len(stock_df) > 0:
            ts_code = stock_df.iloc[0]['ts_code']
            return self.downloader.download_namechange(ts_code=ts_code)
        else:
            return self.downloader.download_namechange()
    
    def _download_stock_company_combined(self) -> pd.DataFrame:
        """
        Download stock company info for both exchanges and combine
        """
        try:
            # Download for both exchanges
            sse_data = self.downloader.download_stock_company(exchange='SSE')
            szse_data = self.downloader.download_stock_company(exchange='SZSE')
            
            # Combine the data if both succeed
            if not sse_data.empty and not szse_data.empty:
                combined_df = pd.concat([sse_data, szse_data], ignore_index=True)
            elif not sse_data.empty:
                combined_df = sse_data
            elif not szse_data.empty:
                combined_df = szse_data
            else:
                combined_df = pd.DataFrame()
            
            return combined_df
        except Exception as e:
            self.logger.error(f"Error downloading stock company combined: {e}")
            return pd.DataFrame()

    def _generate_filename(self, task_name: str) -> str:
        """
        Generate appropriate filename based on task name and current date
        """
        import datetime
        current_date = datetime.datetime.now().strftime('%Y%m%d')
        
        if task_name in ['daily_basic', 'moneyflow', 'stock_st', 
                           'moneyflow_dc', 'moneyflow_ths', 'moneyflow_ind_dc', 'moneyflow_mkt_dc',
                           'moneyflow_cnt_ths', 'moneyflow_ind_ths',
                           'stk_factor', 'stk_factor_pro', 'cyq_perf', 'cyq_chips']:
            # These require a date parameter
            return f"{task_name}_{current_date}"
        elif task_name in ['income', 'balancesheet', 'cashflow', 'fina_indicator',
                           'top10_holders', 'top10_floatholders', 
                           'report_rc', 'stk_surv']:
            # These are financial reports
            return f"{task_name}_20231231"
        elif task_name == 'broker_recommend':
            # This uses a date range
            return f"{task_name}_20231231"
        else:
            return task_name

    def get_score_summary(self) -> Dict:
        """
        Get summary of user's score and available data
        """
        return {
            'user_points': TUSHARE_POINTS,
            'available_categories': {cat: types for cat, types in self.available_types.items() if types},
            'can_access_vip': TUSHARE_POINTS >= 5000
        }


def main():
    """
    Main function to run the enhanced score-based download system
    """
    import sys
    import os
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    downloader = EnhancedMainDownloader()
    
    # Print score summary
    summary = downloader.get_score_summary()
    print("\n" + "="*50)
    print(f"TUSHARE SCORE SUMMARY")
    print(f"User Points: {summary['user_points']}")
    print(f"Can Access VIP APIs: {summary['can_access_vip']}")
    print("Available Categories:")
    for cat, types in summary['available_categories'].items():
        print(f"  {cat}: {len(types)} types")
        for t in types:
            print(f"    - {t}")
    print("="*50 + "\n")
    
    # Perform downloads
    results = downloader.download_all_score_appropriate_data()
    
    print("\n" + "="*50)
    print("DOWNLOAD RESULTS SUMMARY")
    for data_type, count in results.items():
        print(f"{data_type}: {count} records")
    print("="*50)


if __name__ == "__main__":
    main()
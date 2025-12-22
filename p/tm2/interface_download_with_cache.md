# 单纯按股票代码的接口全历史下载与缓存方案

## 概述

本文档描述了针对以下5个必须传递股票代码参数的接口实现全历史下载与缓存功能的方案，基于现有代码库的缓存机制：

1. `stk_rewards` - 管理层薪酬和持股
2. `top10_holders` - 前十大股东
3. `pledge_detail` - 股权质押明细
4. `fina_audit` - 财务审计意见
5. `pro_bar` - 复权行情

## 方案设计

### 1. 主程序参数扩展

在 `main.py` 中扩展参数支持，仅在传递特定参数时启用这5个接口的下载：

```python
# 新增参数
--holders-data  # 启用 stk_rewards, top10_holders, pledge_detail, fina_audit
--pro-bar-only  # 仅启用 pro_bar
--all-historical # 下载全历史数据而非指定日期范围
```

### 2. 接口分类与下载策略

#### 2.1 无分页限制接口
- `stk_rewards`: 直接调用接口获取全历史
- `top10_holders`: 不传日期参数获取全历史
- `fina_audit`: 不传日期参数获取全历史
- `pro_bar`: 获取股票上市日至当前日期全历史

#### 2.2 有限制接口
- `pledge_detail`: 通过分页或日期分批获取（单次限制1000条）

### 3. 现有缓存机制分析

根据现有代码库，缓存机制包括：

#### 3.1 数据存储模块 (data_storage.py)
- `save_to_parquet()`: 保存数据到Parquet格式
- `load_from_parquet()`: 从Parquet格式加载数据
- `is_data_cached()`: 检查数据是否已缓存
- `get_cache_path()`: 生成标准化缓存路径
- `is_data_fresh()`: 检查缓存是否新鲜

#### 3.2 股票列表管理器 (stock_list_manager.py)
- 单例模式实现缓存管理
- 包含缓存验证、加载、保存功能
- 支持缓存过期时间控制

#### 3.3 日期范围下载器 (date_range_downloader.py)
- 使用缓存机制下载日度数据
- 检查缓存后决定是否重新下载

### 4. 为特定接口实现缓存

#### 4.1 创建接口特定缓存管理器

基于现有缓存机制，为这5个接口创建缓存功能：

```python
# 在 interfaces/holders_data.py 中添加缓存功能
class CachedHoldersDataDownloader:
    def __init__(self, pro_api, cache_enabled=True, cache_ttl_hours=24):
        self.pro = pro_api
        self.cache_enabled = cache_enabled
        self.cache_ttl_hours = cache_ttl_hours
        self.logger = logging.getLogger(__name__)

    def _get_cache_path(self, interface_name: str, ts_code: str) -> str:
        """生成接口特定的缓存路径"""
        cache_dir = Path("cache") / interface_name
        cache_dir.mkdir(parents=True, exist_ok=True)
        return str(cache_dir / f"{ts_code}.parquet")

    def _is_cache_valid(self, cache_path: str) -> bool:
        """检查缓存是否有效"""
        if not Path(cache_path).exists():
            return False
        file_mtime = datetime.fromtimestamp(Path(cache_path).stat().st_mtime)
        cache_age = datetime.now() - file_mtime
        return cache_age < timedelta(hours=self.cache_ttl_hours)

    def download_stk_rewards_with_cache(self, ts_code: str) -> pd.DataFrame:
        """带缓存的stk_rewards下载"""
        if not self.cache_enabled:
            return self.download_stk_rewards(ts_code)

        cache_path = self._get_cache_path("stk_rewards", ts_code)

        # 检查缓存
        if self._is_cache_valid(cache_path):
            try:
                df = pd.read_parquet(cache_path)
                self.logger.info(f"从缓存加载stk_rewards数据: {ts_code}")
                return df
            except Exception as e:
                self.logger.warning(f"缓存加载失败: {e}")

        # 缓存无效或不存在，下载新数据
        df = self.download_stk_rewards(ts_code)

        # 保存到缓存
        if not df.empty:
            try:
                df.to_parquet(cache_path, index=False)
                self.logger.info(f"保存stk_rewards数据到缓存: {ts_code}")
            except Exception as e:
                self.logger.warning(f"缓存保存失败: {e}")

        return df
```

#### 4.2 为其他接口实现类似缓存

为`top10_holders`、`pledge_detail`、`fina_audit`、`pro_bar`等接口实现类似的缓存功能。

### 5. 配置管理

#### 5.1 增强下载配置 (enhanced_download_config.py)
利用现有配置结构，为这些接口添加缓存配置：

```python
# 在 enhanced_download_config.py 中为这些接口添加缓存配置
{
    'stk_rewards': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('stk_rewards', True),
        priority=DataTypePriority.LOW,
        max_retries=2,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=2000,
        cache_enabled=True,
        cache_ttl_hours=24
    ),
    'top10_holders': InterfaceConfig(
        # 类似配置
    ),
    # ... 其他接口
}
```

### 6. 集成到主流程

#### 6.1 修改主下载器
在ScoreBasedDownloader或TuShareDownloader中集成缓存功能：

```python
def download_stk_rewards_cached(self, ts_code: str) -> pd.DataFrame:
    """使用缓存机制下载stk_rewards数据"""
    cache_manager = CachedHoldersDataDownloader(self.pro)
    return cache_manager.download_stk_rewards_with_cache(ts_code)
```

### 7. 命令行使用示例

```bash
# 仅下载holders相关数据（全历史）
python app/main.py --holders-data --all-historical

# 仅下载pro_bar（全历史）
python app/main.py --pro-bar-only --all-historical

# 同时下载holders和pro_bar（全历史）
python app/main.py --holders-data --pro-bar-only --all-historical

# 带自定义参数下载
python app/main.py --holders-data --all-historical --start-date 20200101
```

### 8. 并发控制

- 利用现有并发机制，按股票代码批量处理
- 控制并发数，防止API调用超限
- 利用缓存减少重复API调用

### 9. 安全与容错

- 使用现有重试机制
- 缓存失败不影响主流程
- 数据验证与清理

### 10. 监控与日志

- 使用现有日志系统
- 记录缓存命中情况
- 监控下载性能

该方案基于现有代码库的缓存机制，为特定接口恢复和增强缓存功能，提高数据下载效率。
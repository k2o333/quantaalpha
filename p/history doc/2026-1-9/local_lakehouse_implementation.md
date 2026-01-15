# 本地轻量级数据湖 (Local Lakehouse) 实施方案

## 1. 核心目录规划

根据你的要求，我们将目录逻辑划分为 **Landing Zone (着陆区)** 和 **Serving Zone (服务区)**。

*   **着陆区 (Landing Zone)**:
    *   **路径**: `/home/quan/testdata/aspipe_v4/data`
    *   **用途**: 存放下载器刚刚抓取的原始数据文件。这里的数据是“碎片化”的，可能按天、按单只股票存储，文件名和结构较乱，只求**写入速度**。
*   **服务区 (Serving Zone)**:
    *   **路径**: `/home/quan/testdata/aspipe_v4/dataff`
    *   **用途**: 存放经过治理、去重、排序、分区的 Parquet 文件。这里的数据是“规整”的，专为 Polars/DuckDB 的**读取效率**优化。
*   **元数据存储 (Metadata)**:
    *   **路径**: `/home/quan/testdata/aspipe_v4/app4/data/metadata.duckdb` (建议新建)
    *   **用途**: DuckDB 的数据库文件，用于记录哪些数据已经下载、哪些已经合并。

---

## 2. DuckDB 疑问解答

### 2.1 DuckDB 需要另外维护文件吗？
**需要。**
DuckDB 是嵌入式数据库（类似 SQLite），它不需要启动服务器进程，但需要一个持久化的文件来存储数据表。
*   你将在代码中指定一个路径，如 `duckdb.connect('/home/quan/testdata/aspipe_v4/app4/data/metadata.duckdb')`。
*   如果该文件不存在，DuckDB 会自动创建它。
*   这个文件就是你的“目录册”，非常轻量，方便备份。

---

## 3. 详细工作流 (Workflow)

### 3.1 阶段一：下载 (Download to Landing)

**目标**: 快速把数据抓下来，不关心文件碎片化。

1.  **查询元数据**:
    *   下载器启动前，连接 `metadata.duckdb`。
    *   查询表 `download_status`，获取某只股票 (`ts_code`) 某接口 (`api_name`) 上次下载到的 `end_date`。
    *   确定本次下载区间：`start_date = last_end_date + 1`。

2.  **执行下载**:
    *   调用 Tushare API 获取 DataFrame。
    *   **关键动作**: 直接保存为 Parquet 到 `data` 目录 (Landing Zone)。
    *   **命名建议**: 为了方便后续处理，文件名应包含必要信息。
        *   例如: `/home/quan/testdata/aspipe_v4/data/daily/000001.SZ_20240101_20240110.parquet`
    *   *注意：此时不要去修改 `dataff` 中的大文件，也不要执行复杂的去重逻辑，只管追加写小文件。*

### 3.2 阶段二：数据整理 (ETL / Compaction)

**目标**: 将 `data` 中的碎片合并到 `dataff`，并清理碎片。

#### **什么时候触发？ (Trigger Strategy)**

推荐采用 **“批次后触发 (Post-Batch Trigger)”** 策略。

*   **不要** 每下载一只股票就整理一次（IO开销太大）。
*   **建议方案**:
    1.  **日常更新场景**: 下载脚本执行完所有股票的当天任务后，最后调用一次 `organize_data()` 函数。
    2.  **历史补录场景**: 如果是一次性补录 10 年数据，建议每下载完成 500-1000 只股票，或者每隔 1 小时，触发一次整理。

#### **整理逻辑 (The Compaction Logic)**

该逻辑由一个独立的 `Processor` 类处理：

1.  **扫描 (Scan)**:
    *   扫描 `data` 目录下的所有新文件。
    *   提取涉及的年份（例如新下载的数据只包含 2024 年）。
2.  **读取与合并 (Load & Merge)**:
    *   利用 Polars 的 `LazyFrame`。
    *   `df_landing = pl.scan_parquet("data/daily/*.parquet")`
    *   `df_serving = pl.scan_parquet("dataff/daily/year=2024/*.parquet")` (如果存在)
    *   `df_final = pl.concat([df_serving, df_landing])`
3.  **清洗 (Clean)**:
    *   `df_final = df_final.unique(subset=['ts_code', 'trade_date'], keep='last')` (确保新下载的修正数据覆盖旧数据)
    *   **关键步骤**: `df_final = df_final.sort(['ts_code', 'trade_date'])` (这一步对 DuckDB 读取速度至关重要)
4.  **写入 (Write)**:
    *   将 `df_final` 写入 `dataff`，按年份分区。
    *   路径格式: `/home/quan/testdata/aspipe_v4/dataff/daily/year=2024/part-0.parquet`
    *   使用 `zstd` 压缩。
5.  **更新元数据 (Update Meta)**:
    *   在 `metadata.duckdb` 中更新状态，标记这些时间段的数据已归档。
6.  **清理 (Cleanup)**:
    *   删除 `data` 目录中已合并的源文件（保持 Landing Zone 清爽）。

---

## 4. 目录结构预览

```text
/home/quan/testdata/aspipe_v4/
├── app4/
│   └── data/
│       └── metadata.duckdb      <-- [新增] DuckDB 数据库文件 (元数据)
├── data/                        <-- [Landing Zone] 临时下载区
│   ├── daily/
│   │   ├── 000001.SZ_patch.parquet
│   │   └── 000002.SZ_patch.parquet
│   └── financial/
└── dataff/                      <-- [Serving Zone] 最终数据湖
    ├── daily/                   <-- 按接口/业务分类
    │   ├── year=2023/           <-- Hive 风格分区
    │   │   └── data.parquet     <-- 包含该年所有股票，且已排序
    │   ├── year=2024/
    │   │   └── data.parquet
    │   └── ...
    └── income/
        ├── year=2020/
        └── ...
```

---

## 5. 读取效率最高的使用方式 (Best Practice)

以后读取数据时，直接指向 `dataff` 目录，利用 Polars/DuckDB 的**分区裁剪 (Partition Pruning)** 和 **谓词下推 (Predicate Pushdown)**。

**Python (Polars) 示例**:
```python
import polars as pl

# 极速读取：Polars 会自动跳过 2024 年以外的文件夹
# 且因为文件内部已按 ts_code 排序，它能快速定位到 '000001.SZ' 的数据块
df = pl.scan_parquet("/home/quan/testdata/aspipe_v4/dataff/daily/**/*.parquet") \
    .filter(
        (pl.col("year") == 2024) & 
        (pl.col("ts_code") == "000001.SZ")
    ) \
    .collect()
```

**Python (DuckDB) 示例**:
```python
import duckdb

# DuckDB 可以直接把 parquet 文件夹当表查
# Hive 分区字段 (year) 会自动被识别为虚拟列，查询速度极快
sql = """
SELECT *
FROM '/home/quan/testdata/aspipe_v4/dataff/daily/**/*.parquet'
WHERE year = 2024 AND ts_code = '000001.SZ'
"""
df = duckdb.query(sql).df()
```

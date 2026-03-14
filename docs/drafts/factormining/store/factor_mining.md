因子挖掘流程接入 VNPY 的优化方案                                                                                   
  
  核心架构对比                                                                                                       
                  
  ┌──────────┬───────────────────┬───────────────────┬──────────────────────┐
  │   组件   │    原文档方案     │   VNPY 对应组件   │       集成建议       │
  ├──────────┼───────────────────┼───────────────────┼──────────────────────┤
  │ 回测引擎 │ Qlib              │ BacktestingEngine │ 需要桥接层           │
  ├──────────┼───────────────────┼───────────────────┼──────────────────────┤
  │ 数据存储 │ Parquet + Polars  │ Database 抽象层   │ 扩展 ParquetDatafeed │
  ├──────────┼───────────────────┼───────────────────┼──────────────────────┤
  │ 事件调度 │ 生产者-消费者队列 │ EventEngine       │ 直接复用             │
  ├──────────┼───────────────────┼───────────────────┼──────────────────────┤
  │ 策略执行 │ 无                │ CtaTemplate       │ 新增适配层           │
  └──────────┴───────────────────┴───────────────────┴──────────────────────┘

  ---
  1. 数据层集成优化

  ┌─────────────────────────────────────────────────────────────────┐
  │                      数据层架构优化                              │
  ├─────────────────────────────────────────────────────────────────┤
  │                                                                 │
  │ ┌──────────────┐ ┌──────────────┐    ┌──────────────────┐  │
  │  │ TuShare API  │───▶│  Parquet │───▶│ VNPY Datafeed │  │
  │  │ (aspipe_v4)  │    │  Storage     │    │ Adapter          │  │
  │ └──────────────┘    └──────────────┘ └────────┬─────────┘  │
  │                                                    │ │
  │                              ┌─────────────────────▼──────────┐ │
  │ │     VNPY Database Interface    │ │
  │                              │  - load_bar_data()             │ │
  │                              │  - save_bar_data()             │ │
  │                              │  - load_tick_data() │ │
  │ └─────────────────────┬──────────┘ │
  │                                                    │ │
  │  ┌──────────────┐    ┌──────────────┐    ┌────────▼─────────┐  │
  │  │ Factor       │◀───│ HistoryManager│◀───│ BacktestingEngine│  │
  │  │ Calculator   │    │ (VNPY)       │    │ (VNPY)           │  │
  │ └──────────────┘ └──────────────┘ └──────────────────┘  │
  │
  │└─────────────────────────────────────────────────────────────────┘

  实现代码示例:

  # parquet_datafeed.py - VNPY Datafeed 适配器
  from vnpy.trader.datafeed import BaseDatafeed
  from vnpy.trader.object import BarData, TickData, HistoryRequest
  import polars as pl
  from datetime import datetime
  from pathlib import Pathclass ParquetDatafeed(BaseDatafeed):
      """将 aspipe_v4 的 Parquet 数据桥接到 VNPY"""

      def __init__(self, setting: dict):
          self.base_dir = Path(setting.get("base_dir", "../data"))
      def query_bar_history(self, req: HistoryRequest) -> list[BarData]:
   """从 Parquet 加载 K 线数据"""
          # 映射 interval 到文件路径
   interval_map = {
              Interval.DAILY: "daily",
   Interval.MINUTE: "min1",
              # ... 其他周期
          }
          file_path = self.base_dir / f"{interval_map[req.interval]}/{req.symbol}.parquet"

          if not file_path.exists():
              return []

          # 使用 Polars 懒加载 df = pl.scan_parquet(file_path).filter(
              (pl.col("trade_date") >= req.start.strftime("%Y%m%d")) &
              (pl.col("trade_date") <= req.end.strftime("%Y%m%d"))
          ).collect()
   # 转换为 VNPY BarData 格式
          bars = []
   for row in df.iter_rows(named=True):
              bar = BarData(
                  symbol=req.symbol,
                  exchange=req.exchange,
                  datetime=datetime.strptime(row["trade_date"], "%Y%m%d"),
                  interval=req.interval,
                  volume=row["vol"],
                  turnover=row.get("amount", 0),
                  open_interest=row.get("oi", 0),
                  open_price=row["open"],
                  high_price=row["high"],
                  low_price=row["low"],
                  close_price=row["close"],
                  gateway_name="PARQUET"
              )
              bars.append(bar)

          return bars

  ---
  2. 事件驱动架构优化

  将原文档的「异步非阻塞架构」直接使用 VNPY 的 EventEngine 实现：

  from vnpy.event import EventEngine, Event
  from typing import Callable
  from dataclasses import dataclass
  from enum import Enum

  class FactorEventType(Enum):
      """因子事件类型"""
      FACTOR_GENERATED = "eFactorGenerated"    # LLM 生成了新因子 FACTOR_PASSED_AST = "eFactorPassedAST"   # 通过 AST
   检查
      FACTOR_BACKTEST_DONE = "eFactorBacktest" # 回测完成    FACTOR_IC_UPDATE = "eFactorIC"           # IC 更新
      FACTOR_FAILED = "eFactorFailed"          # 因子失败

  @dataclass
  class FactorEvent:
      """因子事件数据"""
   factor_code: str    factor_name: str
      ic_value: float = 0.0
   error_msg: str = ""

  class FactorMiningEventEngine:
      """因子挖掘事件引擎"""
   def __init__(self):
          self.event_engine = EventEngine(interval=1)
          self._setup_handlers()

      def _setup_handlers(self):
          """注册事件处理器"""
          # LLM 生成 -> AST 检查
          self.event_engine.register(
              FactorEventType.FACTOR_GENERATED.value,
              self._on_factor_generated )
          # AST 通过 -> 回测
          self.event_engine.register(
              FactorEventType.FACTOR_PASSED_AST.value,
              self._on_factor_passed_ast )
          # 回测完成 -> IC 评估 self.event_engine.register(
              FactorEventType.FACTOR_BACKTEST_DONE.value,
              self._on_factor_backtest_done )
          # IC 更新 -> Bandit 决策 self.event_engine.register(
              FactorEventType.FACTOR_IC_UPDATE.value,
              self._on_ic_update
          )
   def start(self):
          """启动引擎"""
          self.event_engine.start()
   def submit_factor(self, factor_code: str, factor_name: str):
          """提交新因子到流水线"""
          event = Event(
              type=FactorEventType.FACTOR_GENERATED.value,
              data=FactorEvent(factor_code, factor_name)
          )
          self.event_engine.put(event)
   def _on_factor_generated(self, event: Event):
          """处理因子生成事件 - 执行 AST 检查"""
          factor = event.data # AST 检查逻辑...
          if self._ast_check(factor.factor_code):
              # 通过检查，发送下一阶段事件
              self.event_engine.put(Event(
                  type=FactorEventType.FACTOR_PASSED_AST.value,
                  data=factor
              ))
          else:
              factor.error_msg = "AST check failed"
              self.event_engine.put(Event(
   type=FactorEventType.FACTOR_FAILED.value,
                  data=factor            ))

  ---
  3. 因子回测引擎桥接

  将因子计算与 VNPY 回测引擎集成：

  from vnpy.trader.object import Interval
  from datetime import datetime
  import polars as pl

  class FactorBacktestEngine:
      """因子回测引擎 - 桥接因子计算与 VNPY 回测"""

      def __init__(self, datafeed: ParquetDatafeed):
          self.datafeed = datafeed
          self.engine = BacktestingEngine()

   def backtest_factor(
          self,
          factor_code: str,
          symbol: str,
          exchange: str,
   start: datetime,
          end: datetime,
          initial_capital: float = 1_000_000
      ) -> dict:
          """
          对单个因子进行回测

          Args:
              factor_code: 因子表达式，如 "Ref($close, 5) / $close - 1"
              symbol: 股票代码 exchange: 交易所
              start: 开始日期
              end: 结束日期 """
          # 1. 加载历史数据
   self.engine.set_parameters(
              vt_symbol=f"{symbol}.{exchange}",
              interval=Interval.DAILY,
              start=start,
              end=end,
   rate=0.0003,  # 手续费 slippage=0.01,
              size=1,
              pricetick=0.01,
              capital=initial_capital
          )
   # 2. 创建因子策略
          strategy_class = self._create_factor_strategy(factor_code)
          self.engine.add_strategy(strategy_class, {})

          # 3. 运行回测
          self.engine.load_data()
   self.engine.run_backtesting()

          # 4. 计算结果
          df_result = self.engine.calculate_result()
          stats = self.engine.calculate_statistics()

          return {
              "sharpe_ratio": stats.get("sharpe_ratio", 0),
              "max_drawdown": stats.get("max_drawdown",0),
              "annual_return": stats.get("annual_return", 0),
              "daily_results": df_result
          }
   def _create_factor_strategy(self, factor_code: str):
          """根据因子代码动态创建 VNPY 策略类"""
          from vnpy_ctastrategy import CtaTemplate

          class FactorStrategy(CtaTemplate):
              """因子驱动策略"""
              author = "FactorMining"
   # 因子参数 factor_code = factor_code # 风控参数 stop_loss = 0.05 take_profit = 0.10

              def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
                  super().__init__(cta_engine, strategy_name, vt_symbol, setting)
                  self.factor_value = 0            def on_bar(self, bar):
                  """K 线回调 - 计算因子并交易"""
   # 这里需要将 factor_code 编译为可执行函数 # 可以使用 eval() 或编译为 AST signal = self._evaluate_factor(bar)

                  if signal > 0.02 and self.pos == 0:
                      self.buy(bar.close_price * 1.01, 100)
                  elif signal < -0.02 and self.pos > 0:
                      self.sell(bar.close_price * 0.99, abs(self.pos))
   def _evaluate_factor(self, bar):
                  """评估因子值"""
                  # 解析并执行因子表达式
                  # 需要 HistoryManager 支持
   return 0.0  # 简化示例 return FactorStrategy

  ---
  4. LLM 因子生成器与 VNPY 集成

  结合原文档的「云端大小模型协同」和「Few-Shot 提示工程」：

  # llm_factor_generator.py
  from typing import Optional
  import json

  class LLMFactorGenerator:
      """LLM 因子生成器 - 对接 VNPY 策略"""
   # 模型路由配置
      MODEL_ROUTING = {
   "planning": "mistral-large-3",      # 规划阶段用小模型 "simple_factor": "mistral-large-3", # 简单因子用小模型
  "complex_factor": "glm-4",          # 复杂因子用大模型
          "debug": "glm-4"                    # Debug 用大模型 }

      # Few-Shot 示例库
      FEW_SHOT_EXAMPLES = [
          {
              "category": "动量因子",
              "description": "价格动量因子",
              "code": "Ref($close, 5) / $close - 1",
              "vnpy_strategy": """
                  def on_bar(self, bar):
                      momentum = (self.close_array[-5] / bar.close_price - 1)
                      if momentum > 0.02:
                          self.buy(bar.close_price, 100)
   """
          },
          {
              "category": "成交量因子",
              "description": "成交量异常因子",
              "code": "$volume / Ma($volume, 20)",
              "vnpy_strategy": """
                  def on_bar(self, bar):
                      vol_ratio = bar.volume / self.vol_ma20 if vol_ratio > 2.0:
                          self.buy(bar.close_price, 100)
              """
          }
      ]
   def __init__(self, event_engine: FactorMiningEventEngine):
          self.event_engine = event_engine
          self.error_count = {}  # 错误计数，用于路由决策

      async def generate_factor(self, research_direction: str) -> str:
          """
          生成因子代码 路由策略:
  1. 先用小模型生成 2. 如果报错超过2次，切换大模型
          """
          # 检索 Few-Shot 示例
   examples = self._retrieve_examples(research_direction)
   # 选择模型
          model = self._select_model(research_direction)

          # 调用 LLM
          factor_code = await self._call_llm(
              model=model,
              prompt=self._build_prompt(research_direction, examples)
          )

          # 提交到事件流水线 self.event_engine.submit_factor(factor_code, research_direction)
   return factor_code

      def _select_model(self, direction: str) -> str:
          """根据错误计数选择模型"""
          error_count = self.error_count.get(direction, 0)

          if error_count > 2:
   return self.MODEL_ROUTING["complex_factor"]
          else:
              return self.MODEL_ROUTING["simple_factor"]
   def _retrieve_examples(self, direction: str) -> list:
          """从向量库检索 Few-Shot 示例"""
          # 可以使用 Faiss 或 ChromaDB
          # 这里简化返回全部示例 return self.FEW_SHOT_EXAMPLES[:2]

  ---
  5. Bandit 资源调度优化

  将原文档的「Bandit 资源调度」与 VNPY 的回测引擎结合：

  # bandit_scheduler.py
  import numpy as np
  from collections import defaultdict
  from typing import List, Tuple

  class BanditFactorScheduler:
      """
      Bandit 算法调度因子挖掘资源    使用 UCB (Upper Confidence Bound) 算法：
      - 高 IC 的研究方向获得更多资源 - 低 IC 的方向被早停 """

      def __init__(self, n_directions: int):
          self.n_directions = n_directions
          self.counts = np.zeros(n_directions)      # 每个方向尝试次数
          self.values = np.zeros(n_directions) # 每个方向累计 IC self.ic_history = defaultdict(list)       # IC
  历史记录

          # 早停配置 self.ic_window =3        # IC 监控窗口
          self.ic_threshold = 0.02  # IC 低阈值

      def select_direction(self) -> int:
          """选择下一个研究方向"""
          # UCB 算法
          total_count = np.sum(self.counts) + 1        # 计算每个方向的 UCB 值 ucb_values =
  np.zeros(self.n_directions)
   for i in range(self.n_directions):
   if self.counts[i] == 0:
                  ucb_values[i] = float('inf')
              else:
                  # 平均 IC + 探索项 mean = self.values[i] / self.counts[i]
                  explore = np.sqrt(2 * np.log(total_count) / self.counts[i])
                  ucb_values[i] = mean + explore return np.argmax(ucb_values)
   def update(self, direction: int, ic_value: float) -> bool:
          """
          更新方向的 IC 值 Returns:
   bool: True 继续，False 早停 """
          self.counts[direction] += 1
          self.values[direction] += ic_value
   self.ic_history[direction].append(ic_value)
   # 检查早停条件
   recent_ics = self.ic_history[direction][-self.ic_window:]

          if len(recent_ics) >= self.ic_window:
              # 条件1: IC 持续下降 if all(recent_ics[i] > recent_ics[i+1] for i in range(len(recent_ics)-1)):
                  return False

              # 条件2: IC 始终低于阈值 if all(ic < self.ic_threshold for ic in recent_ics):
                  return False

          return True

      def get_best_factors(self, top_k: int = 10) -> List[Tuple[int, float]]:
   """获取最佳因子"""
          mean_ics = self.values / (self.counts + 1e-6)
          top_indices = np.argsort(mean_ics)[-top_k:][::-1]
          return [(i, mean_ics[i]) for i in top_indices]

  ---
  6. 三级缓存优化

  将原文档的「三级缓存」与 VNPY 的 HistoryManager 结合：

  # factor_cache_system.py
  from vnpy.trader.object import BarData
  import polars as pl
  from functools import lru_cache
  import hashlib

  class FactorCacheSystem:
      """
      三级缓存系统 L1: 因子代码级 RAG - 避免重复失败 L2: 表达式缓存 - 中间计算结果复用
   L3: 底层数据缓存 - Polars 懒执行
   """

      def __init__(self):
          # L1: 失败因子库 self.failed_factors = {}  # hash -> error_msg

          # L2: 表达式缓存
          self.expression_cache = {}
   # L3: 数据缓存 (使用 Polars LazyFrame)
          self.data_cache = {}

   # ========== L1: 因子代码级 RAG ==========

      def check_factor_history(self, factor_code: str) -> tuple[bool, str]:
          """
   检查因子是否曾经失败过
   
          Returns:
              (should_skip, error_msg)
          """
          factor_hash = self._hash_code(factor_code)
   if factor_hash in self.failed_factors:
              return True, self.failed_factors[factor_hash]
   # 语义相似度检查 (需要向量库)
          similar_failed = self._find_similar_failed(factor_code)
   if similar_failed:
   return True, f"Similar to failed factor: {similar_failed}"
   return False, ""

      def record_failure(self, factor_code: str, error_msg: str):
          """记录失败因子"""
          factor_hash = self._hash_code(factor_code)
          self.failed_factors[factor_hash] = error_msg    # ========== L2: 表达式缓存 ==========

      @lru_cache(maxsize=1000)
      def get_expression_result(self, expression: str, data_hash: str) -> pl.Series:
          """获取表达式计算结果"""
          cache_key = f"{expression}_{data_hash}"
          return self.expression_cache.get(cache_key)
   def cache_expression_result(self, expression: str, data_hash: str, result: pl.Series):
          """缓存表达式结果"""
          cache_key = f"{expression}_{data_hash}"
          self.expression_cache[cache_key] = result # ========== L3: 底层数据缓存 ==========
   def get_bar_data_lazy(self, symbol: str, exchange: str) -> pl.LazyFrame:
          """
   获取 K 线数据的 LazyFrame Polars 懒执行:
          - 自动优化查询
          - 只加载需要的列
          - 内存占用优化 """
          cache_key = f"{symbol}.{exchange}"
   if cache_key not in self.data_cache:
              # 从 Parquet 加载
              df = pl.scan_parquet(f"../data/daily/{symbol}.parquet")
              self.data_cache[cache_key] = df return self.data_cache[cache_key]
   # ========== 工具方法 ==========
   def _hash_code(self, code: str) -> str:
          """计算代码哈希"""
          return hashlib.md5(code.encode()).hexdigest()
   def _find_similar_failed(self, factor_code: str) -> str:
          """使用向量库查找相似的失败因子"""
          # 需要 Faiss/ChromaDB
          return ""

  ---
  7. 完整集成架构图

  ┌──────────────────────────────────────────────────────────────────────────────┐
  │                        因子挖掘 + VNPY 集成架构
  │├──────────────────────────────────────────────────────────────────────────────┤
  │                                                                              │
  │  ┌─────────────────────────────────────────────────────────────────────┐ │
  │  │                         LLM 因子生成层                               │    │
  │ │  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐ │    │
  │  │  │ Mistral/MiniMax│   │ Few-Shot    │    │  质量门控            │  │ │
  │  │  │ (小模型路由)   │   │   示例检索    │    │  AST/语义检查        │  │    │
  │  │ └───────┬──────┘ └───────┬──────┘    └──────────┬───────────┘  │    │
  │  │          │                   │                      │              │    │
  │  │          └───────────────────┼──────────────────────┘ │    │
  │  │                              ▼                                     │ │
  │  │ ┌──────────────────┐                            │    ││  │                    │  GLM-4 (兜底)    │
                  │    │
  │  │                    └────────┬─────────┘                            │    │
  │  └─────────────────────────────┼───────────────────────────────────────┘    │
  │                                │                                             │
  │ ▼                                             │
  │ ┌─────────────────────────────────────────────────────────────────────┐    │
  │  │                      VNPY EventEngine 事件总线                       │    ││  │  ┌────────────┐
  ┌────────────┐ ┌────────────┐  ┌────────────┐    │    │
  │  │  │ FACTOR_    │  │ FACTOR_    │ │ FACTOR_ │  │ FACTOR_ │    │    │
  │  │  │ GENERATED  │─▶│ PASSED_AST │─▶│ BACKTEST   │─▶│ IC_UPDATE  │    │    │
  │  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘    │    │
  │ └─────────────────────────────┬───────────────────────────────────────┘    │
  │                                │                                             │
  │ ▼                                             │
  │ ┌─────────────────────────────────────────────────────────────────────┐    │
  │  │                      Bandit 资源调度器                               │    │
  │  │  ┌──────────────────┐    ┌──────────────────┐                       │    │
  │  │  │  UCB 算法选方向  │◀──▶│  早停机制        │                       │    │
  │  │  │  IC 监控窗口     │ │  资源释放        │                       │    ││  │  └──────────────────┘
  └──────────────────┘                       │    │
  │  └─────────────────────────────┬───────────────────────────────────────┘    │
  │                                │                                             │
  │ ▼                                             │
  │  ┌─────────────────────────────────────────────────────────────────────┐    │
  │  │                    VNPY BacktestingEngine                            │    ││  │  ┌──────────────┐
  ┌──────────────┐ ┌──────────────────────┐  │    │
  │  │  │ ParquetData │    │ HistoryManager│ │ FactorStrategy       │  │    │
  │  │  │ feed Adapter │───▶│ (VNPY)       │───▶│ (动态生成)           │  │    │
  │  │ └──────────────┘ └──────────────┘ └──────────────────────┘  │    │
  │  │                                                  │ │    │
  │  │                                                  ▼                  │    ││  │
      ┌──────────────────────┐ │    │
  │  │                                    │ 回测结果 + IC 计算   │        │    │
  │  │ └──────────────────────┘        │    │
  │ └─────────────────────────────────────────────────────────────────────┘    │
  │                                │                                             │
  │ ▼                                             │
  │  ┌─────────────────────────────────────────────────────────────────────┐    │
  │  │                         三级缓存系统                                 │    │
  │  │ ┌────────────┐    ┌────────────┐    ┌────────────────────────┐    │    ││  │  │ L1: RAG    │ │ L2: 表达式 │
   │ L3: Polars LazyFrame   │    │    │
  │  │  │ 失败因子库 │    │ 计算缓存   │    │ 底层数据缓存           │    │    ││  │  └────────────┘ └────────────┘
  └────────────────────────┘    │    │
  │  └─────────────────────────────────────────────────────────────────────┘    │
  │ │
  └──────────────────────────────────────────────────────────────────────────────┘

  ---
  8. 关键优化建议总结

  ┌──────────┬───────────────────┬─────────────────────────────┬────────────────────────┐
  │  优化点  │      原方案       │        VNPY 集成优化        │          效益          │
  ├──────────┼───────────────────┼─────────────────────────────┼────────────────────────┤
  │ 数据层   │ Parquet + Polars  │ 实现 ParquetDatafeed 适配器 │ 复用现有数据，无需迁移 │
  ├──────────┼───────────────────┼─────────────────────────────┼────────────────────────┤
  │ 事件调度 │ 自建生产者-消费者 │ 直接使用 EventEngine        │ 代码量减少 50%         │
  ├──────────┼───────────────────┼─────────────────────────────┼────────────────────────┤
  │ 回测引擎 │ Qlib              │ 可选 VNPY 或保留 Qlib       │ 策略可直接上线交易     │
  ├──────────┼───────────────────┼─────────────────────────────┼────────────────────────┤
  │ 因子策略 │ 无交易执行        │ 动态生成 CtaTemplate        │ 因子→策略→实盘闭环     │
  ├──────────┼───────────────────┼─────────────────────────────┼────────────────────────┤
  │ 资源调度 │ Bandit 算法       │ 结合 VNPY 回测并行优化      │ 算力利用率提升 2x      │
  └──────────┴───────────────────┴─────────────────────────────┴────────────────────────┘

  推荐实施路径

  1. 第一阶段: 实现 ParquetDatafeed 适配器，打通数据层
  2. 第二阶段: 集成 EventEngine 替换自建事件系统
  3. 第三阶段: 实现因子→VNPY 策略的动态转换
  4. 第四阶段: 接入 VNPY Gateway 实现实盘交易
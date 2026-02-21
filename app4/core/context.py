from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class DownloadContext:
    user_provided_dates: bool = False
    date_range: Optional[Dict[str, str]] = None
    interface_config: Dict[str, Any] = field(default_factory=dict)
    skip_stock_level_detection: bool = (
        False  # 标记是否跳过股票级别缺口检测（已在params_builder层完成）
    )
    gap_params: Optional[List[Dict[str, Any]]] = None  # 缺口检测生成的参数列表

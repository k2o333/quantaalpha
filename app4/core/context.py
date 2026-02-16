from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class DownloadContext:
    user_provided_dates: bool = False
    force_download: bool = False
    date_range: Optional[Dict[str, str]] = None
    interface_config: Dict[str, Any] = field(default_factory=dict)

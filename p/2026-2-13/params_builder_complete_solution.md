# App4  unified params builder refactoring solution

## 1. Background and Problem Analysis

### 1.1 Current Code Status

After in-depth analysis of the app4 codebase, the parameter building logic is mainly distributed in the following locations:

| File | Main Functions | Problem |
|------|---------------|---------|
| [`main.py`](app4/main.py) | `run_update_mode()` (L198-485), `main()` (L530-1159) | Duplicate stock_loop judgment logic, special interface hardcoding |
| [`downloader.py`](app4/core/downloader.py) | `download_single_stock()` (L416-587) | Parameter construction logic mixed with download logic |
| [`pagination_executor.py`](app4/core/pagination_executor.py) | `execute()` (L50-108) | Parameter cleaning logic scattered |

### 1.2 Core Issues

1. **Duplicate Judgment Logic**
   - `if pagination_config.get('mode') == 'stock_loop'` appears in two main locations
   - Each location has similar scenario branching logic

2. **Special Interface Hardcoding**
   - `disclosure_date`: `_stock_full_history` flag
   - `broker_recommend`: month loop processing
   - `pro_bar`: special date handling
   - Date anchor interfaces: `_date_anchor_param` flag

3. **Implicit Priority Rules**
   ```
   Priority: Command line > DateCalculator > Interface default > Global default
   (But no clear documentation)
   ```

4. **Parameter Cleaning Inconsistency**
   - Although basically unified as dictionary comprehension, still lacks a unified tool function

---

## 2. Solution Design Principles

### 2.1 Design Philosophy

```
Collaboration over replacement
Strategy pattern over big class
Progressive refactoring over one-time replacement
```

### 2.2 Relationship with Existing Components

```
                    User Request
                        |
                        v
    +-------------------------------------------+
    |              ParamsBuilder                |
    |          (Coordination Entry)             |
    +-------------------------------------------+
                        |
        +---------------+---------------+
        |               |               |
        v               v               v
+---------------+ +---------------+ +-------------------+
| DateParams    | | StockLoop     | | SpecialInterface  |
| Strategy      | | Strategy      | | Strategy          |
| (Date param   | | (Stock loop   | | (disclosure_date, |
|  processing)  | |  processing)  | |  broker_recommend)|
+---------------+ +---------------+ +-------------------+
        |               |               |
        +---------------+---------------+
                        |
                        v
    +-------------------------------------------+
    |           Existing Components             |
    |  DateCalculator / PaginationExecutor /    |
    |  GenericDownloader._validate_parameters() |
    +-------------------------------------------+
```

**Key Point**: `ParamsBuilder` is the coordinator of existing components, not the replacement.

---

## 3. Detailed Design

### 3.1 Core Interface Definition

```python
# app4/core/params_builder.py

from typing import Dict, Any, Optional, Protocol
from dataclasses import dataclass
from enum import Enum


class ParamBuildScenario(Enum):
    """Parameter building scenario enumeration"""
    DIRECT_DOWNLOAD = "direct"           # Direct download, no stock loop
    STOCK_LOOP_HAS_DATE = "stock_loop_date"       # Stock loop, has start_date/end_date
    STOCK_LOOP_DATE_ANCHOR = "stock_loop_anchor"  # Stock loop, uses date anchor param
    STOCK_LOOP_NO_DATE = "stock_loop_no_date"     # Stock loop, no date param
    SPECIAL_INTERFACE = "special"        # Special interface handling


@dataclass
class BuildResult:
    """Parameter building result"""
    params: Dict[str, Any]           # Raw params (including internal flags)
    clean_params: Dict[str, Any]     # Cleaned params (for API request)
    scenario: ParamBuildScenario     # Identified scenario
    requires_stock_loop: bool        # Whether stock loop is needed
    internal_flags: Dict[str, Any]   # Internal flag collection


class ParamBuildStrategy(Protocol):
    """Parameter building strategy protocol"""
    
    def can_handle(
        self, 
        interface_name: str, 
        interface_config: Dict[str, Any],
        args: Any
    ) -> bool:
        """Whether this strategy can handle the interface"""
        ...
    
    def build(
        self,
        interface_config: Dict[str, Any],
        args: Any,
        date_range: Optional['DateRange'] = None,
        user_provided_dates: bool = False
    ) -> BuildResult:
        """Build request parameters"""
        ...
```

### 3.2 Tool Functions (Low Risk, High Value)

```python
# app4/core/param_utils.py

from typing import Dict, Any, List, Optional
from dataclasses import dataclass


def clean_internal_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Unified cleaning of internal flag parameters
    
    Args:
        params: Raw parameter dictionary
        
    Returns:
        Cleaned parameter dictionary (without _ prefixed keys)
    """
    return {k: v for k, v in params.items() if not k.startswith('_')}


@dataclass
class StockLoopScenario:
    """Stock loop scenario analysis result"""
    has_start_end: bool           # Whether interface supports start_date/end_date
    date_anchor_param: Optional[str]  # Date anchor parameter name
    requires_full_history: bool   # Whether full history is needed
    
    @property
    def scenario_type(self) -> str:
        """Determine scenario type"""
        if self.has_start_end:
            return 'has_date'
        elif self.date_anchor_param:
            return 'date_anchor'
        else:
            return 'no_date'


def analyze_stock_loop_scenario(
    interface_config: Dict[str, Any],
    args: Any,
    user_provided_dates: bool
) -> StockLoopScenario:
    """
    Analyze stock loop scenario
    
    Args:
        interface_config: Interface configuration
        args: Command line arguments
        user_provided_dates: Whether user provided dates
        
    Returns:
        StockLoopScenario: Scenario analysis result
    """
    parameter_config = interface_config.get('parameters', {})
    
    # Check if interface supports start_date/end_date
    has_start_end = (
        'start_date' in parameter_config and 
        'end_date' in parameter_config
    )
    
    # Check for date anchor parameter
    date_anchor_param = None
    for param_name, param_def in parameter_config.items():
        if param_def.get('is_date_anchor', False):
            date_anchor_param = param_name
            break
    
    # Determine if full history is needed
    requires_full_history = (
        not user_provided_dates and 
        not getattr(args, 'ts_code', None)
    )
    
    return StockLoopScenario(
        has_start_end=has_start_end,
        date_anchor_param=date_anchor_param,
        requires_full_history=requires_full_history
    )
```

### 3.3 Strategy Implementation

#### 3.3.1 Direct Download Strategy

```python
# app4/core/strategies/direct_download_strategy.py

from typing import Dict, Any, Optional
from ..params_builder import ParamBuildStrategy, BuildResult, ParamBuildScenario
from ..param_utils import clean_internal_params


class DirectDownloadStrategy(ParamBuildStrategy):
    """Direct download strategy - for non-stock-loop interfaces"""
    
    def can_handle(
        self, 
        interface_name: str, 
        interface_config: Dict[str, Any],
        args: Any
    ) -> bool:
        """Check if direct download mode"""
        pagination_config = interface_config.get('pagination', {})
        return not (
            pagination_config.get('enabled', False) and 
            pagination_config.get('mode') == 'stock_loop'
        )
    
    def build(
        self,
        interface_config: Dict[str, Any],
        args: Any,
        date_range: Optional['DateRange'] = None,
        user_provided_dates: bool = False
    ) -> BuildResult:
        """Build direct download parameters"""
        params = {}
        
        # Add date parameters
        if date_range:
            params['start_date'] = date_range.start_date
            params['end_date'] = date_range.end_date
        elif hasattr(args, 'start_date'):
            params['start_date'] = args.start_date
            if hasattr(args, 'end_date') and args.end_date:
                params['end_date'] = args.end_date
        
        # Add stock code
        if getattr(args, 'ts_code', None):
            params['ts_code'] = args.ts_code
        
        return BuildResult(
            params=params,
            clean_params=clean_internal_params(params),
            scenario=ParamBuildScenario.DIRECT_DOWNLOAD,
            requires_stock_loop=False,
            internal_flags={}
        )
```

#### 3.3.2 Stock Loop Strategy

```python
# app4/core/strategies/stock_loop_strategy.py

from typing import Dict, Any, Optional
from ..params_builder import ParamBuildStrategy, BuildResult, ParamBuildScenario
from ..param_utils import clean_internal_params, analyze_stock_loop_scenario


class StockLoopStrategy(ParamBuildStrategy):
    """Stock loop strategy - for stock_loop mode interfaces"""
    
    def can_handle(
        self, 
        interface_name: str, 
        interface_config: Dict[str, Any],
        args: Any
    ) -> bool:
        """Check if stock loop mode"""
        pagination_config = interface_config.get('pagination', {})
        return (
            pagination_config.get('enabled', False) and 
            pagination_config.get('mode') == 'stock_loop'
        )
    
    def build(
        self,
        interface_config: Dict[str, Any],
        args: Any,
        date_range: Optional['DateRange'] = None,
        user_provided_dates: bool = False
    ) -> BuildResult:
        """Build stock loop parameters"""
        scenario = analyze_stock_loop_scenario(
            interface_config, args, user_provided_dates
        )
        
        params = {}
        internal_flags = {}
        
        # Determine scenario type and build parameters
        if scenario.scenario_type == 'has_date':
            # Scenario 1: Interface supports start_date/end_date
            if date_range:
                params['start_date'] = date_range.start_date
                params['end_date'] = date_range.end_date
            elif hasattr(args, 'start_date'):
                params['start_date'] = args.start_date
                if hasattr(args, 'end_date') and args.end_date:
                    params['end_date'] = args.end_date
            
            build_scenario = ParamBuildScenario.STOCK_LOOP_HAS_DATE
            
        elif scenario.scenario_type == 'date_anchor':
            # Scenario 2: Interface uses date anchor parameter
            ts_code = getattr(args, 'ts_code', None)
            
            if ts_code and not user_provided_dates:
                # Single stock full history
                params = {'ts_code': ts_code}
            elif scenario.requires_full_history:
                # Full history per stock
                internal_flags['_stock_full_history'] = True
            else:
                # Date range with anchor
                if date_range:
                    params['start_date'] = date_range.start_date
                    params['end_date'] = date_range.end_date
                internal_flags['_date_anchor_param'] = scenario.date_anchor_param
            
            build_scenario = ParamBuildScenario.STOCK_LOOP_DATE_ANCHOR
            
        else:
            # Scenario 3: No date parameters
            params = {}
            internal_flags['_stock_full_history'] = True
            build_scenario = ParamBuildScenario.STOCK_LOOP_NO_DATE
        
        # Add stock code if specified
        if getattr(args, 'ts_code', None):
            params['ts_code'] = args.ts_code
        
        # Merge internal flags
        params.update(internal_flags)
        
        return BuildResult(
            params=params,
            clean_params=clean_internal_params(params),
            scenario=build_scenario,
            requires_stock_loop=True,
            internal_flags=internal_flags
        )
```

#### 3.3.3 Special Interface Strategy

```python
# app4/core/strategies/special_interface_strategy.py

from typing import Dict, Any, Optional, List
from ..params_builder import ParamBuildStrategy, BuildResult, ParamBuildScenario
from ..param_utils import clean_internal_params


class SpecialInterfaceStrategy(ParamBuildStrategy):
    """Special interface strategy - for interfaces requiring special handling"""
    
    # Special interface registry
    SPECIAL_INTERFACES = {
        'broker_recommend': 'month_loop',
        'pro_bar': 'list_date_start',
        'disclosure_date': 'stock_full_history',
    }
    
    def can_handle(
        self, 
        interface_name: str, 
        interface_config: Dict[str, Any],
        args: Any
    ) -> bool:
        """Check if special interface"""
        return interface_name in self.SPECIAL_INTERFACES
    
    def build(
        self,
        interface_config: Dict[str, Any],
        args: Any,
        date_range: Optional['DateRange'] = None,
        user_provided_dates: bool = False
    ) -> BuildResult:
        """Build special interface parameters"""
        interface_name = interface_config.get('name', '')
        handler_type = self.SPECIAL_INTERFACES.get(interface_name)
        
        if handler_type == 'month_loop':
            return self._build_month_loop_params(interface_config, args, date_range)
        elif handler_type == 'list_date_start':
            return self._build_list_date_params(interface_config, args, date_range)
        elif handler_type == 'stock_full_history':
            return self._build_full_history_params(interface_config, args, user_provided_dates)
        
        # Default: return empty result
        return BuildResult(
            params={},
            clean_params={},
            scenario=ParamBuildScenario.SPECIAL_INTERFACE,
            requires_stock_loop=False,
            internal_flags={}
        )
    
    def _build_month_loop_params(
        self,
        interface_config: Dict[str, Any],
        args: Any,
        date_range: Optional['DateRange']
    ) -> BuildResult:
        """Build month loop parameters (for broker_recommend)"""
        # This interface needs to generate month list
        # Actual month generation is done in main.py
        params = {}
        
        if date_range:
            params['start_date'] = date_range.start_date
            params['end_date'] = date_range.end_date
        
        if getattr(args, 'ts_code', None):
            params['ts_code'] = args.ts_code
        
        # Mark as needing month loop
        internal_flags = {'_requires_month_loop': True}
        params.update(internal_flags)
        
        return BuildResult(
            params=params,
            clean_params=clean_internal_params(params),
            scenario=ParamBuildScenario.SPECIAL_INTERFACE,
            requires_stock_loop=False,
            internal_flags=internal_flags
        )
    
    def _build_list_date_params(
        self,
        interface_config: Dict[str, Any],
        args: Any,
        date_range: Optional['DateRange']
    ) -> BuildResult:
        """Build list_date start parameters (for pro_bar)"""
        params = {}
        
        # pro_bar special handling: if no date specified, use empty params
        # Let downstream use each stock's list_date as start
        if getattr(args, 'start_date', '20230101') == '20230101' and not getattr(args, 'end_date', None):
            # Use default date, meaning full history
            params = {}
        else:
            if date_range:
                params['start_date'] = date_range.start_date
                params['end_date'] = date_range.end_date
            elif hasattr(args, 'start_date'):
                params['start_date'] = args.start_date
                if hasattr(args, 'end_date') and args.end_date:
                    params['end_date'] = args.end_date
        
        if getattr(args, 'ts_code', None):
            params['ts_code'] = args.ts_code
        
        return BuildResult(
            params=params,
            clean_params=clean_internal_params(params),
            scenario=ParamBuildScenario.SPECIAL_INTERFACE,
            requires_stock_loop=True,
            internal_flags={}
        )
    
    def _build_full_history_params(
        self,
        interface_config: Dict[str, Any],
        args: Any,
        user_provided_dates: bool
    ) -> BuildResult:
        """Build full history parameters (for disclosure_date)"""
        ts_code = getattr(args, 'ts_code', None)
        
        if ts_code and not user_provided_dates:
            # Single stock full history
            params = {'ts_code': ts_code}
        elif not user_provided_dates and not ts_code:
            # Full history per stock
            params = {'_stock_full_history': True}
        else:
            # User specified date range
            params = {}
            if hasattr(args, 'start_date'):
                params['start_date'] = args.start_date
            if hasattr(args, 'end_date') and args.end_date:
                params['end_date'] = args.end_date
            if ts_code:
                params['ts_code'] = ts_code
        
        return BuildResult(
            params=params,
            clean_params=clean_internal_params(params),
            scenario=ParamBuildScenario.SPECIAL_INTERFACE,
            requires_stock_loop=True,
            internal_flags={'_stock_full_history': params.get('_stock_full_history', False)}
        )
```

### 3.4 ParamsBuilder Entry Class

```python
# app4/core/params_builder.py (continued)

from typing import Dict, Any, Optional, List, Type
from .strategies.direct_download_strategy import DirectDownloadStrategy
from .strategies.stock_loop_strategy import StockLoopStrategy
from .strategies.special_interface_strategy import SpecialInterfaceStrategy


class ParamsBuilder:
    """
    Unified parameter builder - coordination entry
    
    Responsibilities:
    1. Select appropriate strategy
    2. Coordinate with DateCalculator
    3. Return structured build result
    """
    
    def __init__(self, date_calculator: Optional['DateCalculator'] = None):
        """
        Initialize parameter builder
        
        Args:
            date_calculator: Date calculator instance (optional)
        """
        self._date_calculator = date_calculator
        self._strategies: List[ParamBuildStrategy] = [
            SpecialInterfaceStrategy(),  # Check special interfaces first
            StockLoopStrategy(),         # Then stock loop
            DirectDownloadStrategy(),    # Finally direct download
        ]
    
    def build(
        self,
        interface_name: str,
        interface_config: Dict[str, Any],
        args: Any,
        mode: str = 'normal'
    ) -> BuildResult:
        """
        Build request parameters
        
        Args:
            interface_name: Interface name
            interface_config: Interface configuration
            args: Command line arguments
            mode: Running mode ('normal' or 'update')
            
        Returns:
            BuildResult: Structured build result
        """
        # Determine if user provided dates
        user_provided_dates = getattr(args, 'user_provided_dates', False)
        
        # Calculate date range (if in update mode or user provided dates)
        date_range = None
        if mode == 'update' and self._date_calculator and not user_provided_dates:
            date_range = self._date_calculator.calculate_update_range(interface_name)
        elif user_provided_dates:
            from main import validate_and_adjust_date
            start_date, end_date = validate_and_adjust_date(
                getattr(args, 'start_date', '20230101'),
                getattr(args, 'end_date', None)
            )
            from core.date_utils import DateRange
            date_range = DateRange(start_date=start_date, end_date=end_date)
        
        # Select strategy
        strategy = self._select_strategy(interface_name, interface_config, args)
        
        # Build parameters
        return strategy.build(
            interface_config=interface_config,
            args=args,
            date_range=date_range,
            user_provided_dates=user_provided_dates
        )
    
    def _select_strategy(
        self,
        interface_name: str,
        interface_config: Dict[str, Any],
        args: Any
    ) -> ParamBuildStrategy:
        """
        Select appropriate strategy
        
        Args:
            interface_name: Interface name
            interface_config: Interface configuration
            args: Command line arguments
            
        Returns:
            ParamBuildStrategy: Selected strategy
        """
        for strategy in self._strategies:
            if strategy.can_handle(interface_name, interface_config, args):
                return strategy
        
        # Default to direct download
        return self._strategies[-1]
    
    def register_strategy(self, strategy: ParamBuildStrategy, priority: int = 0):
        """
        Register custom strategy
        
        Args:
            strategy: Strategy instance
            priority: Priority (higher priority checked first)
        """
        if priority > 0:
            self._strategies.insert(0, strategy)
        else:
            self._strategies.append(strategy)
```

---

## 4. File Structure

```
app4/
  core/
    params_builder.py          # Main entry class and interfaces
    param_utils.py             # Tool functions
    strategies/
      __init__.py
      direct_download_strategy.py
      stock_loop_strategy.py
      special_interface_strategy.py
```

---

## 5. Usage Example

### 5.1 In main.py

```python
# Before refactoring (current code)
pagination_config = interface_config.get('pagination', {})
if pagination_config.get('enabled', False) and pagination_config.get('mode') == 'stock_loop':
    parameter_config = interface_config.get('parameters', {})
    has_start_end = 'start_date' in parameter_config and 'end_date' in parameter_config
    date_anchor_param = None
    for param_name, param_def in parameter_config.items():
        if param_def.get('is_date_anchor', False):
            date_anchor_param = param_name
            break
    # ... more complex logic

# After refactoring
from core.params_builder import ParamsBuilder

params_builder = ParamsBuilder(date_calculator=date_calculator)
result = params_builder.build(
    interface_name=interface_name,
    interface_config=interface_config,
    args=args,
    mode='update' if args.update else 'normal'
)

# Use result
params = result.params
if result.requires_stock_loop:
    stock_list = _prepare_stock_list(downloader, args, params, storage_manager, logger)
    # ... stock loop logic
else:
    data = downloader.download(interface_name, result.clean_params)
```

### 5.2 In pagination_executor.py

```python
# Before refactoring
clean_params = {k: v for k, v in params.items() if not k.startswith('_')}

# After refactoring
from core.param_utils import clean_internal_params
clean_params = clean_internal_params(params)
```

---

## 6. Implementation Roadmap

### Phase 1: Low-Risk Improvements (1-2 days)

- [ ] Create `app4/core/param_utils.py`
- [ ] Implement `clean_internal_params()` function
- [ ] Implement `analyze_stock_loop_scenario()` function
- [ ] Replace all parameter cleaning code with unified function

### Phase 2: Strategy Implementation (2-3 days)

- [ ] Create `app4/core/strategies/` directory
- [ ] Implement `DirectDownloadStrategy`
- [ ] Implement `StockLoopStrategy`
- [ ] Implement `SpecialInterfaceStrategy`
- [ ] Write unit tests for each strategy

### Phase 3: Entry Class Implementation (1-2 days)

- [ ] Create `app4/core/params_builder.py`
- [ ] Implement `ParamsBuilder` class
- [ ] Implement `BuildResult` dataclass
- [ ] Write integration tests

### Phase 4: main.py Refactoring (2-3 days)

- [ ] Refactor `run_update_mode()` function
- [ ] Refactor `main()` function
- [ ] Remove duplicate parameter building logic
- [ ] Full regression testing

---

## 7. Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| Breaking existing functionality | High | Comprehensive test coverage before refactoring |
| Missing special interface handling | Medium | Complete special interface registry |
| Performance impact | Low | Strategy selection is O(n), n is small (3-5) |
| Learning curve | Low | Clear interface design, good documentation |

---

## 8. Success Criteria

1. **Code Quality**
   - No duplicate parameter building logic in main.py
   - All parameter cleaning uses unified function
   - Clear strategy pattern implementation

2. **Functionality**
   - All existing interfaces work as before
   - Special interfaces handled correctly
   - Update mode and normal mode both work

3. **Maintainability**
   - Adding new interface type only requires new strategy
   - Clear separation of concerns
   - Well-documented code

---

## 9. Appendix: Special Interface Handling Details

### 9.1 broker_recommend

```python
# Special handling: month loop
# Input: start_date=20230101, end_date=20240101
# Output: Generate month list ['202301', '202302', ..., '202401']

# In main.py, after getting BuildResult:
if result.internal_flags.get('_requires_month_loop'):
    months = generate_month_list(params['start_date'], params['end_date'])
    for month in months:
        month_params = {'month': month}
        data = downloader.download(interface_name, month_params)
```

### 9.2 pro_bar

```python
# Special handling: use list_date as start
# If no date specified, each stock uses its own list_date

# In download_single_stock():
if interface_name == 'pro_bar' and 'start_date' not in params:
    list_date = stock.get('list_date', '20000101')
    params['start_date'] = list_date
```

### 9.3 disclosure_date

```python
# Special handling: full history per stock
# _stock_full_history flag means single request per stock

# In pagination_executor.py:
if base_params.get('_stock_full_history'):
    # Generate one request per stock, no date range
    for stock in stock_list:
        params = {'ts_code': stock['ts_code']}
        # Execute single request
```

---

*Document Version: 1.0*
*Created: 2026-02-13*
*Author: Architect Mode*
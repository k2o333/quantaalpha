# S08: ResourceManager 资源管理 (S7/D018) — Slice Research

**Milestone:** M003 | **Status:** Research | **Started:** 2026-03-23

## 1. Executive Summary

S08 implements **ResourceManager** — a resource boundary enforcement layer for 24H autonomous operation (D018). Based on D018 requirements, ResourceManager must enforce:

1. **Daily Token Budget** — Hard cap (default 5M tokens) with automatic circuit-breaking
2. **Disk Space Monitoring** — Alert when <5GB available, optional stop
3. **result.h5 Auto-Cleanup** — Remove files older than 30 days
4. **Factor Library Entry Limits** — Cap entries + SQLite migration threshold

**Key Finding:** ProviderPool already tracks token usage via `get_token_usage_report()` (S04). ResourceManager needs to:
- Wrap this with daily reset logic
- Add disk space monitoring
- Add workspace cleanup
- Integrate with `loop.py` run() for budget enforcement

**Risk Level:** Medium (established patterns from S04/S06, low technical uncertainty)

---

## 2. D018 Requirements Breakdown

| Requirement | Default | Implementation Location |
|-------------|---------|------------------------|
| Daily Token Budget | 5M tokens | `resource_manager.py` + `loop.py` |
| Disk Space Alert | <5GB | `resource_manager.py` |
| result.h5 Retention | 30 days | `resource_manager.py` |
| Factor Library Cap | TBD entries | `library.py` integration |
| SQLite Migration | TBD threshold | `library.py` integration |

---

## 3. Existing Codebase Analysis

### 3.1 ProviderPool Token Tracking (S04)

**File:** `third_party/quantaalpha/quantaalpha/llm/provider_pool.py`

```python
# Lines 480-510: get_token_usage_report()
def get_token_usage_report(self) -> dict[str, Any]:
    total_tokens = 0
    total_requests = 0
    providers_data: dict[str, Any] = {}
    for name, h in self.health.items():
        total_tokens += h.total_tokens
        total_requests += h.total_requests
        providers_data[name] = {
            "tokens": h.total_tokens,
            "requests": h.total_requests,
            "is_healthy": h.is_healthy,
        }
    return {"total_tokens": total_tokens, ...}
```

**Finding:** Token tracking is already implemented. ResourceManager needs to add:
- Daily reset logic (compare against date-of-day tokens)
- Budget comparison before loop iteration

### 3.2 Checkpoint Patterns (S06) — Reference for Loop Integration

**File:** `third_party/quantaalpha/quantaalpha/pipeline/loop.py`

```python
# Lines 175-220: AlphaAgentLoop.run() integration pattern
def run(self, step_n: int | None = None, stop_event: threading.Event = None):
    while True:
        # ... step execution ...
        
        # Checkpoint save after every step (D017 pattern)
        try:
            self._checkpoint.save({...})
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")
        
        if stop_event is not None and stop_event.is_set():
            raise Exception("Mining stopped by user")
```

**Finding:** Use same pattern for resource checks — wrap step execution with resource guard.

### 3.3 Factor Library Manager

**File:** `third_party/quantaalpha/quantaalpha/factors/library.py`

**Current Structure:**
- `FactorLibraryManager` class with `_load()`, `_save()`, `_acquire_lock()`
- JSON file storage at `data/factorlib/all_factors_library.json`
- `versions` field for rolling history (D017)

**Integration Points:**
- Add entry count check before `add_factors_from_experiment()`
- Add cleanup of old versions based on retention policy

### 3.4 Experiment Configuration Structure

**File:** `third_party/quantaalpha/quantaalpha/factors/prompts/experiment.yaml`

```yaml
# S07 pit_alignment pattern (reference)
pit_alignment:
  enabled: true
  default_lag_days: 45
  source_overrides:
    forecast_vip:
      lag_days: 15
```

**Finding:** Add `resource_management:` section following same pattern.

---

## 4. Implementation Architecture

### 4.1 Module Structure

```
third_party/quantaalpha/
├── configs/
│   └── experiment.yaml        # Add resource_management section
└── quantaalpha/
    ├── llm/
    │   └── provider_pool.py      # Existing (S04)
    ├── pipeline/
    │   ├── checkpoint.py         # Existing (S06)
    │   └── resource_manager.py    # NEW
    └── factors/
        └── library.py            # Modified (entry limits)
```

**Note:** Worktree root is `/home/quan/testdata/aspipe_v4/.gsd/worktrees/M003/`. The quantaalpha submodule is at `third_party/quantaalpha/`.

### 4.2 ResourceManager Class Design

```python
@dataclass
class ResourceConfig:
    """Configuration for ResourceManager (D018)."""
    enabled: bool = True
    # Token budget
    daily_token_limit: int = 5_000_000  # 5M default
    token_budget_check_interval: int = 1  # check every N loops
    # Disk space
    disk_space_min_gb: float = 5.0  # alert threshold
    disk_space_stop_gb: float = 2.0  # hard stop threshold
    # result.h5 cleanup
    result_cleanup_enabled: bool = True
    result_retention_days: int = 30
    result_cleanup_max_files: int = 1000  # guard against corruption
    # Factor library
    factor_library_max_entries: int = 10000  # cap
    sqlite_migration_threshold: int = 50000  # entries
    # State
    daily_token_reset_hour: int = 0  # midnight UTC

@dataclass
class ResourceStatus:
    """Current resource state snapshot."""
    total_tokens_today: int
    daily_limit: int
    disk_space_gb: float
    disk_space_status: str  # "ok" | "warning" | "critical"
    oldest_result_h5_age_days: int | None
    factor_library_entries: int
    within_budget: bool
    within_disk: bool

class ResourceManager:
    """Singleton resource boundary enforcer (D018)."""
    
    def __init__(self, config: dict | None = None) -> None:
        # Load from experiment.yaml or defaults
        # Initialize daily token counter with date tracking
        # Setup cleanup scheduler
    
    def check_and_enforce(self) -> tuple[bool, str]:
        """
        Main enforcement gate called before each loop iteration.
        Returns (allowed, reason) where reason explains if blocked.
        """
    
    def get_token_usage_report(self) -> dict[str, Any]:
        """Get ProviderPool tokens + daily tracking."""
    
    def get_disk_space_report(self) -> dict[str, Any]:
        """Get disk space status."""
    
    def get_status(self) -> ResourceStatus:
        """Get full status snapshot."""
    
    def cleanup_old_results(self) -> int:
        """Remove result.h5 files older than retention period."""
    
    def _get_provider_pool(self) -> ProviderPool | None:
        """Lazy import to avoid circular dependency."""
```

### 4.3 Integration with loop.py

**File:** `third_party/quantaalpha/quantaalpha/pipeline/loop.py`

**Pattern:** Wrap loop iteration with resource check

```python
# In AlphaAgentLoop.run()
def run(self, ...):
    # Initialize ResourceManager (lazy)
    resource_mgr = self._get_resource_manager()
    
    while True:
        # Resource budget check before each iteration
        if resource_mgr:
            allowed, reason = resource_mgr.check_and_enforce()
            if not allowed:
                logger.warning(f"Resource budget exceeded: {reason}")
                logger.warning("Consider increasing budget or clearing old results.")
                # Could raise ResourceBudgetExceeded or just warn
                break  # or raise
        
        # ... existing step execution ...
```

### 4.4 experiment.yaml Configuration

```yaml
# ============================================================
# RESOURCE MANAGEMENT CONFIGURATION (D018)
# Controls token budget, disk space, and cleanup policies
# ============================================================
resource_management:
  enabled: true
  
  # Token budget (daily hard cap)
  daily_token_limit: 5000000        # 5M tokens
  token_budget_check_interval: 1    # check every loop
  daily_token_reset_hour: 0          # midnight UTC
  
  # Disk space monitoring
  disk_space_min_gb: 5.0            # WARNING threshold
  disk_space_stop_gb: 2.0           # HARD STOP threshold
  
  # result.h5 auto-cleanup
  result_cleanup_enabled: true
  result_retention_days: 30         # keep 30 days
  result_cleanup_max_files: 1000    # guard against corruption
  
  # Factor library limits
  factor_library_max_entries: 10000
  sqlite_migration_threshold: 50000
```

---

## 5. Key Design Decisions

### 5.1 Daily Token Reset Logic

**Challenge:** ProviderPool tracks `total_tokens` across all time, not daily.

**Solution:**
```python
class ResourceManager:
    def __init__(self):
        self._daily_token_file = Path.home() / ".cache" / "quantaalpha" / "daily_tokens.json"
        self._load_daily_tokens()
    
    def _load_daily_tokens(self):
        """Load or initialize daily token tracking."""
        today = datetime.now().date().isoformat()
        if self._daily_token_file.exists():
            data = json.loads(self._daily_token_file.read_text())
            if data.get("date") == today:
                self._tokens_today = data.get("tokens", 0)
            else:
                self._tokens_today = 0
        else:
            self._tokens_today = 0
    
    def _save_daily_tokens(self):
        """Persist daily token count."""
        data = {
            "date": datetime.now().date().isoformat(),
            "tokens": self._tokens_today
        }
        self._daily_token_file.parent.mkdir(parents=True, exist_ok=True)
        self._daily_token_file.write_text(json.dumps(data))
```

### 5.2 Disk Space Calculation

**Cross-Platform:** Use `shutil.disk_usage()` which works on Linux/macOS/Windows.

```python
import shutil

def get_disk_space_gb(path: str = "/") -> float:
    """Return available disk space in GB."""
    total, used, free = shutil.disk_usage(path)
    return free / (1024**3)
```

### 5.3 result.h5 Cleanup

**Location:** Per workspace in `data/results/workspace/*/result.h5`

```python
def cleanup_old_results(self, max_age_days: int = 30) -> int:
    """Remove result.h5 files older than max_age_days."""
    results_root = Path("data/results")
    if not results_root.exists():
        return 0
    
    cutoff = datetime.now() - timedelta(days=max_age_days)
    removed = 0
    
    for result_h5 in results_root.rglob("result.h5"):
        mtime = datetime.fromtimestamp(result_h5.stat().st_mtime)
        if mtime < cutoff:
            result_h5.unlink()
            removed += 1
    
    return removed
```

### 5.4 Lazy Import Pattern

**From S04/S06:** Avoid circular imports at module level.

```python
# resource_manager.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quantaalpha.llm.provider_pool import ProviderPool

# Lazy import in method
def _get_provider_pool(self) -> "ProviderPool | None":
    try:
        from quantaalpha.llm.provider_pool import provider_pool
        return provider_pool
    except ImportError:
        return None
```

---

## 6. Testing Strategy

### 6.1 Unit Test Coverage (target: 20+ tests)

| Test Class | Coverage |
|------------|----------|
| `TestResourceConfig` | from_dict, defaults, validation |
| `TestResourceStatus` | status computation |
| `TestTokenTracking` | daily reset, budget enforcement |
| `TestDiskSpace` | space calculation, thresholds |
| `TestResultCleanup` | file age filtering, dry-run |
| `TestFactorLibraryLimits` | entry count, migration check |
| `TestEnforcementGate` | allowed/blocked scenarios |

### 6.2 Integration Points to Test

1. **loop.py integration:** Verify resource check called before each iteration
2. **provider_pool.py integration:** Verify token usage pulled correctly
3. **library.py integration:** Verify entry limits enforced

---

## 7. Known Limitations & Dependencies

### 7.1 Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| S04 ProviderPool | ✅ Complete | `get_token_usage_report()` exists |
| S06 Checkpoint | ✅ Complete | Integration pattern established |
| `shutil.disk_usage` | ✅ Built-in | Cross-platform disk space |
| `json` for daily tokens | ✅ Built-in | Simple persistence |

### 7.2 Out of Scope

- **SQLite migration:** D018 mentions it but implementation requires separate planning
- **Multi-machine coordination:** Assume single-node operation
- **Real-time token streaming:** Daily snapshots only (sufficient for budget)

### 7.3 Risks

| Risk | Mitigation |
|------|------------|
| ProviderPool singleton returns `None` | Check `if pool is None` before calling |
| Disk space check on network mounts | Use `shutil.disk_usage()` which handles most cases |
| result.h5 files locked by other processes | Add try/except with WARNING log |

---

## 8. Files to Create/Modify

### 8.1 Create

| File | Purpose |
|------|---------|
| `third_party/quantaalpha/quantaalpha/pipeline/resource_manager.py` | Core ResourceManager class |
| `third_party/quantaalpha/tests/test_resource_manager.py` | Unit tests (20+ tests) |

### 8.2 Modify

| File | Changes |
|------|---------|
| `third_party/quantaalpha/quantaalpha/pipeline/loop.py` | Add resource_mgr check in run() |
| `third_party/quantaalpha/quantaalpha/factors/library.py` | Add entry count limit check |
| `third_party/quantaalpha/quantaalpha/factors/prompts/experiment.yaml` | Add resource_management: section |

### 8.3 Configuration

| File | Section |
|------|---------|
| `third_party/quantaalpha/configs/experiment.yaml` | Add `resource_management:` section |

---

## 9. Verification Plan

```bash
# 1. Syntax check
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/resource_manager.py

# 2. Unit tests
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M003
python -m pytest third_party/quantaalpha/tests/test_resource_manager.py -v

# 3. Integration: token budget exceeded
# - Set daily_token_limit: 1000
# - Run loop, verify WARNING logged

# 4. Integration: disk space warning
# - Mock shutil.disk_usage to return <5GB
# - Verify WARNING logged

# 5. Cleanup test
# - Create old result.h5 files
# - Run cleanup
# - Verify files removed
```

---

## 10. Milestone Alignment

| Checkpoint | Status |
|------------|--------|
| S04 ProviderPool | ✅ Complete |
| S06 Checkpoint | ✅ Complete |
| S08 ResourceManager | 📋 Research Complete |
| S09 M001 Lessons | ⏳ Pending |
| S10 ADR-003 Phase 3 | ⏳ Pending |

**S08 unblocks:** S09 (M001 lessons test), S10 (ADR-003 orchestration)

---

## 11. Recommendation

**Proceed to S08-IMPLEMENTATION** with the following concrete plan:

1. Create `resource_manager.py` with:
   - `ResourceConfig` dataclass
   - `ResourceStatus` dataclass
   - `ResourceManager` class with all 4 enforcement mechanisms

2. Create unit tests following S04 pattern (26 tests)

3. Modify `loop.py` to integrate resource check

4. Add `resource_management:` section to `experiment.yaml`

5. Add factor library entry limit integration to `library.py`

**Estimated:** 1 implementation session + 1 testing session

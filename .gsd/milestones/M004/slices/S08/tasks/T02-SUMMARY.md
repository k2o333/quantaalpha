---
id: T02
parent: S08
milestone: M004
status: completed
verification_result: passed
completed_at: 2026-03-24
blocker_discovered: false
observability_surfaces:
  - "quantaalpha/continuous/DESIGN.md"
  - "quantaalpha/continuous/scheduler.py:SchedulerConfig"
---

# T02: 技术选型评估

**Status:** Completed

## What was done

Evaluated and documented technology choices for the 24H orchestration center.

## Technology Decisions

| Category | Decision | Rationale |
|----------|-----------|-----------|
| **Task Scheduling** | APScheduler | Lightweight, no external dependencies, sufficient for single-machine |
| **Process Management** | Supervisor | Simple config, `supervisorctl` management interface |
| **Data Monitoring** | Filesystem polling | Reliable, upgradeable to inotify later |
| **Vector Store** | ChromaDB | Already integrated in S06, Python-native |
| **Configuration** | YAML + Pydantic | Type safety, validation, defaults |
| **Logging** | Loguru | Already integrated, zero-config structured logs |

## Tech Stack Summary

| Layer | Choice | Alternative |
|-------|--------|-------------|
| Task scheduling | APScheduler | Celery (distributed), Prefect (workflows) |
| Process management | Supervisor | systemd (system-level) |
| Data monitoring | Polling | inotify (real-time) |
| Vector store | ChromaDB | sqlite-vss, Milvus |
| Configuration | Pydantic dataclass | JSON, env vars |
| Logging | Loguru | Grafana + Loki (later) |

## Diagnostics

```bash
# View technology decisions
cat quantaalpha/continuous/DESIGN.md | grep -A 20 "技术选型"
```

## Verification Evidence

| Check | Command | Exit | Result |
|-------|---------|------|--------|
| Design doc exists | `ls -la continuous/DESIGN.md` | 0 | PASS |
| Has tech comparisons | `grep -c "候选" continuous/DESIGN.md` | 0 | 6+ entries |
| Has recommendations | `grep -c "推荐" continuous/DESIGN.md` | 0 | 6+ entries |

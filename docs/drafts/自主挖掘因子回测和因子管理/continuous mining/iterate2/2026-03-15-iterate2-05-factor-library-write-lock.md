# Iterate 2.5: 因子库写入保护

Status: draft
Priority: P1
Depends-on: 2026-03-15-iterate2-04-external-scheduler-summary-and-audit.md

---

## 一、目标

为 `all_factors_library.json` 或其他因子库 JSON 文件增加最小并发写保护，避免多进程或调度重叠时写坏文件。

本迭代只做“最小治理增强”：

- 保护当前 JSON 方案
- 不迁移数据库

---

## 二、范围

包含：

- `FactorLibraryManager._save()` 写锁
- 必要的原子写策略
- 并发写测试

不包含：

- SQLite 迁移
- 分布式锁
- 跨机器协调

---

## 三、代码落点

- `third_party/quantaalpha/quantaalpha/factors/library.py`
- 建议新增：
  - `third_party/quantaalpha/tests/test_factor_library_locking.py`

如果需要临时文件原子替换，可使用：

- `tempfile`
- `os.replace`

---

## 四、开发方案

### 4.1 锁策略

优先方案：

- 在 `_save()` 里使用文件锁
- 写入临时文件后再 `os.replace()`

这样可以同时解决：

- 并发写交叉覆盖
- 写到一半进程退出导致 JSON 半截损坏

### 4.2 失败处理

要求：

- 获取锁失败时应有明确日志
- 写入失败不能破坏原文件
- 解锁动作必须在 `finally` 中完成

### 4.3 兼容性约束

- 不改变 `FactorLibraryManager` 对外接口
- 单进程场景下性能退化应尽量小
- Linux 环境优先；如果锁实现有平台差异，需要在文档中写明

---

## 五、测试方案

### 5.1 单元测试

新增 `test_factor_library_locking.py`，至少覆盖：

1. 正常写入仍可成功
2. 并发连续写入后 JSON 仍可解析
3. 写入失败时原文件仍保持有效 JSON
4. 原子替换后 `last_updated` 等字段仍正确

### 5.2 并发测试

可使用多线程或多进程模拟两个 writer：

- writer A 连续写
- writer B 连续写

最终检查：

- 文件存在
- JSON 可读
- 没有半截内容

### 5.3 手工验收

用两个终端同时运行会写库的命令，结束后确认：

- 因子库仍是合法 JSON
- 没有出现明显截断或空文件

---

## 六、验收标准

1. `_save()` 增加了最小并发写保护
2. 因子库写入失败不会破坏旧文件
3. 并发测试可稳定通过
4. 不引入数据库迁移或大规模重构

---

## 七、交付产物

- 带锁和原子写的 `library.py`
- `test_factor_library_locking.py`
- 并发写验证记录

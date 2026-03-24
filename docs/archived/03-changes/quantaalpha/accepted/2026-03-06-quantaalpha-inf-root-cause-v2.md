Status: accepted
Owner: AI Assistant
Created: 2026-03-06
Outcome: accepted

# QuantaAlpha 回测 `inf/-inf/NaN` 问题纠错结论

## 结论

原文档中“`SH000300` 底层行情数据已损坏”的表述不准确。

更准确的结论是：

1. 文档描述的现象是对的：`SH000300` 的 `$close` 被 Qlib 读取后，确实表现为交替的 `0` 和极大值。
2. 根因不是“数据损坏”，而是 **指数 `bin` 文件的编码格式与 Qlib 的读取协议不匹配**。
3. 数据本身并没有坏：按脚本自己的写入格式解析，收盘价序列是正常的沪深 300 指数数据。

这也是为什么回测中会出现：

- benchmark return 为 `inf`
- excess return 为 `-inf`
- `std` / `information_ratio` 为 `NaN`

因为 benchmark 使用的是 `SH000300`，而 `bench` 实际来自：

```python
$close / Ref($close, 1) - 1
```

一旦 `$close` 被错误解码成 `0` 和极大值交替，收益序列就会自然变成 `-1.0` 和 `inf` 交替。

## 原文需要修正的点

原文中这句：

> `SH000300` 在当前 Qlib provider 中的原始行情文件已损坏，导致 benchmark 收益序列错误。

应改为：

> `SH000300` 的特征文件编码格式不符合 Qlib `FileFeatureStorage` 的 `bin` 规范，导致 Qlib 按错误布局解释二进制内容，进而生成错误的 benchmark 收益序列。

另外，工程师给出的“Qlib 期望读取：纯 `float32[]`”这个说法也不够准确。

Qlib 本地实现读取的并不是“完全无头部的纯值数组”，而是：

```text
float32(start_index) + float32[data...]
```

也就是：

1. 第 1 个 `float32` 是起始日历索引
2. 后续每个 `float32` 才是特征值

所以问题不只是“不能写时间戳和长度头”，还包括“不能把起始索引头也去掉”。

## 证据摘要

### 1. 指数脚本的实际写入格式不符合 Qlib 规范

[add_index_to_qlib.py](/home/quan/testdata/aspipe_v4/third_party/scripts/dataconvert/add_index_to_qlib.py) 当前写入 `*.day.bin` 的逻辑是：

```text
int32(len) + int64[timestamps] + float32[values]
```

脚本里明确做了三段写入：

1. 先写记录数 `int32`
2. 再写 Unix 时间戳数组 `int64[]`
3. 最后写价格数组 `float32[]`

这不是 Qlib `FileFeatureStorage` 使用的 `bin` 格式。

### 2. Qlib 的实际读取协议是 `float32(start_index) + float32[data...]`

本地 Qlib 源码位于：

- [file_storage.py](/root/miniforge3/envs/mining/lib/python3.12/site-packages/qlib/data/storage/file_storage.py)

其中 `FileFeatureStorage` 的实现表明：

1. `start_index` 通过读取前 4 个字节并按 `float32` 解释得到
2. 后续数据也统一按小端 `float32` 顺序读取
3. `len = 文件大小 / 4 - 1`
4. 写入时对应逻辑就是 `np.hstack([index, data_array]).astype("<f").tofile(fp)`

这说明 Qlib 并不会读取：

- `int32(len)`
- `int64[] timestamps`

也不会根据文件内时间戳对齐日期。

### 3. 正常股票文件可作为直接对照

正常股票文件例如：

- [close.day.bin](/home/quan/testdata/aspipe_v4/third_party/data/qlib_data_csi300_bin/features/000001.sz/close.day.bin)

按 `float32` 顺序解释，前几项是：

```text
[0.0, 7.2396798, 7.28441, 7.36748, ...]
```

这符合 Qlib 约定：

1. 第一个值是起始索引 `0.0`
2. 后面才是连续的收盘价

而指数文件：

- [close.day.bin](/home/quan/testdata/aspipe_v4/third_party/data/qlib_data_csi300_bin/features/sh000300/close.day.bin)

按同样方式解释，前几项变成：

```text
[3.405155e-42, 7.5707389e13, 0.0, 7.6432164e13, 0.0, ...]
```

这正是把：

- `int32(len)` 的字节
- `int64(timestamp)` 的高低位字节

误当成 `float32` 后出现的错位结果。

### 4. 错位读取会直接产生 `-1.0 / inf`

当 `SH000300` 的 `$close` 被读成如下模式：

```text
0, 极大值, 0, 极大值, ...
```

则：

```text
$close / Ref($close, 1) - 1
```

会对应变成：

```text
-1.0, inf, -1.0, inf, ...
```

这与 `report_normal_1day.pkl` 中异常的 `bench` 列完全一致，因此现象链路是闭合的，但根因应描述为“格式不匹配”，不是“行情值本身坏掉”。

## 正确修复方案

应修改：

- [add_index_to_qlib.py](/home/quan/testdata/aspipe_v4/third_party/scripts/dataconvert/add_index_to_qlib.py)

修复方向应为：

1. 按 Qlib `FileFeatureStorage` 的 `bin` 规范写入指数特征文件
2. 文件格式应为：

```text
float32(start_index) + float32[data...]
```

3. `start_index` 不是任意起始偏移，而必须对应 Qlib 交易日历 `calendars/day.txt` 中该标的数据起始日期所在的行号索引（0-based）
4. 后续值序列必须与交易日历按日对齐
5. 重新生成 `features/sh000300/*.day.bin`
6. 重新运行 benchmark 验证，确认 `$close` 和 `bench` 恢复正常

`start_index` 的计算方式可以明确为：

```python
calendar = pd.read_csv(
    QLIB_DATA_DIR / "calendars" / "day.txt",
    header=None,
    names=["date"],
)
calendar["date"] = pd.to_datetime(calendar["date"])
data_start_date = pd.to_datetime(df["trade_date"].min(), format="%Y%m%d")
start_index = calendar[calendar["date"] == data_start_date].index[0]
```

如果 `start_index` 算错，即使文件不再被错位解码，Qlib 仍会把价格序列映射到错误的交易日上，最终使 benchmark 收益出现日期错位偏差。

不建议采用以下表述作为修复方案：

1. “改成 pkl 格式，与股票数据一致”
2. “改成纯 float32 数组，去掉头部”

原因是：

1. 当前股票 Qlib 特征数据本身就是 `bin`，不是 `pkl`
2. Qlib `bin` 仍然有一个 `start_index` 头部，不能简单理解为“纯值数组”

## 额外工程建议

下面这些建议是合理的，但它们属于“修复后的防回归和可维护性增强”，不是本次根因结论成立所必需的前提：

1. 在修复 `add_index_to_qlib.py` 后增加 round-trip 验证
2. 增加一个批量检查脚本，对 `features/` 下所有 `*.day.bin` 的头部做基本格式校验

例如，脚本在写完后可以立刻用 Qlib 自己的读取接口回读：

```python
from qlib.data.storage.file_storage import FileFeatureStorage

storage = FileFeatureStorage(
    instrument=qlib_code.lower(),
    field="close",
    freq="day",
    provider_uri={"day": str(QLIB_DATA_DIR)},
)
print(f"start_index={storage.start_index}, len={len(storage)}")
print(storage[storage.start_index : storage.start_index + 5])
```

这类验证的价值在于：它能尽早发现“写入格式看似成功、但 Qlib 实际读取结果错误”的问题，适合作为脚本自检或 CI 数据检查步骤。

## 最终建议

如果要更新原排查结论，推荐使用下面这句作为最终版本：

> 本次 `inf/-inf/NaN` 的直接触发点是 benchmark `SH000300` 的 `close.day.bin` 被 Qlib 错误解码；根因不是指数行情数据损坏，而是 `add_index_to_qlib.py` 写出的 `bin` 文件格式不符合 Qlib `FileFeatureStorage` 的读取规范。

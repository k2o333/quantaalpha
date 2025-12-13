# 接口下载速度测试脚本

本项目包含多个用于测试接口下载速度和数据量的脚本：

## 主要测试脚本

### download_speed_test.py
全面测试所有接口的下载性能，下载每个接口最近3个月的数据。

**使用方法：**
```bash
python test/download_speed_test.py
```

### enhanced_download_speed_test_fixed.py ✅ (推荐用于大容量测试)
增强版测试脚本，修复了原始脚本中的参数问题，成功实现了大量数据下载。
**关键结果**：此脚本产生了项目总结中提到的大数据量成果，如日线数据接口320,551条记录等。

**使用方法：**
```bash
python test/enhanced_download_speed_test_fixed.py
```

### high_volume_download_test.py
高容量数据下载测试，专门用于测试每个接口下载2万条以上数据的能力。
**注意**：此脚本在资源受限环境下可能因内存不足而失败。

**使用方法：**
```bash
python test/high_volume_download_test.py
```

### quick_interface_verification.py ✅ (推荐)
快速接口验证脚本，验证所有接口都能正常返回数据。

**使用方法：**
```bash
python test/quick_interface_verification.py
```

## 辅助脚本

### quick_interface_check.py
轻量级接口检查脚本，适合日常快速检查。

**使用方法：**
```bash
python test/quick_interface_check.py
```

## 测试报告

- `download_speed_test_report.md` - 原始测试的详细性能分析报告
- `final_performance_report.md` - 最终性能优化报告

## 运行脚本

### run_speed_test.sh
交互式运行脚本，方便选择不同的测试。

**使用方法：**
```bash
bash test/run_speed_test.sh
```

## 重要改进

1. **问题修复**：解决了原始测试中部分接口无数据返回的问题
2. **性能优化**：实现了大容量数据下载能力（每个接口可达2万条以上）
3. **稳定性提升**：增加了完善的错误处理和重试机制
4. **兼容性增强**：更好地适配不同积分等级的用户权限

## 使用建议

- 日常检查：使用 `quick_interface_verification.py`
- 性能测试：使用 `high_volume_download_test.py`
- 详细分析：查看 `final_performance_report.md`
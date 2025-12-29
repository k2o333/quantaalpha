# aspipe_v4 融合重构版 (App4) - 配置驱动架构

这是 aspipe_v4 的全新重构版本，采用了配置驱动的设计理念。所有的接口逻辑都定义在 YAML 配置文件中，由通用下载器根据配置执行下载任务。

## 特性

1. **全配置化接口**：新增接口只需编写YAML文件，无需修改Python代码
2. **统一下载引擎**：`GenericDownloader` 根据YAML指令运行
3. **灵活控制**：YAML中控制分页、代理、限流
4. **标准化处理**：YAML定义输出字段、类型、主键
5. **极简维护**：维护者无需深入了解类结构
6. **完全兼容**：保持CLI参数兼容性

## 目录结构

```
app4/
├── config/
│   ├── settings.yaml          # 全局配置（Token, 默认重试次数, 全局代理root等）
│   └── interfaces/            # 接口定义目录
│       ├── daily.yaml         # 日线行情配置
│       ├── pro_bar.yaml       # 复权行情配置
│       ├── stock_basic.yaml   # 股票列表配置
│       └── ... (其他接口)
├── core/
│   ├── __init__.py
│   ├── config_loader.py       # 配置加载器
│   ├── downloader.py          # 通用下载器
│   ├── processor.py           # 数据处理器
│   ├── storage.py             # 存储管理器
│   ├── cache_manager.py       # 缓存管理器
│   └── scheduler.py           # 任务调度器
├── main.py                    # 统一CLI入口
├── run.py                     # 启动脚本
├── requirements.txt            # 依赖包
└── __init__.py
```

## 安装依赖

```bash
pip install -r app4/requirements.txt
```

## 使用方法

### 保持原有参数兼容性

```bash
# 运行从指定日期开始的所有数据下载
python app4/main.py --start_date 20230101 --end_date 20231231

# 下载股东数据
python app4/main.py --start_date 20230101 --end_date 20231231 --holders-data

# 仅下载pro_bar数据
python app4/main.py --start_date 20230101 --end_date 20231231 --pro-bar-only

# 全历史数据下载
python app4/main.py --start_date 20230101 --end_date 20231231 --tscode-historical
```

### 新增参数

```bash
# 指定特定接口
python app4/main.py --interface pro_bar --start_date 20230101 --end_date 20231231

# 指定接口组
python app4/main.py --group daily --start_date 20230101 --end_date 20231231

# 设置并发数
python app4/main.py --concurrency 16 --start_date 20230101 --end_date 20231231
```

## 配置文件说明

### 全局配置 settings.yaml

包含全局设置如API密钥、并发设置、缓存配置等。

### 接口配置

每个接口都有对应的YAML配置文件，包含：

1. **基础元数据**：接口标识和描述
2. **权限与限制**：积分要求和流控设置
3. **请求配置**：HTTP方法、超时等
4. **输入参数**：字段定义与校验
5. **分页策略**：分页模式和参数
6. **输出配置**：主键定义和字段类型

## 开发指南

### 添加新接口

1. 在 `config/interfaces/` 目录下创建新的 YAML 配置文件
2. 按照规范填写接口的各项配置
3. 无需修改任何Python代码即可使用新接口

### 修改接口行为

只需编辑对应的 YAML 配置文件，即可改变接口的行为，包括：
- 请求参数
- 分页策略
- 输出字段定义
- 限流设置等

## 优势

1. **极简维护**：维护者不需要懂 Python 类继承结构，只需修改 YAML 文本
2. **解耦**：下载逻辑与业务逻辑完全分离
3. **适应性强**：特殊处理的接口完全可以通过 YAML 配置描述
4. **功能完备**：保留并增强了原有的缓存和并发能力
5. **文档化**：YAML 文件本身就是最好的接口文档
6. **完全兼容**：通过参数映射层，老用户可以继续使用熟悉的 CLI 参数
7. **高性能**：通过全链路异步化和智能缓存，显著提升大数据量下的吞吐能力
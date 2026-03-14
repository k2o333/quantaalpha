
# 基础数据

## 基础信息

---

接口：stock_basic，可以通过[**数据工具**](https://tushare.pro/webclient/)调试和查看数据  
描述：获取基础信息数据，包括股票代码、名称、上市日期、退市日期等  
权限：2000积分起。此接口是基础信息，调取一次就可以拉取完，建议保存倒本地存储后使用

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|TS股票代码|
|name|str|N|名称|
|market|str|N|市场类别 （主板/创业板/科创板/CDR/北交所）|
|list_status|str|N|上市状态 L上市 D退市 P暂停上市，默认是L|
|exchange|str|N|交易所 SSE上交所 SZSE深交所 BSE北交所|
|is_hs|str|N|是否沪深港通标的，N否 H沪股通 S深股通|

**输出参数**

| 名称           | 类型  | 默认显示 | 描述                    |
| ------------ | --- | ---- | --------------------- |
| ts_code      | str | Y    | TS代码                  |
| symbol       | str | Y    | 股票代码                  |
| name         | str | Y    | 股票名称                  |
| area         | str | Y    | 地域                    |
| industry     | str | Y    | 所属行业                  |
| fullname     | str | N    | 股票全称                  |
| enname       | str | N    | 英文全称                  |
| cnspell      | str | Y    | 拼音缩写                  |
| market       | str | Y    | 市场类型（主板/创业板/科创板/CDR）  |
| exchange     | str | N    | 交易所代码                 |
| curr_type    | str | N    | 交易货币                  |
| list_status  | str | N    | 上市状态 L上市 D退市 P暂停上市    |
| list_date    | str | Y    | 上市日期                  |
| delist_date  | str | N    | 退市日期                  |
| is_hs        | str | N    | 是否沪深港通标的，N否 H沪股通 S深股通 |
| act_name     | str | Y    | 实控人名称                 |
| act_ent_type | str | Y    | 实控人企业性质               |

说明：旧版上的PE/PB/股本等字段，请在行情接口[“每日指标”](https://tushare.pro/document/2?doc_id=32)中获取。

**接口示例**

```python

pro = ts.pro_api()

#查询当前所有正常上市交易的股票列表

data = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,list_date')
```

  
或者：  

```python

#查询当前所有正常上市交易的股票列表

data = pro.query('stock_basic', exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,list_date')
```

**数据样例**

```
    ts_code     symbol     name     area industry    list_date
0     000001.SZ  000001  平安银行   深圳       银行  19910403
1     000002.SZ  000002   万科A   深圳     全国地产  19910129
2     000004.SZ  000004  国农科技   深圳     生物制药  19910114
3     000005.SZ  000005  世纪星源   深圳     房产服务  19901210
4     000006.SZ  000006  深振业A   深圳     区域地产  19920427
5     000007.SZ  000007   全新好   深圳     酒店餐饮  19920413
6     000008.SZ  000008  神州高铁   北京     运输设备  19920507
7     000009.SZ  000009  中国宝安   深圳      综合类  19910625
8     000010.SZ  000010  美丽生态   深圳     建筑施工  19951027
9     000011.SZ  000011  深物业A   深圳     区域地产  19920330
10    000012.SZ  000012   南玻A   深圳       玻璃  19920228
11    000014.SZ  000014  沙河股份   深圳     全国地产  19920602
12    000016.SZ  000016  深康佳A   深圳     家用电器  19920327
13    000017.SZ  000017  深中华A   深圳     文教休闲  19920331
14    000018.SZ  000018  神州长城   深圳     装修装饰  19920616
15    000019.SZ  000019  深深宝A   深圳      软饮料  19921012
16    000020.SZ  000020  深华发A   深圳      元器件  19920428
17    000021.SZ  000021   深科技   深圳     电脑设备  19940202
18    000022.SZ  000022  深赤湾A   深圳       港口  19930505
19    000023.SZ  000023  深天地A   深圳     其他建材  19930429
20    000025.SZ  000025   特力A   深圳     汽车服务  19930621
```


## 股本情况（盘前）

---

接口：stk_premarket  
描述：每日开盘前获取当日股票的股本情况，包括总股本和流通股本，涨跌停价格等。  
限量：单次最大8000条数据，可循环提取  
权限：与积分无关，需单独[开权限](https://tushare.pro/document/1?doc_id=290)

  
  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|股票代码|
|trade_date|str|N|交易日期(YYYYMMDD格式，下同)|
|start_date|str|N|开始日期|
|end_date|str|N|结束日期|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|trade_date|str|Y|交易日期|
|ts_code|str|Y|TS股票代码|
|total_share|float|Y|总股本（万股）|
|float_share|float|Y|流通股本（万股）|
|pre_close|float|Y|昨日收盘价|
|up_limit|float|Y|今日涨停价|
|down_limit|float|Y|今日跌停价|

  
  

**接口示例**

```python

pro = ts.pro_api()

#获取某一日盘前所有股票当日的最新股本
df = pro.stk_premarket(trade_date='20240603')

```

  
  

**数据示例**

```
    trade_date    ts_code  total_share  float_share pre_close up_limit down_limit
0      20240603  001387.SZ   17778.8000    4355.7297    17.000   18.700     15.300
1      20240603  600460.SH  166407.1845  166407.1845    18.790   20.670     16.910
2      20240603  603052.SH   13484.8000    4096.4000    30.270   33.300     27.240
3      20240603  603269.SH   22053.6977   22053.6977    10.140   11.150      9.130
4      20240603  001339.SZ   24974.4000    7157.2575    29.210   32.130     26.290
...         ...        ...          ...          ...       ...      ...        ...
5335   20240603  603567.SH   94196.3592   93954.0524    12.340   13.570     11.110
5336   20240603  301188.SZ   23245.0244   15044.4508    17.740   21.290     14.190
5337   20240603  603939.SH  101057.9797  100811.6102    45.060   49.570     40.550
5338   20240603  300441.SZ   65225.6868   63480.0236     6.460    7.750      5.170
5339   20240603  920002.BJ    3175.2120     475.0000      None   77.840     41.920
```

## 交易日历

---

接口：trade_cal，可以通过[**数据工具**](https://tushare.pro/webclient/)调试和查看数据。  
描述：获取各大交易所交易日历数据,默认提取的是上交所  
积分：需2000积分

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|exchange|str|N|交易所 SSE上交所,SZSE深交所,CFFEX 中金所,SHFE 上期所,CZCE 郑商所,DCE 大商所,INE 上能源|
|start_date|str|N|开始日期 （格式：YYYYMMDD 下同）|
|end_date|str|N|结束日期|
|is_open|str|N|是否交易 '0'休市 '1'交易|

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|exchange|str|Y|交易所 SSE上交所 SZSE深交所|
|cal_date|str|Y|日历日期|
|is_open|str|Y|是否交易 0休市 1交易|
|pretrade_date|str|Y|上一个交易日|

**接口示例**

```python

pro = ts.pro_api()


df = pro.trade_cal(exchange='', start_date='20180101', end_date='20181231')
```

或者

```python

df = pro.query('trade_cal', start_date='20180101', end_date='20181231')
```

**数据样例**

```
    exchange  cal_date  is_open
0           SSE  20180101        0
1           SSE  20180102        1
2           SSE  20180103        1
3           SSE  20180104        1
4           SSE  20180105        1
5           SSE  20180106        0
6           SSE  20180107        0
7           SSE  20180108        1
8           SSE  20180109        1
9           SSE  20180110        1
10          SSE  20180111        1
11          SSE  20180112        1
12          SSE  20180113        0
13          SSE  20180114        0
14          SSE  20180115        1
15          SSE  20180116        1
16          SSE  20180117        1
17          SSE  20180118        1
18          SSE  20180119        1
19          SSE  20180120        0
20          SSE  20180121        0
```

## ST股票列表

---

接口：stock_st，可以通过[**数据工具**](https://tushare.pro/webclient/)调试和查看数据。  
描述：获取ST股票列表，可根据交易日期获取历史上每天的ST列表  
权限：3000积分起  
提示：每天上午9:20更新，单次请求最大返回1000行数据，可循环提取,本接口数据从20160101开始,太早历史无法补齐

  
  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|股票代码|
|trade_date|str|N|交易日期（格式：YYYYMMDD下同）|
|start_date|str|N|开始时间|
|end_date|str|N|结束时间|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|股票代码|
|name|str|Y|股票名称|
|trade_date|str|Y|交易日期|
|type|str|Y|类型|
|type_name|str|Y|类型名称|

  
  

**接口用法**

```python

pro = ts.pro_api()

#获取20250813日所有的ST股票
df = pro.stock_st(trade_date='20250813')

```

  
  

**数据样例**

```
             ts_code   name trade_date type type_name
0    300313.SZ  *ST天山   20250813   ST     风险警示板
1    605081.SH  *ST太和   20250813   ST     风险警示板
2    300391.SZ  *ST长药   20250813   ST     风险警示板
3    300343.SZ   ST联创   20250813   ST     风险警示板
4    300044.SZ   ST赛为   20250813   ST     风险警示板
..         ...    ...        ...  ...       ...
170  300175.SZ   ST朗源   20250813   ST     风险警示板
171  603721.SH  *ST天择   20250813   ST     风险警示板
172  600289.SH   ST信通   20250813   ST     风险警示板
173  000929.SZ  *ST兰黄   20250813   ST     风险警示板
174  000638.SZ  *ST万方   20250813   ST     风险警示板
```

## 沪深港通股票列表

---

接口：stock_hsgt，可以通过[**数据工具**](https://tushare.pro/webclient/)调试和查看数据。  
描述：获取沪深港通股票列表  
权限：3000积分起  
提示：每天上午9:20更新，单次请求最大返回2000行数据，可根据类型循环提取,本接口数据从20250812开始

  
  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|股票代码|
|trade_date|str|N|交易日期（格式：YYYYMMDD）|
|type|str|Y|类型（参考下表）|
|start_date|str|N|开始时间|
|end_date|str|N|结束时间|

类型说明如下：

|类型|类型名称|
|---|---|
|HK_SZ|深股通(港>深)|
|SZ_HK|港股通(深>港)|
|HK_SH|沪股通(港>沪)|
|SH_HK|港股通(沪>港)|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|股票代码|
|trade_date|str|Y|交易日期|
|type|str|Y|类型|
|name|str|Y|股票名称|
|type_name|str|Y|类型名称|

  
  

**接口用法**

```python

pro = ts.pro_api()

#获取20250813日深股通的股票列表
df = pro.stock_hsgt(trade_date='20250813',type='HK_SZ')

```

  
  

**数据样例**

```
             ts_code trade_date   type     name type_name
0    001258.SZ   20250813  HK_SZ     立新能源  深股通(港>深)
1     00019.HK   20250813  SZ_HK  太古股份公司A  港股通(深>港)
2    000513.SZ   20250813  HK_SZ     丽珠集团  深股通(港>深)
3    002044.SZ   20250813  HK_SZ     美年健康  深股通(港>深)
4    000338.SZ   20250813  HK_SZ     潍柴动力  深股通(港>深)
..         ...        ...    ...      ...       ...
995  300206.SZ   20250813  HK_SZ     理邦仪器  深股通(港>深)
996   02331.HK   20250813  SH_HK       李宁  港股通(沪>港)
997   01855.HK   20250813  SH_HK     中庆股份  港股通(沪>港)
998  300726.SZ   20250813  HK_SZ     宏达电子  深股通(港>深)
999   06127.HK   20250813  SH_HK     昭衍新药  港股通(沪>港)
```

## 股票曾用名

---

接口：namechange  
描述：历史名称变更记录

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|TS代码|
|start_date|str|N|公告开始日期|
|end_date|str|N|公告结束日期|

**输出参数**

|名称|类型|默认输出|描述|
|---|---|---|---|
|ts_code|str|Y|TS代码|
|name|str|Y|证券名称|
|start_date|str|Y|开始日期|
|end_date|str|Y|结束日期|
|ann_date|str|Y|公告日期|
|change_reason|str|Y|变更原因|

**接口示例**

```python

pro = ts.pro_api()

df = pro.namechange(ts_code='600848.SH', fields='ts_code,name,start_date,end_date,change_reason')
```

**数据样例**

```
    ts_code    name    start_date   end_date      change_reason
0  600848.SH   上海临港   20151118      None         改名
1  600848.SH   自仪股份   20070514  20151117         撤销ST
2  600848.SH   ST自仪     20061026  20070513         完成股改
3  600848.SH   SST自仪   20061009  20061025        未股改加S
4  600848.SH   ST自仪     20010508  20061008         ST
5  600848.SH   自仪股份  19940324  20010507         其他
```

## 上市公司基本信息

---

接口：stock_company，可以通过[**数据工具**](https://tushare.pro/webclient/)调试和查看数据。  
描述：获取上市公司基础信息，单次提取4500条，可以根据交易所分批提取  
积分：用户需要至少120积分才可以调取，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

**输入参数**

|名称|类型|必须|描述|
|---|---|---|---|
|ts_code|str|N|股票代码|
|exchange|str|N|交易所代码 ，SSE上交所 SZSE深交所 BSE北交所|

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|股票代码|
|com_name|str|Y|公司全称|
|com_id|str|Y|统一社会信用代码|
|exchange|str|Y|交易所代码|
|chairman|str|Y|法人代表|
|manager|str|Y|总经理|
|secretary|str|Y|董秘|
|reg_capital|float|Y|注册资本(万元)|
|setup_date|str|Y|注册日期|
|province|str|Y|所在省份|
|city|str|Y|所在城市|
|introduction|str|N|公司介绍|
|website|str|Y|公司主页|
|email|str|Y|电子邮件|
|office|str|N|办公室|
|employees|int|Y|员工人数|
|main_business|str|N|主要业务及产品|
|business_scope|str|N|经营范围|

**接口示例**

```python
pro = ts.pro_api()

#或者
#pro = ts.pro_api('your token')

df = pro.stock_company(exchange='SZSE', fields='ts_code,chairman,manager,secretary,reg_capital,setup_date,province')
```

**数据示例**

```
                ts_code chairman manager secretary   reg_capital setup_date province  \
0     000001.SZ      谢永林     胡跃飞        周强  1.717041e+06   19871222       广东   
1     000002.SZ       郁亮     祝九胜        朱旭  1.103915e+06   19840530       广东   
2     000003.SZ      马钟鸿     马钟鸿        安汪  3.334336e+04   19880208       广东   
3     000004.SZ      李林琳     李林琳       徐文苏  8.397668e+03   19860505       广东   
4     000005.SZ       丁芃     郑列列       罗晓春  1.058537e+05   19870730       广东   
5     000006.SZ      赵宏伟     朱新宏        杜汛  1.349995e+05   19850525       广东   
6     000007.SZ      智德宇     智德宇       陈伟彬  3.464480e+04   19830311       广东   
7     000008.SZ      王志全      钟岩       王志刚  2.818330e+05   19891011       北京   
8     000009.SZ      陈政立     陈政立       郭山清  2.149345e+05   19830706       广东   
9     000010.SZ       曾嵘     李德友       金小刚  8.198547e+04   19881231       广东   
10    000011.SZ      刘声向     王航军       范维平  5.959791e+04   19830117       广东   
11    000012.SZ       陈琳      王健       杨昕宇  2.863277e+05   19840910       广东   
12    000013.SZ      厉怒江     阮克竖       刘渝敏  3.033550e+04   19920114       广东   
13    000014.SZ       陈勇      温毅        王凡  2.017052e+04   19870727       广东   
14    000015.SZ      宿南南      马骧       蒋孝安  1.598761e+05   19880408       广东   
15    000016.SZ      刘凤喜      周彬       吴勇军  2.407945e+05   19801001       广东  
```

## 上市公司管理层

---

接口：stk_managers  
描述：获取上市公司管理层  
积分：用户需要2000积分才可以调取，5000积分以上频次相对较高，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

  
  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|股票代码，支持单个或多个股票输入|
|ann_date|str|N|公告日期（YYYYMMDD格式，下同）|
|start_date|str|N|公告开始日期|
|end_date|str|N|公告结束日期|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|TS股票代码|
|ann_date|str|Y|公告日期|
|name|str|Y|姓名|
|gender|str|Y|性别|
|lev|str|Y|岗位类别|
|title|str|Y|岗位|
|edu|str|Y|学历|
|national|str|Y|国籍|
|birthday|str|Y|出生年月|
|begin_date|str|Y|上任日期|
|end_date|str|Y|离任日期|
|resume|str|N|个人简历|

  
  

**接口用例**

```python

pro = ts.pro_api()

#获取单个公司高管全部数据
df = pro.stk_managers(ts_code='000001.SZ')

#获取多个公司高管全部数据
df = pro.stk_managers(ts_code='000001.SZ,600000.SH')
```

  
  

**数据样例**

```
    ts_code  ann_date     name    gender  ... national  birthday begin_date  end_date
0    000001.SZ  20190604  姚贵平      M  ...       中国     1961   20180815  20190604
1    000001.SZ  20190604  姚贵平      M  ...       中国     1961   20170629  20190604
2    000001.SZ  20190604  姚贵平      M  ...       中国     1961   20180129  20190604
3    000001.SZ  20190309   吴鹏      M  ...       中国     1965   20110817  20190309
4    000001.SZ  20190307  孙永桢      F  ...       中国     1968   20181025      None
5    000001.SZ  20180816  杨志群      M  ...       中国     1970   20180815      None
6    000001.SZ  20180816  郭世邦      M  ...       中国     1965   20180815      None
7    000001.SZ  20180405  何之江      M  ...       中国     1965   20170513  20180405
8    000001.SZ  20180203  项有志      M  ...       中国     1964   20170913      None
9    000001.SZ  20180130  杨如生      M  ...       中国   196802   20161107      None
10   000001.SZ  20180130  蔡方方      F  ...       中国     1974   20161107      None
11   000001.SZ  20180130  郭田勇      M  ...       中国   196808   20161107      None
12   000001.SZ  20180130   郭建      M  ...       中国     1964   20161107      None
13   000001.SZ  20180130  杨如生      M  ...       中国   196802   20161107      None
14   000001.SZ  20180130  杨如生      M  ...       中国   196802   20161107      None
15   000001.SZ  20180130   姚波      M  ...       中国     1971   20101227      None
16   000001.SZ  20180130  王春汉      M  ...       中国     1951   20160811      None
17   000001.SZ  20180130  郭田勇      M  ...       中国   196808   20160811      None
18   000001.SZ  20180130  郭田勇      M  ...       中国   196808   20160811      None
19   000001.SZ  20180130  韩小京      M  ...       中国     1955   20140121      None
20   000001.SZ  20180130  陈心颖      F  ...      新加坡     1977   20140121      None
21   000001.SZ  20180130  蔡方方      F  ...       中国     1974   20140121      None
22   000001.SZ  20180130  王松奇      M  ...       中国     1952   20140121      None
23   000001.SZ  20180130  王春汉      M  ...       中国     1951   20140121      None
24   000001.SZ  20180130  韩小京      M  ...       中国     1955   20140121      None
```

## 管理层薪酬和持股

---

接口：stk_rewards  
描述：获取上市公司管理层薪酬和持股  
积分：用户需要2000积分才可以调取，5000积分以上频次相对较高，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

  
  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|Y|TS股票代码，支持单个或多个代码输入|
|end_date|str|N|报告期|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|TS股票代码|
|ann_date|str|Y|公告日期|
|end_date|str|Y|截止日期|
|name|str|Y|姓名|
|title|str|Y|职务|
|reward|float|Y|报酬|
|hold_vol|float|Y|持股数|

  
  

**接口用例**

```python

pro = ts.pro_api()

#获取单个公司高管全部数据
df = pro.stk_rewards(ts_code='000001.SZ')

#获取多个公司高管全部数据
df = pro.stk_rewards(ts_code='000001.SZ,600000.SH')
```

  
  

**数据样例**

```
     ts_code    ann_date  end_date      name     title     reward  hold_vol
0    000001.SZ  20190808  20190630  谢永林       董事长        NaN       0.0
1    000001.SZ  20190808  20190630  胡跃飞     董事,行长        NaN    4104.0
2    000001.SZ  20190808  20190630  陈心颖        董事        NaN       0.0
3    000001.SZ  20190808  20190630   姚波        董事        NaN       0.0
4    000001.SZ  20190808  20190630  叶素兰        董事        NaN       0.0
5    000001.SZ  20190808  20190630  韩小京      独立董事        NaN       0.0
6    000001.SZ  20190808  20190630  蔡方方        董事        NaN       0.0
7    000001.SZ  20190808  20190630   郭建        董事        NaN       0.0
8    000001.SZ  20190808  20190630  郭世邦    董事,副行长        NaN       0.0
9    000001.SZ  20190808  20190630  王春汉      独立董事        NaN       0.0
10   000001.SZ  20190808  20190630  王松奇      独立董事        NaN       0.0
11   000001.SZ  20190808  20190630  郭田勇      独立董事        NaN       0.0
12   000001.SZ  20190808  20190630  杨如生      独立董事        NaN       0.0
13   000001.SZ  20190808  20190630   邱伟  监事长,职工监事        NaN       0.0
14   000001.SZ  20190808  20190630  车国宝      股东监事        NaN       0.0
15   000001.SZ  20190808  20190630  周建国      外部监事        NaN       0.0
16   000001.SZ  20190808  20190630  骆向东      外部监事        NaN       0.0
17   000001.SZ  20190808  20190630  储一昀      外部监事        NaN       0.0
18   000001.SZ  20190808  20190630  孙永桢      职工监事        NaN       0.0
```

## 北交所新旧代码对照表

---

接口：bse_mapping  
描述：获取北交所股票代码变更后新旧代码映射表数据  
限量：单次最大1000条（本接口总数据量300以内）  
积分：120积分即可调取

  
  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|o_code|str|N|旧代码|
|n_code|str|N|新代码|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|name|str|Y|股票名称|
|o_code|str|Y|原代码|
|n_code|str|Y|新代码|
|list_date|str|Y|上市日期|

  
  

**接口示例**

```python

#获取方大新材新旧代码对照数据
df = pro.bse_mapping(o_code='838163.BJ')


#获取全部变更的股票代码对照表
df = pro.bse_mapping()

```

  
  

**数据示例**

```
      name     o_code   n_code    list_date
0  方大新材  838163.BJ  920163.BJ  20200727
```

## IPO新股列表

---

接口：new_share  
描述：获取新股上市列表数据  
限量：单次最大2000条，总量不限制  
积分：用户需要至少120积分才可以调取，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|start_date|str|N|上网发行开始日期|
|end_date|str|N|上网发行结束日期|

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|TS股票代码|
|sub_code|str|Y|申购代码|
|name|str|Y|名称|
|ipo_date|str|Y|上网发行日期|
|issue_date|str|Y|上市日期|
|amount|float|Y|发行总量（万股）|
|market_amount|float|Y|上网发行总量（万股）|
|price|float|Y|发行价格|
|pe|float|Y|市盈率|
|limit_amount|float|Y|个人申购上限（万股）|
|funds|float|Y|募集资金（亿元）|
|ballot|float|Y|中签率|

**接口示例**

```python

pro = ts.pro_api()

df = pro.new_share(start_date='20180901', end_date='20181018')
```

**数据示例**

```
  ts_code       sub_code  name  ipo_date    issue_date   amount  market_amount  \
0   002939.SZ   002939  长城证券  20181017       None  31034.0        27931.0   
1   002940.SZ   002940   昂利康  20181011   20181023   2250.0         2025.0   
2   601162.SH   780162  天风证券  20181009   20181019  51800.0        46620.0   
3   300694.SZ   300694  蠡湖股份  20180927   20181015   5383.0         4845.0   
4   300760.SZ   300760  迈瑞医疗  20180927   20181016  12160.0        10944.0   
5   300749.SZ   300749  顶固集创  20180913   20180925   2850.0         2565.0   
6   002937.SZ   002937  兴瑞科技  20180912   20180926   4600.0         4140.0   
7   601577.SH   780577  长沙银行  20180912   20180926  34216.0        30794.0   
8   603583.SH   732583  捷昌驱动  20180911   20180921   3020.0         2718.0   
9   002936.SZ   002936  郑州银行  20180907   20180919  60000.0        54000.0   
10  300748.SZ   300748  金力永磁  20180906   20180921   4160.0         3744.0   
11  603810.SH   732810  丰山集团  20180906   20180917   2000.0         2000.0   
12  002938.SZ   002938  鹏鼎控股  20180905   20180918  23114.0        20803.0   

    price     pe  limit_amount   funds  ballot  
0    6.31  22.98          9.30  19.582    0.16  
1   23.07  22.99          0.90   5.191    0.03  
2    1.79  22.86         15.50   0.000    0.25  
3    9.89  22.98          2.15   5.324    0.04  
4   48.80  22.99          3.60  59.341    0.08  
5   12.22  22.99          1.10   3.483    0.03  
6    9.94  22.99          1.80   4.572    0.04  
7    7.99   6.97         10.20  27.338    0.17  
8   29.17  22.99          1.20   8.809    0.03  
9    4.59   6.50         18.00  27.540    0.25  
10   5.39  22.98          1.20   2.242    0.05  
11  25.43  20.39          2.00   5.086    0.02  
12  16.07  22.99          6.90  37.145    0.12  
```

## 股票历史列表（历史每天股票列表）

---

接口：bak_basic  
描述：获取备用基础列表，数据从2016年开始  
限量：单次最大7000条，可以根据日期参数循环获取历史，正式权限需要5000积分。

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|trade_date|str|N|交易日期|
|ts_code|str|N|股票代码|

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|trade_date|str|Y|交易日期|
|ts_code|str|Y|TS股票代码|
|name|str|Y|股票名称|
|industry|str|Y|行业|
|area|str|Y|地域|
|pe|float|Y|市盈率（动）|
|float_share|float|Y|流通股本（亿）|
|total_share|float|Y|总股本（亿）|
|total_assets|float|Y|总资产（亿）|
|liquid_assets|float|Y|流动资产（亿）|
|fixed_assets|float|Y|固定资产（亿）|
|reserved|float|Y|公积金|
|reserved_pershare|float|Y|每股公积金|
|eps|float|Y|每股收益|
|bvps|float|Y|每股净资产|
|pb|float|Y|市净率|
|list_date|str|Y|上市日期|
|undp|float|Y|未分配利润|
|per_undp|float|Y|每股未分配利润|
|rev_yoy|float|Y|收入同比（%）|
|profit_yoy|float|Y|利润同比（%）|
|gpr|float|Y|毛利率（%）|
|npr|float|Y|净利润率（%）|
|holder_num|int|Y|股东人数|

**接口示例**

```python

pro = ts.pro_api()

df = pro.bak_basic(trade_date='20211012', fields='trade_date,ts_code,name,industry,pe')
```

**数据样例**

```
 trade_date    ts_code  name industry       pe
0      20211012  300605.SZ  恒锋信息     软件服务  56.4400
1      20211012  301017.SZ  漱玉平民     医药商业  58.7600
2      20211012  300755.SZ  华致酒行     其他商业  23.0000
3      20211012  300255.SZ  常山药业     生物制药  24.9900
4      20211012  688378.SH   奥来德     专用机械  24.9600
...         ...        ...   ...      ...      ...
4529   20211012  688257.SH  新锐股份     机械基件   0.0000
4530   20211012  688255.SH   凯尔达     机械基件   0.0000
4531   20211012  688211.SH  中科微至     专用机械   0.0000
4532   20211012  605567.SH  春雪食品       食品   0.0000
4533   20211012  605566.SH  福莱蒽特     染料涂料   0.0000
```





# 财务数据

## 利润表

---

接口：income，可以通过[**数据工具**](https://tushare.pro/webclient/)调试和查看数据。  
描述：获取上市公司财务利润表数据  
积分：用户需要至少2000积分才可以调取，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)  
  
提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用income_vip接口（参数一致），需积攒5000积分。  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|Y|股票代码|
|ann_date|str|N|公告日期（YYYYMMDD格式，下同）|
|f_ann_date|str|N|实际公告日期|
|start_date|str|N|公告开始日期|
|end_date|str|N|公告结束日期|
|period|str|N|报告期(每个季度最后一天的日期，比如20171231表示年报，20170630半年报，20170930三季报)|
|report_type|str|N|报告类型，参考文档最下方说明|
|comp_type|str|N|公司类型（1一般工商业2银行3保险4证券）|

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|TS代码|
|ann_date|str|Y|公告日期|
|f_ann_date|str|Y|实际公告日期|
|end_date|str|Y|报告期|
|report_type|str|Y|报告类型 见底部表|
|comp_type|str|Y|公司类型(1一般工商业2银行3保险4证券)|
|end_type|str|Y|报告期类型|
|basic_eps|float|Y|基本每股收益|
|diluted_eps|float|Y|稀释每股收益|
|total_revenue|float|Y|营业总收入|
|revenue|float|Y|营业收入|
|int_income|float|Y|利息收入|
|prem_earned|float|Y|已赚保费|
|comm_income|float|Y|手续费及佣金收入|
|n_commis_income|float|Y|手续费及佣金净收入|
|n_oth_income|float|Y|其他经营净收益|
|n_oth_b_income|float|Y|加:其他业务净收益|
|prem_income|float|Y|保险业务收入|
|out_prem|float|Y|减:分出保费|
|une_prem_reser|float|Y|提取未到期责任准备金|
|reins_income|float|Y|其中:分保费收入|
|n_sec_tb_income|float|Y|代理买卖证券业务净收入|
|n_sec_uw_income|float|Y|证券承销业务净收入|
|n_asset_mg_income|float|Y|受托客户资产管理业务净收入|
|oth_b_income|float|Y|其他业务收入|
|fv_value_chg_gain|float|Y|加:公允价值变动净收益|
|invest_income|float|Y|加:投资净收益|
|ass_invest_income|float|Y|其中:对联营企业和合营企业的投资收益|
|forex_gain|float|Y|加:汇兑净收益|
|total_cogs|float|Y|营业总成本|
|oper_cost|float|Y|减:营业成本|
|int_exp|float|Y|减:利息支出|
|comm_exp|float|Y|减:手续费及佣金支出|
|biz_tax_surchg|float|Y|减:营业税金及附加|
|sell_exp|float|Y|减:销售费用|
|admin_exp|float|Y|减:管理费用|
|fin_exp|float|Y|减:财务费用|
|assets_impair_loss|float|Y|减:资产减值损失|
|prem_refund|float|Y|退保金|
|compens_payout|float|Y|赔付总支出|
|reser_insur_liab|float|Y|提取保险责任准备金|
|div_payt|float|Y|保户红利支出|
|reins_exp|float|Y|分保费用|
|oper_exp|float|Y|营业支出|
|compens_payout_refu|float|Y|减:摊回赔付支出|
|insur_reser_refu|float|Y|减:摊回保险责任准备金|
|reins_cost_refund|float|Y|减:摊回分保费用|
|other_bus_cost|float|Y|其他业务成本|
|operate_profit|float|Y|营业利润|
|non_oper_income|float|Y|加:营业外收入|
|non_oper_exp|float|Y|减:营业外支出|
|nca_disploss|float|Y|其中:减:非流动资产处置净损失|
|total_profit|float|Y|利润总额|
|income_tax|float|Y|所得税费用|
|n_income|float|Y|净利润(含少数股东损益)|
|n_income_attr_p|float|Y|净利润(不含少数股东损益)|
|minority_gain|float|Y|少数股东损益|
|oth_compr_income|float|Y|其他综合收益|
|t_compr_income|float|Y|综合收益总额|
|compr_inc_attr_p|float|Y|归属于母公司(或股东)的综合收益总额|
|compr_inc_attr_m_s|float|Y|归属于少数股东的综合收益总额|
|ebit|float|Y|息税前利润|
|ebitda|float|Y|息税折旧摊销前利润|
|insurance_exp|float|Y|保险业务支出|
|undist_profit|float|Y|年初未分配利润|
|distable_profit|float|Y|可分配利润|
|rd_exp|float|Y|研发费用|
|fin_exp_int_exp|float|Y|财务费用:利息费用|
|fin_exp_int_inc|float|Y|财务费用:利息收入|
|transfer_surplus_rese|float|Y|盈余公积转入|
|transfer_housing_imprest|float|Y|住房周转金转入|
|transfer_oth|float|Y|其他转入|
|adj_lossgain|float|Y|调整以前年度损益|
|withdra_legal_surplus|float|Y|提取法定盈余公积|
|withdra_legal_pubfund|float|Y|提取法定公益金|
|withdra_biz_devfund|float|Y|提取企业发展基金|
|withdra_rese_fund|float|Y|提取储备基金|
|withdra_oth_ersu|float|Y|提取任意盈余公积金|
|workers_welfare|float|Y|职工奖金福利|
|distr_profit_shrhder|float|Y|可供股东分配的利润|
|prfshare_payable_dvd|float|Y|应付优先股股利|
|comshare_payable_dvd|float|Y|应付普通股股利|
|capit_comstock_div|float|Y|转作股本的普通股股利|
|net_after_nr_lp_correct|float|N|扣除非经常性损益后的净利润（更正前）|
|credit_impa_loss|float|N|信用减值损失|
|net_expo_hedging_benefits|float|N|净敞口套期收益|
|oth_impair_loss_assets|float|N|其他资产减值损失|
|total_opcost|float|N|营业总成本（二）|
|amodcost_fin_assets|float|N|以摊余成本计量的金融资产终止确认收益|
|oth_income|float|N|其他收益|
|asset_disp_income|float|N|资产处置收益|
|continued_net_profit|float|N|持续经营净利润|
|end_net_profit|float|N|终止经营净利润|
|update_flag|str|Y|更新标识|

**接口使用说明**

```python

pro = ts.pro_api()

df = pro.income(ts_code='600000.SH', start_date='20180101', end_date='20180730', fields='ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,basic_eps,diluted_eps')
```

获取某一季度全部股票数据

```python

df = pro.income_vip(period='20181231',fields='ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,basic_eps,diluted_eps')
```

**数据样例**

```
     ts_code  ann_date f_ann_date  end_date report_type comp_type  basic_eps  diluted_eps  \
0  600000.SH  20180428   20180428  20180331           1         2       0.46         0.46   
1  600000.SH  20180428   20180428  20180331           1         2       0.46         0.46   
2  600000.SH  20180428   20180428  20171231           1         2       1.84         1.84
    
    
    
```

**主要报表类型说明**

|代码|类型|说明|
|---|---|---|
|1|合并报表|上市公司最新报表（默认）|
|2|单季合并|单一季度的合并报表|
|3|调整单季合并表|调整后的单季合并报表（如果有）|
|4|调整合并报表|本年度公布上年同期的财务报表数据，报告期为上年度|
|5|调整前合并报表|数据发生变更，将原数据进行保留，即调整前的原数据|
|6|母公司报表|该公司母公司的财务报表数据|
|7|母公司单季表|母公司的单季度表|
|8|母公司调整单季表|母公司调整后的单季表|
|9|母公司调整表|该公司母公司的本年度公布上年同期的财务报表数据|
|10|母公司调整前报表|母公司调整之前的原始财务报表数据|
|11|母公司调整前合并报表|母公司调整之前合并报表原数据|
|12|母公司调整前报表|母公司报表发生变更前保留的原数据|

## 资产负债表

---

接口：balancesheet，可以通过[**数据工具**](https://tushare.pro/webclient/)调试和查看数据。  
描述：获取上市公司资产负债表  
积分：用户需要至少2000积分才可以调取，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)  
  
提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用balancesheet_vip接口（参数一致），需积攒5000积分。  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|Y|股票代码|
|ann_date|str|N|公告日期(YYYYMMDD格式，下同)|
|start_date|str|N|公告开始日期|
|end_date|str|N|公告结束日期|
|period|str|N|报告期(每个季度最后一天的日期，比如20171231表示年报，20170630半年报，20170930三季报)|
|report_type|str|N|报告类型：见下方详细说明|
|comp_type|str|N|公司类型：1一般工商业 2银行 3保险 4证券|

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|TS股票代码|
|ann_date|str|Y|公告日期|
|f_ann_date|str|Y|实际公告日期|
|end_date|str|Y|报告期|
|report_type|str|Y|报表类型|
|comp_type|str|Y|公司类型(1一般工商业2银行3保险4证券)|
|end_type|str|Y|报告期类型|
|total_share|float|Y|期末总股本|
|cap_rese|float|Y|资本公积金|
|undistr_porfit|float|Y|未分配利润|
|surplus_rese|float|Y|盈余公积金|
|special_rese|float|Y|专项储备|
|money_cap|float|Y|货币资金|
|trad_asset|float|Y|交易性金融资产|
|notes_receiv|float|Y|应收票据|
|accounts_receiv|float|Y|应收账款|
|oth_receiv|float|Y|其他应收款|
|prepayment|float|Y|预付款项|
|div_receiv|float|Y|应收股利|
|int_receiv|float|Y|应收利息|
|inventories|float|Y|存货|
|amor_exp|float|Y|待摊费用|
|nca_within_1y|float|Y|一年内到期的非流动资产|
|sett_rsrv|float|Y|结算备付金|
|loanto_oth_bank_fi|float|Y|拆出资金|
|premium_receiv|float|Y|应收保费|
|reinsur_receiv|float|Y|应收分保账款|
|reinsur_res_receiv|float|Y|应收分保合同准备金|
|pur_resale_fa|float|Y|买入返售金融资产|
|oth_cur_assets|float|Y|其他流动资产|
|total_cur_assets|float|Y|流动资产合计|
|fa_avail_for_sale|float|Y|可供出售金融资产|
|htm_invest|float|Y|持有至到期投资|
|lt_eqt_invest|float|Y|长期股权投资|
|invest_real_estate|float|Y|投资性房地产|
|time_deposits|float|Y|定期存款|
|oth_assets|float|Y|其他资产|
|lt_rec|float|Y|长期应收款|
|fix_assets|float|Y|固定资产|
|cip|float|Y|在建工程|
|const_materials|float|Y|工程物资|
|fixed_assets_disp|float|Y|固定资产清理|
|produc_bio_assets|float|Y|生产性生物资产|
|oil_and_gas_assets|float|Y|油气资产|
|intan_assets|float|Y|无形资产|
|r_and_d|float|Y|研发支出|
|goodwill|float|Y|商誉|
|lt_amor_exp|float|Y|长期待摊费用|
|defer_tax_assets|float|Y|递延所得税资产|
|decr_in_disbur|float|Y|发放贷款及垫款|
|oth_nca|float|Y|其他非流动资产|
|total_nca|float|Y|非流动资产合计|
|cash_reser_cb|float|Y|现金及存放中央银行款项|
|depos_in_oth_bfi|float|Y|存放同业和其它金融机构款项|
|prec_metals|float|Y|贵金属|
|deriv_assets|float|Y|衍生金融资产|
|rr_reins_une_prem|float|Y|应收分保未到期责任准备金|
|rr_reins_outstd_cla|float|Y|应收分保未决赔款准备金|
|rr_reins_lins_liab|float|Y|应收分保寿险责任准备金|
|rr_reins_lthins_liab|float|Y|应收分保长期健康险责任准备金|
|refund_depos|float|Y|存出保证金|
|ph_pledge_loans|float|Y|保户质押贷款|
|refund_cap_depos|float|Y|存出资本保证金|
|indep_acct_assets|float|Y|独立账户资产|
|client_depos|float|Y|其中：客户资金存款|
|client_prov|float|Y|其中：客户备付金|
|transac_seat_fee|float|Y|其中:交易席位费|
|invest_as_receiv|float|Y|应收款项类投资|
|total_assets|float|Y|资产总计|
|lt_borr|float|Y|长期借款|
|st_borr|float|Y|短期借款|
|cb_borr|float|Y|向中央银行借款|
|depos_ib_deposits|float|Y|吸收存款及同业存放|
|loan_oth_bank|float|Y|拆入资金|
|trading_fl|float|Y|交易性金融负债|
|notes_payable|float|Y|应付票据|
|acct_payable|float|Y|应付账款|
|adv_receipts|float|Y|预收款项|
|sold_for_repur_fa|float|Y|卖出回购金融资产款|
|comm_payable|float|Y|应付手续费及佣金|
|payroll_payable|float|Y|应付职工薪酬|
|taxes_payable|float|Y|应交税费|
|int_payable|float|Y|应付利息|
|div_payable|float|Y|应付股利|
|oth_payable|float|Y|其他应付款|
|acc_exp|float|Y|预提费用|
|deferred_inc|float|Y|递延收益|
|st_bonds_payable|float|Y|应付短期债券|
|payable_to_reinsurer|float|Y|应付分保账款|
|rsrv_insur_cont|float|Y|保险合同准备金|
|acting_trading_sec|float|Y|代理买卖证券款|
|acting_uw_sec|float|Y|代理承销证券款|
|non_cur_liab_due_1y|float|Y|一年内到期的非流动负债|
|oth_cur_liab|float|Y|其他流动负债|
|total_cur_liab|float|Y|流动负债合计|
|bond_payable|float|Y|应付债券|
|lt_payable|float|Y|长期应付款|
|specific_payables|float|Y|专项应付款|
|estimated_liab|float|Y|预计负债|
|defer_tax_liab|float|Y|递延所得税负债|
|defer_inc_non_cur_liab|float|Y|递延收益-非流动负债|
|oth_ncl|float|Y|其他非流动负债|
|total_ncl|float|Y|非流动负债合计|
|depos_oth_bfi|float|Y|同业和其它金融机构存放款项|
|deriv_liab|float|Y|衍生金融负债|
|depos|float|Y|吸收存款|
|agency_bus_liab|float|Y|代理业务负债|
|oth_liab|float|Y|其他负债|
|prem_receiv_adva|float|Y|预收保费|
|depos_received|float|Y|存入保证金|
|ph_invest|float|Y|保户储金及投资款|
|reser_une_prem|float|Y|未到期责任准备金|
|reser_outstd_claims|float|Y|未决赔款准备金|
|reser_lins_liab|float|Y|寿险责任准备金|
|reser_lthins_liab|float|Y|长期健康险责任准备金|
|indept_acc_liab|float|Y|独立账户负债|
|pledge_borr|float|Y|其中:质押借款|
|indem_payable|float|Y|应付赔付款|
|policy_div_payable|float|Y|应付保单红利|
|total_liab|float|Y|负债合计|
|treasury_share|float|Y|减:库存股|
|ordin_risk_reser|float|Y|一般风险准备|
|forex_differ|float|Y|外币报表折算差额|
|invest_loss_unconf|float|Y|未确认的投资损失|
|minority_int|float|Y|少数股东权益|
|total_hldr_eqy_exc_min_int|float|Y|股东权益合计(不含少数股东权益)|
|total_hldr_eqy_inc_min_int|float|Y|股东权益合计(含少数股东权益)|
|total_liab_hldr_eqy|float|Y|负债及股东权益总计|
|lt_payroll_payable|float|Y|长期应付职工薪酬|
|oth_comp_income|float|Y|其他综合收益|
|oth_eqt_tools|float|Y|其他权益工具|
|oth_eqt_tools_p_shr|float|Y|其他权益工具(优先股)|
|lending_funds|float|Y|融出资金|
|acc_receivable|float|Y|应收款项|
|st_fin_payable|float|Y|应付短期融资款|
|payables|float|Y|应付款项|
|hfs_assets|float|Y|持有待售的资产|
|hfs_sales|float|Y|持有待售的负债|
|cost_fin_assets|float|Y|以摊余成本计量的金融资产|
|fair_value_fin_assets|float|Y|以公允价值计量且其变动计入其他综合收益的金融资产|
|cip_total|float|Y|在建工程(合计)(元)|
|oth_pay_total|float|Y|其他应付款(合计)(元)|
|long_pay_total|float|Y|长期应付款(合计)(元)|
|debt_invest|float|Y|债权投资(元)|
|oth_debt_invest|float|Y|其他债权投资(元)|
|oth_eq_invest|float|N|其他权益工具投资(元)|
|oth_illiq_fin_assets|float|N|其他非流动金融资产(元)|
|oth_eq_ppbond|float|N|其他权益工具:永续债(元)|
|receiv_financing|float|N|应收款项融资|
|use_right_assets|float|N|使用权资产|
|lease_liab|float|N|租赁负债|
|contract_assets|float|Y|合同资产|
|contract_liab|float|Y|合同负债|
|accounts_receiv_bill|float|Y|应收票据及应收账款|
|accounts_pay|float|Y|应付票据及应付账款|
|oth_rcv_total|float|Y|其他应收款(合计)（元）|
|fix_assets_total|float|Y|固定资产(合计)(元)|
|update_flag|str|Y|更新标识|

**接口使用说明**

```python

pro = ts.pro_api()

df = pro.balancesheet(ts_code='600000.SH', start_date='20180101', end_date='20180730', fields='ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,cap_rese')
```

获取某一季度全部股票数据

```
df2 = pro.balancesheet_vip(period='20181231',fields='ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,cap_rese')
```

**数据样例**

```
         ts_code  ann_date f_ann_date  end_date report_type comp_type  \
0  600000.SH  20180830   20180830  20180630           1         2   
1  600000.SH  20180428   20180428  20180331           1         2   

             cap_rese  
0  8.176000e+10  
1  8.176000e+10 
```

**主要报表类型说明**

|代码|类型|说明|
|---|---|---|
|1|合并报表|上市公司最新报表（默认）|
|2|单季合并|单一季度的合并报表|
|3|调整单季合并表|调整后的单季合并报表（如果有）|
|4|调整合并报表|本年度公布上年同期的财务报表数据，报告期为上年度|
|5|调整前合并报表|数据发生变更，将原数据进行保留，即调整前的原数据|
|6|母公司报表|该公司母公司的财务报表数据|
|7|母公司单季表|母公司的单季度表|
|8|母公司调整单季表|母公司调整后的单季表|
|9|母公司调整表|该公司母公司的本年度公布上年同期的财务报表数据|
|10|母公司调整前报表|母公司调整之前的原始财务报表数据|
|11|母公司调整前合并报表|母公司调整之前合并报表原数据|
|12|母公司调整前报表|母公司报表发生变更前保留的原数据|

## 现金流量表

---

接口：cashflow，可以通过[**数据工具**](https://tushare.pro/webclient/)调试和查看数据。  
描述：获取上市公司现金流量表  
积分：用户需要至少2000积分才可以调取，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)  
  
提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用cashflow_vip接口（参数一致），需积攒5000积分。  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|Y|股票代码|
|ann_date|str|N|公告日期（YYYYMMDD格式，下同）|
|f_ann_date|str|N|实际公告日期|
|start_date|str|N|公告开始日期|
|end_date|str|N|公告结束日期|
|period|str|N|报告期(每个季度最后一天的日期，比如20171231表示年报，20170630半年报，20170930三季报)|
|report_type|str|N|报告类型：见下方详细说明|
|comp_type|str|N|公司类型：1一般工商业 2银行 3保险 4证券|
|is_calc|int|N|是否计算报表|

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|TS股票代码|
|ann_date|str|Y|公告日期|
|f_ann_date|str|Y|实际公告日期|
|end_date|str|Y|报告期|
|comp_type|str|Y|公司类型(1一般工商业2银行3保险4证券)|
|report_type|str|Y|报表类型|
|end_type|str|Y|报告期类型|
|net_profit|float|Y|净利润|
|finan_exp|float|Y|财务费用|
|c_fr_sale_sg|float|Y|销售商品、提供劳务收到的现金|
|recp_tax_rends|float|Y|收到的税费返还|
|n_depos_incr_fi|float|Y|客户存款和同业存放款项净增加额|
|n_incr_loans_cb|float|Y|向中央银行借款净增加额|
|n_inc_borr_oth_fi|float|Y|向其他金融机构拆入资金净增加额|
|prem_fr_orig_contr|float|Y|收到原保险合同保费取得的现金|
|n_incr_insured_dep|float|Y|保户储金净增加额|
|n_reinsur_prem|float|Y|收到再保业务现金净额|
|n_incr_disp_tfa|float|Y|处置交易性金融资产净增加额|
|ifc_cash_incr|float|Y|收取利息和手续费净增加额|
|n_incr_disp_faas|float|Y|处置可供出售金融资产净增加额|
|n_incr_loans_oth_bank|float|Y|拆入资金净增加额|
|n_cap_incr_repur|float|Y|回购业务资金净增加额|
|c_fr_oth_operate_a|float|Y|收到其他与经营活动有关的现金|
|c_inf_fr_operate_a|float|Y|经营活动现金流入小计|
|c_paid_goods_s|float|Y|购买商品、接受劳务支付的现金|
|c_paid_to_for_empl|float|Y|支付给职工以及为职工支付的现金|
|c_paid_for_taxes|float|Y|支付的各项税费|
|n_incr_clt_loan_adv|float|Y|客户贷款及垫款净增加额|
|n_incr_dep_cbob|float|Y|存放央行和同业款项净增加额|
|c_pay_claims_orig_inco|float|Y|支付原保险合同赔付款项的现金|
|pay_handling_chrg|float|Y|支付手续费的现金|
|pay_comm_insur_plcy|float|Y|支付保单红利的现金|
|oth_cash_pay_oper_act|float|Y|支付其他与经营活动有关的现金|
|st_cash_out_act|float|Y|经营活动现金流出小计|
|n_cashflow_act|float|Y|经营活动产生的现金流量净额|
|oth_recp_ral_inv_act|float|Y|收到其他与投资活动有关的现金|
|c_disp_withdrwl_invest|float|Y|收回投资收到的现金|
|c_recp_return_invest|float|Y|取得投资收益收到的现金|
|n_recp_disp_fiolta|float|Y|处置固定资产、无形资产和其他长期资产收回的现金净额|
|n_recp_disp_sobu|float|Y|处置子公司及其他营业单位收到的现金净额|
|stot_inflows_inv_act|float|Y|投资活动现金流入小计|
|c_pay_acq_const_fiolta|float|Y|购建固定资产、无形资产和其他长期资产支付的现金|
|c_paid_invest|float|Y|投资支付的现金|
|n_disp_subs_oth_biz|float|Y|取得子公司及其他营业单位支付的现金净额|
|oth_pay_ral_inv_act|float|Y|支付其他与投资活动有关的现金|
|n_incr_pledge_loan|float|Y|质押贷款净增加额|
|stot_out_inv_act|float|Y|投资活动现金流出小计|
|n_cashflow_inv_act|float|Y|投资活动产生的现金流量净额|
|c_recp_borrow|float|Y|取得借款收到的现金|
|proc_issue_bonds|float|Y|发行债券收到的现金|
|oth_cash_recp_ral_fnc_act|float|Y|收到其他与筹资活动有关的现金|
|stot_cash_in_fnc_act|float|Y|筹资活动现金流入小计|
|free_cashflow|float|Y|企业自由现金流量|
|c_prepay_amt_borr|float|Y|偿还债务支付的现金|
|c_pay_dist_dpcp_int_exp|float|Y|分配股利、利润或偿付利息支付的现金|
|incl_dvd_profit_paid_sc_ms|float|Y|其中:子公司支付给少数股东的股利、利润|
|oth_cashpay_ral_fnc_act|float|Y|支付其他与筹资活动有关的现金|
|stot_cashout_fnc_act|float|Y|筹资活动现金流出小计|
|n_cash_flows_fnc_act|float|Y|筹资活动产生的现金流量净额|
|eff_fx_flu_cash|float|Y|汇率变动对现金的影响|
|n_incr_cash_cash_equ|float|Y|现金及现金等价物净增加额|
|c_cash_equ_beg_period|float|Y|期初现金及现金等价物余额|
|c_cash_equ_end_period|float|Y|期末现金及现金等价物余额|
|c_recp_cap_contrib|float|Y|吸收投资收到的现金|
|incl_cash_rec_saims|float|Y|其中:子公司吸收少数股东投资收到的现金|
|uncon_invest_loss|float|Y|未确认投资损失|
|prov_depr_assets|float|Y|加:资产减值准备|
|depr_fa_coga_dpba|float|Y|固定资产折旧、油气资产折耗、生产性生物资产折旧|
|amort_intang_assets|float|Y|无形资产摊销|
|lt_amort_deferred_exp|float|Y|长期待摊费用摊销|
|decr_deferred_exp|float|Y|待摊费用减少|
|incr_acc_exp|float|Y|预提费用增加|
|loss_disp_fiolta|float|Y|处置固定、无形资产和其他长期资产的损失|
|loss_scr_fa|float|Y|固定资产报废损失|
|loss_fv_chg|float|Y|公允价值变动损失|
|invest_loss|float|Y|投资损失|
|decr_def_inc_tax_assets|float|Y|递延所得税资产减少|
|incr_def_inc_tax_liab|float|Y|递延所得税负债增加|
|decr_inventories|float|Y|存货的减少|
|decr_oper_payable|float|Y|经营性应收项目的减少|
|incr_oper_payable|float|Y|经营性应付项目的增加|
|others|float|Y|其他|
|im_net_cashflow_oper_act|float|Y|经营活动产生的现金流量净额(间接法)|
|conv_debt_into_cap|float|Y|债务转为资本|
|conv_copbonds_due_within_1y|float|Y|一年内到期的可转换公司债券|
|fa_fnc_leases|float|Y|融资租入固定资产|
|im_n_incr_cash_equ|float|Y|现金及现金等价物净增加额(间接法)|
|net_dism_capital_add|float|Y|拆出资金净增加额|
|net_cash_rece_sec|float|Y|代理买卖证券收到的现金净额(元)|
|credit_impa_loss|float|Y|信用减值损失|
|use_right_asset_dep|float|Y|使用权资产折旧|
|oth_loss_asset|float|Y|其他资产减值损失|
|end_bal_cash|float|Y|现金的期末余额|
|beg_bal_cash|float|Y|减:现金的期初余额|
|end_bal_cash_equ|float|Y|加:现金等价物的期末余额|
|beg_bal_cash_equ|float|Y|减:现金等价物的期初余额|
|update_flag|str|Y|更新标志(1最新）|

**输出参数**

**接口使用说明**

```python

pro = ts.pro_api()

df = pro.cashflow(ts_code='600000.SH', start_date='20180101', end_date='20180730')
```

获取某一季度全部股票数据

```
df2 = pro.cashflow_vip(period='20181231',fields='')
```

**数据样例**

```
     ts_code  ann_date f_ann_date  end_date comp_type report_type    net_profit finan_exp  \
0  600000.SH  20180428   20180428  20180331         2           1           NaN      None   
1  600000.SH  20180428   20180428  20171231         2           1  5.500200e+10      None   
2  600000.SH  20180428   20180428  20171231         2           1  5.500200e+10      None
    
    
```

**主要报表类型说明**

|代码|类型|说明|
|---|---|---|
|1|合并报表|上市公司最新报表（默认）|
|2|单季合并|单一季度的合并报表|
|3|调整单季合并表|调整后的单季合并报表（如果有）|
|4|调整合并报表|本年度公布上年同期的财务报表数据，报告期为上年度|
|5|调整前合并报表|数据发生变更，将原数据进行保留，即调整前的原数据|
|6|母公司报表|该公司母公司的财务报表数据|
|7|母公司单季表|母公司的单季度表|
|8|母公司调整单季表|母公司调整后的单季表|
|9|母公司调整表|该公司母公司的本年度公布上年同期的财务报表数据|
|10|母公司调整前报表|母公司调整之前的原始财务报表数据|
|11|目公司调整前合并报表|母公司调整之前合并报表原数据|
|12|母公司调整前报表|母公司报表发生变更前保留的原数据|
## 业绩预告

---

接口：forecast，可以通过[**数据工具**](https://tushare.pro/webclient/)调试和查看数据。  
描述：获取业绩预告数据  
权限：用户需要至少2000积分才可以调取，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)  
  
提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用forecast_vip接口（参数一致），需积攒5000积分。  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|股票代码(二选一)|
|ann_date|str|N|公告日期 (二选一)|
|start_date|str|N|公告开始日期|
|end_date|str|N|公告结束日期|
|period|str|N|报告期(每个季度最后一天的日期，比如20171231表示年报，20170630半年报，20170930三季报)|
|type|str|N|预告类型(预增/预减/扭亏/首亏/续亏/续盈/略增/略减)|

**输出参数**

|名称|类型|描述|
|---|---|---|
|ts_code|str|TS股票代码|
|ann_date|str|公告日期|
|end_date|str|报告期|
|type|str|业绩预告类型(预增/预减/扭亏/首亏/续亏/续盈/略增/略减)|
|p_change_min|float|预告净利润变动幅度下限（%）|
|p_change_max|float|预告净利润变动幅度上限（%）|
|net_profit_min|float|预告净利润下限（万元）|
|net_profit_max|float|预告净利润上限（万元）|
|last_parent_net|float|上年同期归属母公司净利润|
|first_ann_date|str|首次公告日|
|summary|str|业绩预告摘要|
|change_reason|str|业绩变动原因|

**接口用法**

```python

pro = ts.pro_api()

pro.forecast(ann_date='20190131', fields='ts_code,ann_date,end_date,type,p_change_min,p_change_max,net_profit_min')
```

获取某一季度全部股票数据

```python

df = pro.forecast_vip(period='20181231',fields='ts_code,ann_date,end_date,type,p_change_min,p_change_max,net_profit_min')
```

**数据样例**

```
       ts_code  ann_date  end_date type  p_change_min  p_change_max  \
0    000005.SZ  20190131  20181231   预增      618.5600      945.1800   
1    000825.SZ  20190131  20181231   略增        3.8500       12.5100   
2    000566.SZ  20190131  20181231   预增       50.0000      100.0000   
3    000932.SZ  20190131  20181231   预增       60.8864       68.1664   
4    000557.SZ  20190131  20181231   预增       66.6800       66.6800   
5    600127.SH  20190131  20181231   首亏     -601.5517     -510.3604   
6    600159.SH  20190131  20181231   预增      315.0000      315.0000   
7    600963.SH  20190131  20181231   略增        2.3800       11.5800   
8    002336.SZ  20190131  20181231   续亏       33.1367       47.9952   
9    601608.SH  20190131  20181231   预增      228.5900      274.5700   
10   600531.SH  20190131  20181231   预减      -61.8800      -54.3200   
11   300200.SZ  20190131  20181231   预增       82.4000      112.4000   
12   300441.SZ  20190131  20181231   略减      -20.5100       -0.6400   
13   300157.SZ  20190131  20181231   扭亏      107.3969      108.5176   
14   300052.SZ  20190131  20181231   略减      -30.0000        0.0000   
15   002328.SZ  20190131  20181231   略增        0.0000       20.0000   
16   300420.SZ  20190131  20181231   预增       61.1500       90.8000   
17   300109.SZ  20190131  20181231   续盈      -13.8100        7.7300   
18   300479.SZ  20190131  20181231   略减      -35.8400       -6.6700   
19   000402.SZ  20190131  20181231   略增        1.0000       10.0000   
20   002626.SZ  20190131  20181231   略增       37.1200       47.6600
```

## 业绩快报

---

接口：express  
描述：获取上市公司业绩快报  
权限：用户需要至少2000积分才可以调取，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)  
  
提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用express_vip接口（参数一致），需积攒5000积分。  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|Y|股票代码|
|ann_date|str|N|公告日期|
|start_date|str|N|公告开始日期|
|end_date|str|N|公告结束日期|
|period|str|N|报告期(每个季度最后一天的日期,比如20171231表示年报，20170630半年报，20170930三季报)|

**输出参数**

|名称|类型|描述|
|---|---|---|
|ts_code|str|TS股票代码|
|ann_date|str|公告日期|
|end_date|str|报告期|
|revenue|float|营业收入(元)|
|operate_profit|float|营业利润(元)|
|total_profit|float|利润总额(元)|
|n_income|float|净利润(元)|
|total_assets|float|总资产(元)|
|total_hldr_eqy_exc_min_int|float|股东权益合计(不含少数股东权益)(元)|
|diluted_eps|float|每股收益(摊薄)(元)|
|diluted_roe|float|净资产收益率(摊薄)(%)|
|yoy_net_profit|float|去年同期修正后净利润|
|bps|float|每股净资产|
|yoy_sales|float|同比增长率:营业收入|
|yoy_op|float|同比增长率:营业利润|
|yoy_tp|float|同比增长率:利润总额|
|yoy_dedu_np|float|同比增长率:归属母公司股东的净利润|
|yoy_eps|float|同比增长率:基本每股收益|
|yoy_roe|float|同比增减:加权平均净资产收益率|
|growth_assets|float|比年初增长率:总资产|
|yoy_equity|float|比年初增长率:归属母公司的股东权益|
|growth_bps|float|比年初增长率:归属于母公司股东的每股净资产|
|or_last_year|float|去年同期营业收入|
|op_last_year|float|去年同期营业利润|
|tp_last_year|float|去年同期利润总额|
|np_last_year|float|去年同期净利润|
|eps_last_year|float|去年同期每股收益|
|open_net_assets|float|期初净资产|
|open_bps|float|期初每股净资产|
|perf_summary|str|业绩简要说明|
|is_audit|int|是否审计： 1是 0否|
|remark|str|备注|

**接口用法**

```python

pro = ts.pro_api()

pro.express(ts_code='600000.SH', start_date='20180101', end_date='20180701', fields='ts_code,ann_date,end_date,revenue,operate_profit,total_profit,n_income,total_assets')
```

获取某一季度全部股票数据

```python

df = pro.express_vip(period='20181231',fields='ts_code,ann_date,end_date,revenue,operate_profit,total_profit,n_income,total_assets')
```

**数据样例**

```
     ts_code  ann_date  end_date       revenue  operate_profit  total_profit      n_income  total_assets  \
0  603535.SH  20180411  20180331  2.064659e+08    3.345047e+07  3.340047e+07  2.672643e+07  1.682111e+09   
1  603535.SH  20180208  20171231  1.034262e+09    1.323373e+08  1.440493e+08  1.188325e+08  1.710466e+09   
2  603535.SH  20171016  20170930  7.064117e+08    9.509520e+07  9.931530e+07  8.202480e+07  1.672986e+09
```

## 分红送股

---

接口：dividend  
描述：分红送股数据  
权限：用户需要至少2000积分才可以调取，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|TS代码|
|ann_date|str|N|公告日|
|record_date|str|N|股权登记日期|
|ex_date|str|N|除权除息日|
|imp_ann_date|str|N|实施公告日|

  

以上参数至少有一个不能为空

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|TS代码|
|end_date|str|Y|分红年度|
|ann_date|str|Y|预案公告日|
|div_proc|str|Y|实施进度|
|stk_div|float|Y|每股送转|
|stk_bo_rate|float|Y|每股送股比例|
|stk_co_rate|float|Y|每股转增比例|
|cash_div|float|Y|每股分红（税后）|
|cash_div_tax|float|Y|每股分红（税前）|
|record_date|str|Y|股权登记日|
|ex_date|str|Y|除权除息日|
|pay_date|str|Y|派息日|
|div_listdate|str|Y|红股上市日|
|imp_ann_date|str|Y|实施公告日|
|base_date|str|N|基准日|
|base_share|float|N|基准股本（万）|

**接口示例**

```python

pro = ts.pro_api()

df = pro.dividend(ts_code='600848.SH', fields='ts_code,div_proc,stk_div,record_date,ex_date')
```

**数据样例**

```python

             ts_code div_proc  stk_div record_date   ex_date
    0  600848.SH       实施     0.10    19950606  19950607
    1  600848.SH       实施     0.10    19970707  19970708
    2  600848.SH       实施     0.15    19960701  19960702
    3  600848.SH       实施     0.10    19980706  19980707
    4  600848.SH       预案     0.00        None      None
    5  600848.SH       实施     0.00    20180522  20180523
    
```

## 财务指标数据

---

接口：fina_indicator，可以通过[**数据工具**](https://tushare.pro/webclient/)调试和查看数据。  
描述：获取上市公司财务指标数据，为避免服务器压力，现阶段每次请求最多返回100条记录，可通过设置日期多次请求获取更多数据。  
权限：用户需要至少2000积分才可以调取，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)  
  
提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用fina_indicator_vip接口（参数一致），需积攒5000积分。  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|Y|TS股票代码,e.g. 600001.SH/000001.SZ|
|ann_date|str|N|公告日期|
|start_date|str|N|报告期开始日期|
|end_date|str|N|报告期结束日期|
|period|str|N|报告期(每个季度最后一天的日期,比如20171231表示年报)|

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|TS代码|
|ann_date|str|Y|公告日期|
|end_date|str|Y|报告期|
|eps|float|Y|基本每股收益|
|dt_eps|float|Y|稀释每股收益|
|total_revenue_ps|float|Y|每股营业总收入|
|revenue_ps|float|Y|每股营业收入|
|capital_rese_ps|float|Y|每股资本公积|
|surplus_rese_ps|float|Y|每股盈余公积|
|undist_profit_ps|float|Y|每股未分配利润|
|extra_item|float|Y|非经常性损益|
|profit_dedt|float|Y|扣除非经常性损益后的净利润（扣非净利润）|
|gross_margin|float|Y|毛利|
|current_ratio|float|Y|流动比率|
|quick_ratio|float|Y|速动比率|
|cash_ratio|float|Y|保守速动比率|
|invturn_days|float|N|存货周转天数|
|arturn_days|float|N|应收账款周转天数|
|inv_turn|float|N|存货周转率|
|ar_turn|float|Y|应收账款周转率|
|ca_turn|float|Y|流动资产周转率|
|fa_turn|float|Y|固定资产周转率|
|assets_turn|float|Y|总资产周转率|
|op_income|float|Y|经营活动净收益|
|valuechange_income|float|N|价值变动净收益|
|interst_income|float|N|利息费用|
|daa|float|N|折旧与摊销|
|ebit|float|Y|息税前利润|
|ebitda|float|Y|息税折旧摊销前利润|
|fcff|float|Y|企业自由现金流量|
|fcfe|float|Y|股权自由现金流量|
|current_exint|float|Y|无息流动负债|
|noncurrent_exint|float|Y|无息非流动负债|
|interestdebt|float|Y|带息债务|
|netdebt|float|Y|净债务|
|tangible_asset|float|Y|有形资产|
|working_capital|float|Y|营运资金|
|networking_capital|float|Y|营运流动资本|
|invest_capital|float|Y|全部投入资本|
|retained_earnings|float|Y|留存收益|
|diluted2_eps|float|Y|期末摊薄每股收益|
|bps|float|Y|每股净资产|
|ocfps|float|Y|每股经营活动产生的现金流量净额|
|retainedps|float|Y|每股留存收益|
|cfps|float|Y|每股现金流量净额|
|ebit_ps|float|Y|每股息税前利润|
|fcff_ps|float|Y|每股企业自由现金流量|
|fcfe_ps|float|Y|每股股东自由现金流量|
|netprofit_margin|float|Y|销售净利率|
|grossprofit_margin|float|Y|销售毛利率|
|cogs_of_sales|float|Y|销售成本率|
|expense_of_sales|float|Y|销售期间费用率|
|profit_to_gr|float|Y|净利润/营业总收入|
|saleexp_to_gr|float|Y|销售费用/营业总收入|
|adminexp_of_gr|float|Y|管理费用/营业总收入|
|finaexp_of_gr|float|Y|财务费用/营业总收入|
|impai_ttm|float|Y|资产减值损失/营业总收入|
|gc_of_gr|float|Y|营业总成本/营业总收入|
|op_of_gr|float|Y|营业利润/营业总收入|
|ebit_of_gr|float|Y|息税前利润/营业总收入|
|roe|float|Y|净资产收益率|
|roe_waa|float|Y|加权平均净资产收益率|
|roe_dt|float|Y|净资产收益率(扣除非经常损益)|
|roa|float|Y|总资产报酬率|
|npta|float|Y|总资产净利润|
|roic|float|Y|投入资本回报率|
|roe_yearly|float|Y|年化净资产收益率|
|roa2_yearly|float|Y|年化总资产报酬率|
|roe_avg|float|N|平均净资产收益率(增发条件)|
|opincome_of_ebt|float|N|经营活动净收益/利润总额|
|investincome_of_ebt|float|N|价值变动净收益/利润总额|
|n_op_profit_of_ebt|float|N|营业外收支净额/利润总额|
|tax_to_ebt|float|N|所得税/利润总额|
|dtprofit_to_profit|float|N|扣除非经常损益后的净利润/净利润|
|salescash_to_or|float|N|销售商品提供劳务收到的现金/营业收入|
|ocf_to_or|float|N|经营活动产生的现金流量净额/营业收入|
|ocf_to_opincome|float|N|经营活动产生的现金流量净额/经营活动净收益|
|capitalized_to_da|float|N|资本支出/折旧和摊销|
|debt_to_assets|float|Y|资产负债率|
|assets_to_eqt|float|Y|权益乘数|
|dp_assets_to_eqt|float|Y|权益乘数(杜邦分析)|
|ca_to_assets|float|Y|流动资产/总资产|
|nca_to_assets|float|Y|非流动资产/总资产|
|tbassets_to_totalassets|float|Y|有形资产/总资产|
|int_to_talcap|float|Y|带息债务/全部投入资本|
|eqt_to_talcapital|float|Y|归属于母公司的股东权益/全部投入资本|
|currentdebt_to_debt|float|Y|流动负债/负债合计|
|longdeb_to_debt|float|Y|非流动负债/负债合计|
|ocf_to_shortdebt|float|Y|经营活动产生的现金流量净额/流动负债|
|debt_to_eqt|float|Y|产权比率|
|eqt_to_debt|float|Y|归属于母公司的股东权益/负债合计|
|eqt_to_interestdebt|float|Y|归属于母公司的股东权益/带息债务|
|tangibleasset_to_debt|float|Y|有形资产/负债合计|
|tangasset_to_intdebt|float|Y|有形资产/带息债务|
|tangibleasset_to_netdebt|float|Y|有形资产/净债务|
|ocf_to_debt|float|Y|经营活动产生的现金流量净额/负债合计|
|ocf_to_interestdebt|float|N|经营活动产生的现金流量净额/带息债务|
|ocf_to_netdebt|float|N|经营活动产生的现金流量净额/净债务|
|ebit_to_interest|float|N|已获利息倍数(EBIT/利息费用)|
|longdebt_to_workingcapital|float|N|长期债务与营运资金比率|
|ebitda_to_debt|float|N|息税折旧摊销前利润/负债合计|
|turn_days|float|Y|营业周期|
|roa_yearly|float|Y|年化总资产净利率|
|roa_dp|float|Y|总资产净利率(杜邦分析)|
|fixed_assets|float|Y|固定资产合计|
|profit_prefin_exp|float|N|扣除财务费用前营业利润|
|non_op_profit|float|N|非营业利润|
|op_to_ebt|float|N|营业利润／利润总额|
|nop_to_ebt|float|N|非营业利润／利润总额|
|ocf_to_profit|float|N|经营活动产生的现金流量净额／营业利润|
|cash_to_liqdebt|float|N|货币资金／流动负债|
|cash_to_liqdebt_withinterest|float|N|货币资金／带息流动负债|
|op_to_liqdebt|float|N|营业利润／流动负债|
|op_to_debt|float|N|营业利润／负债合计|
|roic_yearly|float|N|年化投入资本回报率|
|total_fa_trun|float|N|固定资产合计周转率|
|profit_to_op|float|Y|利润总额／营业收入|
|q_opincome|float|N|经营活动单季度净收益|
|q_investincome|float|N|价值变动单季度净收益|
|q_dtprofit|float|N|扣除非经常损益后的单季度净利润|
|q_eps|float|N|每股收益(单季度)|
|q_netprofit_margin|float|N|销售净利率(单季度)|
|q_gsprofit_margin|float|N|销售毛利率(单季度)|
|q_exp_to_sales|float|N|销售期间费用率(单季度)|
|q_profit_to_gr|float|N|净利润／营业总收入(单季度)|
|q_saleexp_to_gr|float|Y|销售费用／营业总收入 (单季度)|
|q_adminexp_to_gr|float|N|管理费用／营业总收入 (单季度)|
|q_finaexp_to_gr|float|N|财务费用／营业总收入 (单季度)|
|q_impair_to_gr_ttm|float|N|资产减值损失／营业总收入(单季度)|
|q_gc_to_gr|float|Y|营业总成本／营业总收入 (单季度)|
|q_op_to_gr|float|N|营业利润／营业总收入(单季度)|
|q_roe|float|Y|净资产收益率(单季度)|
|q_dt_roe|float|Y|净资产单季度收益率(扣除非经常损益)|
|q_npta|float|Y|总资产净利润(单季度)|
|q_opincome_to_ebt|float|N|经营活动净收益／利润总额(单季度)|
|q_investincome_to_ebt|float|N|价值变动净收益／利润总额(单季度)|
|q_dtprofit_to_profit|float|N|扣除非经常损益后的净利润／净利润(单季度)|
|q_salescash_to_or|float|N|销售商品提供劳务收到的现金／营业收入(单季度)|
|q_ocf_to_sales|float|Y|经营活动产生的现金流量净额／营业收入(单季度)|
|q_ocf_to_or|float|N|经营活动产生的现金流量净额／经营活动净收益(单季度)|
|basic_eps_yoy|float|Y|基本每股收益同比增长率(%)|
|dt_eps_yoy|float|Y|稀释每股收益同比增长率(%)|
|cfps_yoy|float|Y|每股经营活动产生的现金流量净额同比增长率(%)|
|op_yoy|float|Y|营业利润同比增长率(%)|
|ebt_yoy|float|Y|利润总额同比增长率(%)|
|netprofit_yoy|float|Y|归属母公司股东的净利润同比增长率(%)|
|dt_netprofit_yoy|float|Y|归属母公司股东的净利润-扣除非经常损益同比增长率(%)|
|ocf_yoy|float|Y|经营活动产生的现金流量净额同比增长率(%)|
|roe_yoy|float|Y|净资产收益率(摊薄)同比增长率(%)|
|bps_yoy|float|Y|每股净资产相对年初增长率(%)|
|assets_yoy|float|Y|资产总计相对年初增长率(%)|
|eqt_yoy|float|Y|归属母公司的股东权益相对年初增长率(%)|
|tr_yoy|float|Y|营业总收入同比增长率(%)|
|or_yoy|float|Y|营业收入同比增长率(%)|
|q_gr_yoy|float|N|营业总收入同比增长率(%)(单季度)|
|q_gr_qoq|float|N|营业总收入环比增长率(%)(单季度)|
|q_sales_yoy|float|Y|营业收入同比增长率(%)(单季度)|
|q_sales_qoq|float|N|营业收入环比增长率(%)(单季度)|
|q_op_yoy|float|N|营业利润同比增长率(%)(单季度)|
|q_op_qoq|float|Y|营业利润环比增长率(%)(单季度)|
|q_profit_yoy|float|N|净利润同比增长率(%)(单季度)|
|q_profit_qoq|float|N|净利润环比增长率(%)(单季度)|
|q_netprofit_yoy|float|N|归属母公司股东的净利润同比增长率(%)(单季度)|
|q_netprofit_qoq|float|N|归属母公司股东的净利润环比增长率(%)(单季度)|
|equity_yoy|float|Y|净资产同比增长率|
|rd_exp|float|N|研发费用|
|update_flag|str|N|更新标识|

**接口用法**

```python

pro = ts.pro_api()

df = pro.fina_indicator(ts_code='600000.SH')
```

或者

```python

df = pro.query('fina_indicator', ts_code='600000.SH', start_date='20170101', end_date='20180801')
```

**数据样例**

```
ts_code  ann_date  end_date   eps  dt_eps  total_revenue_ps  revenue_ps  \
0  600000.SH  20180830  20180630  0.95    0.95            2.8024      2.8024   
1  600000.SH  20180428  20180331  0.46    0.46            1.3501      1.3501   
2  600000.SH  20180428  20171231  1.84    1.84            5.7447      5.7447   
3  600000.SH  20180428  20171231  1.84    1.84            5.7447      5.7447   
4  600000.SH  20171028  20170930  1.45    1.45            4.2507      4.2507   
5  600000.SH  20171028  20170930  1.45    1.45            4.2507      4.2507   
6  600000.SH  20170830  20170630  0.97    0.97            2.9659      2.9659   
7  600000.SH  20170427  20170331  0.63    0.63            1.9595      1.9595   
8  600000.SH  20170427  20170331  0.63    0.63            1.9595      1.9595  
```

## 财务审计意见

---

接口：fina_audit  
描述：获取上市公司定期财务审计意见数据  
权限：用户需要至少500积分才可以调取，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|Y|股票代码|
|ann_date|str|N|公告日期|
|start_date|str|N|公告开始日期|
|end_date|str|N|公告结束日期|
|period|str|N|报告期(每个季度最后一天的日期,比如20171231表示年报)|

**输出参数**

|名称|类型|描述|
|---|---|---|
|ts_code|str|TS股票代码|
|ann_date|str|公告日期|
|end_date|str|报告期|
|audit_result|str|审计结果|
|audit_fees|float|审计总费用（元）|
|audit_agency|str|会计事务所|
|audit_sign|str|签字会计师|

**接口使用**

```python

pro = ts.pro_api()

df = pro.fina_audit(ts_code='600000.SH', start_date='20100101', end_date='20180808')
```

**数据示例**

```
      ts_code  ann_date  end_date        audit_result  audit_agency                audit_sign
0  600000.SH  20180428  20171231      标准无保留意见  普华永道中天会计师事务所      周章,张武
1  600000.SH  20170401  20161231      标准无保留意见  普华永道中天会计师事务所      周章,张武
2  600000.SH  20160407  20151231      标准无保留意见  普华永道中天会计师事务所      胡亮,张武
3  600000.SH  20150319  20141231      标准无保留意见  普华永道中天会计师事务所      胡亮,张武
4  600000.SH  20140320  20131231      标准无保留意见  普华永道中天会计师事务所      胡亮,周章
5  600000.SH  20130314  20121231      标准无保留意见  普华永道中天会计师事务所      胡亮,周章
6  600000.SH  20120316  20111231      标准无保留意见  普华永道中天会计师事务所      胡亮,周章
7  600000.SH  20110330  20101231      标准无保留意见    安永华明会计师事务所    严盛炜,周明骏
8  600000.SH  20100830  20100630      标准无保留意见    安永华明会计师事务所    严盛炜,周明骏
9  600000.SH  20100407  20091231      标准无保留意见    安永华明会计师事务所    严盛炜,周明骏
```

## 主营业务构成

---

接口：fina_mainbz  
描述：获得上市公司主营业务构成，分地区和产品两种方式  
权限：用户需要至少2000积分才可以调取，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13) ，单次最大提取100行，总量不限制，可循环获取。  
  
提示：当前接口只能按单只股票获取其历史数据，如果需要获取某一季度全部上市公司数据，请使用fina_mainbz_vip接口（参数一致），需积攒5000积分。  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|Y|股票代码|
|period|str|N|报告期(每个季度最后一天的日期,比如20171231表示年报)|
|type|str|N|类型：P按产品 D按地区 I按行业（请输入大写字母P或者D）|
|start_date|str|N|报告期开始日期|
|end_date|str|N|报告期结束日期|

**输出参数**

|名称|类型|描述|
|---|---|---|
|ts_code|str|TS代码|
|end_date|str|报告期|
|bz_item|str|主营业务来源|
|bz_sales|float|主营业务收入(元)|
|bz_profit|float|主营业务利润(元)|
|bz_cost|float|主营业务成本(元)|
|curr_type|str|货币代码|
|update_flag|str|是否更新|

**代码示例**

```python

pro = ts.pro_api()

df = pro.fina_mainbz(ts_code='000627.SZ', type='P')
```

获取某一季度全部股票数据

```python

df = pro.fina_mainbz_vip(period='20181231', type='P' ,fields='ts_code,end_date,bz_item,bz_sales')
```

**数据样例**

```
     ts_code  end_date    bz_item       bz_sales       bz_profit bz_cost curr_type
0  000627.SZ  20171231    其他产品      1.847507e+08      None    None       CNY
1  000627.SZ  20171231    其他主营业务  1.847507e+08      None    None       CNY
2  000627.SZ  20171231    聚丙烯        6.629111e+07      None    None       CNY
3  000627.SZ  20171231    原料药产品    2.685909e+08      None    None       CNY
4  000627.SZ  20171231    保险业务      5.288595e+10      None    None       CNY
```

## 财报披露计划

---

接口：disclosure_date  
描述：获取财报披露计划日期  
限量：单次最大3000，总量不限制  
积分：用户需要至少500积分才可以调取，积分越多权限越大，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|TS股票代码|
|end_date|str|N|财报周期（每个季度最后一天的日期，比如20181231表示2018年年报，20180630表示中报)|
|pre_date|str|N|计划披露日期|
|ann_date|str|N|最新披露公告日|
|actual_date|str|N|实际披露日期|

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|TS代码|
|ann_date|str|Y|最新披露公告日|
|end_date|str|Y|报告期|
|pre_date|str|Y|预计披露日期|
|actual_date|str|Y|实际披露日期|
|modify_date|str|N|披露日期修正记录|

**接口使用**

```python

pro = ts.pro_api()

df = pro.disclosure_date(end_date='20181231')
```

**数据示例**

```
        ts_code  ann_date  end_date  pre_date actual_date modify_date
0     300619.SZ  20181228  20181231  20190122    20190122        None
1     300125.SZ  20181228  20181231  20190129    20190129        None
2     601619.SH  20181227  20181231  20190129    20190129        None
3     000055.SZ  20181228  20181231  20190130    20190130        None
4     002910.SZ  20181228  20181231  20190131        None        None
5     002188.SZ  20181228  20181231  20190131        None        None
6     600738.SH  20190124  20181231  20190131        None        None
7     002107.SZ  20181228  20181231  20190201        None        None
8     300748.SZ  20181228  20181231  20190201        None        None
9     002675.SZ  20181228  20181231  20190201        None        None
10    002167.SZ  20181228  20181231  20190201        None        None
11    002211.SZ  20190125  20181231  20190201        None        None
12    002240.SZ  20181228  20181231  20190201        None        None
13    002245.SZ  20181228  20181231  20190201        None        None
14    002552.SZ  20181228  20181231  20190201        None        None
15    002825.SZ  20181228  20181231  20190201        None        None
```


## A股日线行情

---

接口：daily，可以通过[**数据工具**](https://tushare.pro/webclient/)调试和查看数据  
数据说明：交易日每天15点～16点之间入库。本接口是未复权行情，停牌期间不提供数据  
调取说明：基础积分每分钟内可调取500次，每次6000条数据，一次请求相当于提取一个股票23年历史  
描述：获取股票行情数据，或通过[**通用行情接口**](https://tushare.pro/document/2?doc_id=109)获取数据，包含了前后复权数据

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|股票代码（支持多个股票同时提取，逗号分隔）|
|trade_date|str|N|交易日期（YYYYMMDD）|
|start_date|str|N|开始日期(YYYYMMDD)|
|end_date|str|N|结束日期(YYYYMMDD)|

**注：日期都填YYYYMMDD格式，比如20181010**

**输出参数**

|名称|类型|描述|
|---|---|---|
|ts_code|str|股票代码|
|trade_date|str|交易日期|
|open|float|开盘价|
|high|float|最高价|
|low|float|最低价|
|close|float|收盘价|
|pre_close|float|昨收价【除权价，前复权】|
|change|float|涨跌额|
|pct_chg|float|涨跌幅 【基于除权后的昨收计算的涨跌幅：（今收-除权昨收）/除权昨收 】|
|vol|float|成交量 （手）|
|amount|float|成交额 （千元）|

**接口示例**

```python

pro = ts.pro_api()

df = pro.daily(ts_code='000001.SZ', start_date='20180701', end_date='20180718')

#多个股票
df = pro.daily(ts_code='000001.SZ,600000.SH', start_date='20180701', end_date='20180718')
```

或者

```python

df = pro.query('daily', ts_code='000001.SZ', start_date='20180701', end_date='20180718')
```

也可以通过日期取历史某一天的全部历史

```python

df = pro.daily(trade_date='20180810')
```

**数据样例**

```
 ts_code     trade_date  open  high   low  close  pre_close  change    pct_chg  vol        amount
0  000001.SZ   20180718  8.75  8.85  8.69   8.70       8.72   -0.02       -0.23   525152.77   460697.377
1  000001.SZ   20180717  8.74  8.75  8.66   8.72       8.73   -0.01       -0.11   375356.33   326396.994
2  000001.SZ   20180716  8.85  8.90  8.69   8.73       8.88   -0.15       -1.69   689845.58   603427.713
3  000001.SZ   20180713  8.92  8.94  8.82   8.88       8.88    0.00        0.00   603378.21   535401.175
4  000001.SZ   20180712  8.60  8.97  8.58   8.88       8.64    0.24        2.78  1140492.31  1008658.828
5  000001.SZ   20180711  8.76  8.83  8.68   8.78       8.98   -0.20       -2.23   851296.70   744765.824
6  000001.SZ   20180710  9.02  9.02  8.89   8.98       9.03   -0.05       -0.55   896862.02   803038.965
7  000001.SZ   20180709  8.69  9.03  8.68   9.03       8.66    0.37        4.27  1409954.60  1255007.609
8  000001.SZ   20180706  8.61  8.78  8.45   8.66       8.60    0.06        0.70   988282.69   852071.526
9  000001.SZ   20180705  8.62  8.73  8.55   8.60       8.61   -0.01       -0.12   835768.77   722169.579
```


## A股复权行情

---

**接口名称** ：pro_bar  
**接口说明** ：复权行情通过[通用行情接口](https://tushare.pro/document/2?doc_id=109)实现，利用Tushare Pro提供的[复权因子](https://tushare.pro/document/2?doc_id=28)进行动态计算，因此http方式无法调取。若需要静态复权行情（支持http），请访问[股票技术因子接口](https://tushare.pro/document/2?doc_id=296)。  
**Python SDK版本要求**： >= 1.2.26

  
  

**复权说明**

|类型|算法|参数标识|
|---|---|---|
|不复权|无|空或None|
|前复权|当日收盘价 × 当日复权因子 / 最新复权因子|qfq|
|后复权|当日收盘价 × 当日复权因子|hfq|

  
  
注：目前只支持A股的日线复权。在Tushare数据接口里，不管是旧版的一些接口还是Pro版的行情接口，都是以用户设定的end_date开始往前复权，跟所有行情软件或者财经网站上看到的前复权可能存在差异，因为行情软件都是以最近一个交易日开始往前复权的。比如今天是2018年10月26日，您想查2018年1月5日～2018年9月28日的前复权数据，Tushare是先查找9月28日的复权因子，从28日开始复权，而行情软件是从10月26日这天开始复权的。同时，Tushare的复权采用“分红再投”模式计算。  
  

**接口参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|Y|证券代码|
|start_date|str|N|开始日期 (格式：YYYYMMDD)|
|end_date|str|N|结束日期 (格式：YYYYMMDD)|
|asset|str|Y|资产类别：E股票 I沪深指数 C数字货币 FT期货 FD基金 O期权，默认E|
|adj|str|N|复权类型(只针对股票)：None未复权 qfq前复权 hfq后复权 , 默认None|
|freq|str|Y|数据频度 ：1MIN表示1分钟（1/5/15/30/60分钟） D日线 ，默认D|
|ma|list|N|均线，支持任意周期的均价和均量，输入任意合理int数值|

  
  

**接口用例**

日线复权

```python

#取000001的前复权行情
df = ts.pro_bar(ts_code='000001.SZ', adj='qfq', start_date='20180101', end_date='20181011')

#取000001的后复权行情
df = ts.pro_bar(ts_code='000001.SZ', adj='hfq', start_date='20180101', end_date='20181011')
```

  

周线复权

```python

#取000001的周线前复权行情
df = ts.pro_bar( ts_code='000001.SZ', freq='W', adj='qfq', start_date='20180101', end_date='20181011')

#取000001的周线后复权行情
df = ts.pro_bar(ts_code='000001.SZ', freq='W', adj='hfq', start_date='20180101', end_date='20181011')
```

  

月线复权

```python

#取000001的月线前复权行情
df = ts.pro_bar(ts_code='000001.SZ', freq='M', adj='qfq', start_date='20180101', end_date='20181011')

#取000001的月线后复权行情
df = ts.pro_bar(ts_code='000001.SZ', freq='M', adj='hfq', start_date='20180101', end_date='20181011')
```

## 每日指标

---

接口：daily_basic，可以通过[**数据工具**](https://tushare.pro/webclient/)调试和查看数据。  
更新时间：交易日每日15点～17点之间  
描述：获取全部股票每日重要的基本面指标，可用于选股分析、报表展示等。单次请求最大返回6000条数据，可按日线循环提取全部历史。  
积分：至少2000积分才可以调取，5000积分无总量限制，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|Y|股票代码（二选一）|
|trade_date|str|N|交易日期 （二选一）|
|start_date|str|N|开始日期(YYYYMMDD)|
|end_date|str|N|结束日期(YYYYMMDD)|

**注：日期都填YYYYMMDD格式，比如20181010**

**输出参数**

|名称|类型|描述|
|---|---|---|
|ts_code|str|TS股票代码|
|trade_date|str|交易日期|
|close|float|当日收盘价|
|turnover_rate|float|换手率（%）|
|turnover_rate_f|float|换手率（自由流通股）|
|volume_ratio|float|量比|
|pe|float|市盈率（总市值/净利润， 亏损的PE为空）|
|pe_ttm|float|市盈率（TTM，亏损的PE为空）|
|pb|float|市净率（总市值/净资产）|
|ps|float|市销率|
|ps_ttm|float|市销率（TTM）|
|dv_ratio|float|股息率 （%）|
|dv_ttm|float|股息率（TTM）（%）|
|total_share|float|总股本 （万股）|
|float_share|float|流通股本 （万股）|
|free_share|float|自由流通股本 （万）|
|total_mv|float|总市值 （万元）|
|circ_mv|float|流通市值（万元）|

**接口用法**

```python

pro = ts.pro_api()

df = pro.daily_basic(ts_code='', trade_date='20180726', fields='ts_code,trade_date,turnover_rate,volume_ratio,pe,pb')
```

或者

```python

df = pro.query('daily_basic', ts_code='', trade_date='20180726',fields='ts_code,trade_date,turnover_rate,volume_ratio,pe,pb')
```

**数据样例**

```
    ts_code     trade_date  turnover_rate  volume_ratio        pe       pb
0     600230.SH   20180726         2.4584          0.72    8.6928   3.7203
1     600237.SH   20180726         1.4737          0.88  166.4001   1.8868
2     002465.SZ   20180726         0.7489          0.72   71.8943   2.6391
3     300732.SZ   20180726         6.7083          0.77   21.8101   3.2513
4     600007.SH   20180726         0.0381          0.61   23.7696   2.3774
5     300068.SZ   20180726         1.4583          0.52   27.8166   1.7549
6     300552.SZ   20180726         2.0728          0.95   56.8004   2.9279
7     601369.SH   20180726         0.2088          0.95   44.1163   1.8001
8     002518.SZ   20180726         0.5814          0.76   15.1004   2.5626
9     002913.SZ   20180726        12.1096          1.03   33.1279   2.9217
10    601818.SH   20180726         0.1893          0.86    6.3064   0.7209
11    600926.SH   20180726         0.6065          0.46    9.1772   0.9808
12    002166.SZ   20180726         0.7582          0.82   16.9868   3.3452
13    600841.SH   20180726         0.3754          1.02   66.2647   2.2302
14    300634.SZ   20180726        23.1127          1.26  120.3053  14.3168
15    300126.SZ   20180726         1.2304          1.11  348.4306   1.5171
16    300718.SZ   20180726        17.6612          0.92   32.0239   3.8661
17    000708.SZ   20180726         0.5575          0.70   10.3674   1.0276
18    002626.SZ   20180726         0.6187          0.83   22.7580   4.2446
19    600816.SH   20180726         0.6745          0.65   11.0778   3.2214
```

## 通用行情接口

---

**接口名称**：pro_bar，本接口是集成开发接口，部分指标是现用现算  
**更新时间**：股票和指数通常在15点～17点之间，数字货币实时更新，具体请参考各接口文档明细。  
**描述**：目前整合了股票（未复权、前复权、后复权）、指数、数字货币、ETF基金、期货、期权的行情数据，未来还将整合包括外汇在内的所有交易行情数据，同时提供分钟数据。不同数据对应不同的积分要求，具体请参阅每类数据的文档说明。  
**其它**：由于本接口是集成接口，在SDK层做了一些逻辑处理，目前暂时没法用http的方式调取通用行情接口。用户可以访问Tushare的Github，查看源代码完成类似功能。

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|Y|证券代码，不支持多值输入，多值输入获取结果会有重复记录|
|start_date|str|N|开始日期 (日线格式：YYYYMMDD，提取分钟数据请用2019-09-01 09:00:00这种格式)|
|end_date|str|N|结束日期 (日线格式：YYYYMMDD)|
|asset|str|Y|资产类别：E股票 I沪深指数 C数字货币 FT期货 FD基金 O期权 CB可转债（v1.2.39），默认E|
|adj|str|N|复权类型(只针对股票)：None未复权 qfq前复权 hfq后复权 , 默认None，**目前只支持日线复权**，同时复权机制是根据设定的end_date参数动态复权，采用分红再投模式，具体请参考[常见问题列表](https://tushare.pro/document/1?doc_id=122)里的说明。|
|freq|str|Y|数据频度 ：支持分钟(min)/日(D)/周(W)/月(M)K线，其中1min表示1分钟（类推1/5/15/30/60分钟） ，默认D。对于分钟数据有600积分用户可以试用（请求2次），正式权限可以参考[权限列表说明](https://tushare.pro/document/1?doc_id=290) ，使用方法请参考[股票分钟使用方法](https://tushare.pro/document/1?doc_id=234)。|
|ma|list|N|均线，支持任意合理int数值。注：均线是动态计算，要设置一定时间范围才能获得相应的均线，比如5日均线，开始和结束日期参数跨度必须要超过5日。目前只支持单一个股票提取均线，即需要输入ts_code参数。e.g: ma_5表示5日均价，ma_v_5表示5日均量|
|factors|list|N|股票因子（asset='E'有效）支持 tor换手率 vr量比|
|adjfactor|str|N|复权因子，在复权数据时，如果此参数为True，返回的数据中则带复权因子，默认为False。 该功能从1.2.33版本开始生效|

  

**输出指标**

具体输出的数据指标可参考各行情具体指标：

股票Daily：[https://tushare.pro/document/2?doc_id=27](https://tushare.pro/document/2?doc_id=27)

基金Daily：[https://tushare.pro/document/2?doc_id=127](https://tushare.pro/document/2?doc_id=127)

期货Daily：[https://tushare.pro/document/2?doc_id=138](https://tushare.pro/document/2?doc_id=138)

期权Daily：[https://tushare.pro/document/2?doc_id=159](https://tushare.pro/document/2?doc_id=159)

指数Daily：[https://tushare.pro/document/2?doc_id=95](https://tushare.pro/document/2?doc_id=95)

**接口用例**

```python

#取000001的前复权行情
df = ts.pro_bar(ts_code='000001.SZ', adj='qfq', start_date='20180101', end_date='20181011')

              ts_code trade_date     open     high      low    close  \
trade_date
20181011    000001.SZ   20181011  1085.71  1097.59  1047.90  1065.19
20181010    000001.SZ   20181010  1138.65  1151.61  1121.36  1128.92
20181009    000001.SZ   20181009  1130.00  1155.93  1122.44  1140.81
20181008    000001.SZ   20181008  1155.93  1165.65  1128.92  1128.92
20180928    000001.SZ   20180928  1164.57  1217.51  1164.57  1193.74
```

  
  

```python

#取上证指数行情数据

df = ts.pro_bar(ts_code='000001.SH', asset='I', start_date='20180101', end_date='20181011')

In [10]: df.head()
Out[10]:
     ts_code trade_date      close       open       high        low  \
0  000001.SH   20181011  2583.4575  2643.0740  2661.2859  2560.3164
1  000001.SH   20181010  2725.8367  2723.7242  2743.5480  2703.0626
2  000001.SH   20181009  2721.0130  2713.7319  2734.3142  2711.1971
3  000001.SH   20181008  2716.5104  2768.2075  2771.9384  2710.1781
4  000001.SH   20180928  2821.3501  2794.2644  2821.7553  2791.8363

   pre_close    change  pct_chg          vol       amount
0  2725.8367 -142.3792     -5.2233  197150702.0  170057762.5
1  2721.0130    4.8237      0.1773  113485736.0  111312455.3
2  2716.5104    4.5026      0.1657  116771899.0  110292457.8
3  2821.3501 -104.8397     -3.7159  149501388.0  141531551.8
4  2791.7748   29.5753      1.0594  134290456.0  125369989.4
```

  
  

```python

#均线

df = ts.pro_bar(ts_code='000001.SZ', start_date='20180101', end_date='20181011', ma=[5, 20, 50])
```

注：Tushare pro_bar接口的均价和均量数据是动态计算，想要获取某个时间段的均线，必须要设置start_date日期大于最大均线的日期数，然后自行截取想要日期段。例如，想要获取20190801开始的3日均线，必须设置start_date='20190729'，然后剔除20190801之前的日期记录。

  
  

```python

#换手率tor，量比vr

df = ts.pro_bar(ts_code='000001.SZ', start_date='20180101', end_date='20181011', factors=['tor', 'vr'])
```

  
  

**说明**

对于pro_api参数，如果在一开始就通过 ts.set_token('xxxx') 设置过token的情况，这个参数就不是必需的。

例如：

```python

df = ts.pro_bar(ts_code='000001.SH', asset='I', start_date='20180101', end_date='20181011')
```

## 每日停复牌信息

---

接口：suspend_d  
更新时间：不定期  
描述：按日期方式获取股票每日停复牌信息

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|股票代码(可输入多值)|
|trade_date|str|N|交易日日期|
|start_date|str|N|停复牌查询开始日期|
|end_date|str|N|停复牌查询结束日期|
|suspend_type|str|N|停复牌类型：S-停牌,R-复牌|

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|TS代码|
|trade_date|str|Y|停复牌日期|
|suspend_timing|str|Y|日内停牌时间段|
|suspend_type|str|Y|停复牌类型：S-停牌，R-复牌|

**接口用法**

```python

pro = ts.pro_api()

#提取2020-03-12的停牌股票
df = pro.suspend_d(suspend_type='S', trade_date='20200312')
```

**数据样例**

```
        ts_code suspend_type trade_date suspend_timing
0   000029.SZ            S     20200312           None
1   000502.SZ            S     20200312           None
2   000939.SZ            S     20200312           None
3   000977.SZ            S     20200312           None
4   000995.SZ            S     20200312           None
5   002260.SZ            S     20200312           None
6   002450.SZ            S     20200312           None
7   002604.SZ            S     20200312           None
8   300028.SZ            S     20200312           None
9   300104.SZ            S     20200312           None
10  300216.SZ            S     20200312           None
11  300592.SZ            S     20200312           None
12  300819.SZ            S     20200312    09:30-10:00
13  300821.SZ            S     20200312    09:30-10:00
14  600074.SH            S     20200312           None
15  600145.SH            S     20200312           None
16  600228.SH            S     20200312           None
17  600310.SH            S     20200312           None
18  600610.SH            S     20200312           None
19  600745.SH            S     20200312           None
20  600766.SH            S     20200312           None
21  600891.SH            S     20200312           None
22  601127.SH            S     20200312           None
23  601162.SH            S     20200312           None
24  603002.SH            S     20200312           None
25  603399.SH            S     20200312           None
```

## 备用行情

---

接口：bak_daily  
描述：获取备用行情，包括特定的行情指标(数据从2017年中左右开始，早期有几天数据缺失，近期正常)  
限量：单次最大7000行数据，可以根据日期参数循环获取，正式权限需要5000积分。

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|股票代码|
|trade_date|str|N|交易日期|
|start_date|str|N|开始日期|
|end_date|str|N|结束日期|
|offset|str|N|开始行数|
|limit|str|N|最大行数|

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|股票代码|
|trade_date|str|Y|交易日期|
|name|str|Y|股票名称|
|pct_change|float|Y|涨跌幅|
|close|float|Y|收盘价|
|change|float|Y|涨跌额|
|open|float|Y|开盘价|
|high|float|Y|最高价|
|low|float|Y|最低价|
|pre_close|float|Y|昨收价|
|vol_ratio|float|Y|量比|
|turn_over|float|Y|换手率|
|swing|float|Y|振幅|
|vol|float|Y|成交量|
|amount|float|Y|成交额|
|selling|float|Y|内盘（主动卖，手）|
|buying|float|Y|外盘（主动买， 手）|
|total_share|float|Y|总股本(亿)|
|float_share|float|Y|流通股本(亿)|
|pe|float|Y|市盈(动)|
|industry|str|Y|所属行业|
|area|str|Y|所属地域|
|float_mv|float|Y|流通市值|
|total_mv|float|Y|总市值|
|avg_price|float|Y|平均价|
|strength|float|Y|强弱度(%)|
|activity|float|Y|活跃度(%)|
|avg_turnover|float|Y|笔换手|
|attack|float|Y|攻击波(%)|
|interval_3|float|Y|近3月涨幅|
|interval_6|float|Y|近6月涨幅|

**接口示例**

```python

pro = ts.pro_api()

df = pro.bak_daily(trade_date='20211012', fields='trade_date,ts_code,name,close,open')
```

**数据样例**

```
    ts_code     trade_date      name  close   open
0     300605.SZ   20211012  恒锋信息  14.86  12.65
1     301017.SZ   20211012  漱玉平民  25.21  20.82
2     300755.SZ   20211012  华致酒行  40.45  37.01
3     300255.SZ   20211012  常山药业   8.39   7.26
4     688378.SH   20211012   奥来德  68.62  67.00
...         ...        ...   ...    ...    ...
4529  688257.SH   20211012  新锐股份   0.00   0.00
4530  688255.SH   20211012   凯尔达   0.00   0.00
4531  688211.SH   20211012  中科微至   0.00   0.00
4532  605567.SH   20211012  春雪食品   0.00   0.00
4533  605566.SH   20211012  福莱蒽特   0.00   0.00
```

# 参考数据
## 前十大流通股东

---

接口：top10_floatholders  
描述：获取上市公司前十大流通股东数据  
积分：需2000积分以上才可以调取本接口，5000积分以上频次会更高

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|Y|TS代码|
|period|str|N|报告期（YYYYMMDD格式，一般为每个季度最后一天）|
|ann_date|str|N|公告日期|
|start_date|str|N|报告期开始日期|
|end_date|str|N|报告期结束日期|

**输出参数**

|名称|类型|描述|
|---|---|---|
|ts_code|str|TS股票代码|
|ann_date|str|公告日期|
|end_date|str|报告期|
|holder_name|str|股东名称|
|hold_amount|float|持有数量（股）|
|hold_ratio|float|占总股本比例(%)|
|hold_float_ratio|float|占流通股本比例(%)|
|hold_change|float|持股变动|
|holder_type|str|股东类型|

**接口用法**

```python

pro = ts.pro_api()

df = pro.top10_floatholders(ts_code='600000.SH', start_date='20170101', end_date='20171231')
```

或者

```python

df = pro.query('top10_floatholders', ts_code='600000.SH', start_date='20170101', end_date='20171231')
```

**数据样例**

```
     ts_code  ann_date  end_date                        holder_name   hold_amount
0  600000.SH  20180428  20171231  富德生命人寿保险股份有限公司-资本金  1.763232e+09
1  600000.SH  20180428  20171231          上海国际集团有限公司  5.489319e+09
2  600000.SH  20180428  20171231   富德生命人寿保险股份有限公司-传统  2.779437e+09
3  600000.SH  20180428  20171231        中国证券金融股份有限公司  1.216979e+09
4  600000.SH  20180428  20171231       梧桐树投资平台有限责任公司  8.861313e+08
5  600000.SH  20180428  20171231       上海上国投资产管理有限公司  1.395571e+09
6  600000.SH  20180428  20171231  富德生命人寿保险股份有限公司-万能H  1.270429e+09
7  600000.SH  20180428  20171231        上海国鑫投资发展有限公司  5.392559e+08
8  600000.SH  20180428  20171231      中央汇金资产管理有限责任公司  3.985214e+08
9  600000.SH  20180428  20171231      中国移动通信集团广东有限公司  5.334893e+09
```

## 前十大股东

---

接口：top10_holders  
描述：获取上市公司前十大股东数据，包括持有数量和比例等信息  
积分：需2000积分以上才可以调取本接口，5000积分以上频次会更高

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|Y|TS代码|
|period|str|N|报告期（YYYYMMDD格式，一般为每个季度最后一天）|
|ann_date|str|N|公告日期|
|start_date|str|N|报告期开始日期|
|end_date|str|N|报告期结束日期|

**输出参数**

|名称|类型|描述|
|---|---|---|
|ts_code|str|TS股票代码|
|ann_date|str|公告日期|
|end_date|str|报告期|
|holder_name|str|股东名称|
|hold_amount|float|持有数量（股）|
|hold_ratio|float|占总股本比例(%)|
|hold_float_ratio|float|占流通股本比例(%)|
|hold_change|float|持股变动|
|holder_type|str|股东类型|

**接口用法**

```python

pro = ts.pro_api()

df = pro.top10_holders(ts_code='600000.SH', start_date='20170101', end_date='20171231')
```

或者

```python

df = pro.query('top10_holders', ts_code='600000.SH', start_date='20170101', end_date='20171231')
```

**数据样例**

```
     ts_code  ann_date  end_date                        holder_name   hold_amount  hold_ratio
0  600000.SH  20180428  20171231   富德生命人寿保险股份有限公司-传统  2.779437e+09        9.47
1  600000.SH  20180428  20171231        上海国鑫投资发展有限公司  9.455690e+08        3.22
2  600000.SH  20180428  20171231  富德生命人寿保险股份有限公司-万能H  1.270429e+09        4.33
3  600000.SH  20180428  20171231  富德生命人寿保险股份有限公司-资本金  1.763232e+09        6.01
4  600000.SH  20180428  20171231          上海国际集团有限公司  6.331323e+09       21.57
5  600000.SH  20180428  20171231      中国移动通信集团广东有限公司  5.334893e+09       18.18
6  600000.SH  20180428  20171231        中国证券金融股份有限公司  1.216979e+09        4.15
7  600000.SH  20180428  20171231       梧桐树投资平台有限责任公司  8.861313e+08        3.02
8  600000.SH  20180428  20171231      中央汇金资产管理有限责任公司  3.985214e+08        1.36
9  600000.SH  20180428  20171231       上海上国投资产管理有限公司  1.395571e+09        4.75
```

## 股权质押统计数据

---

接口：pledge_stat  
描述：获取股票质押统计数据  
限量：单次最大1000  
积分：用户需要至少500积分才可以调取，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|股票代码|
|end_date|str|N|截止日期|

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|TS代码|
|end_date|str|Y|截止日期|
|pledge_count|int|Y|质押次数|
|unrest_pledge|float|Y|无限售股质押数量（万）|
|rest_pledge|float|Y|限售股份质押数量（万）|
|total_share|float|Y|总股本|
|pledge_ratio|float|Y|质押比例|

**接口使用**

```pyhton
pro = ts.pro_api()
#或者
#pro = ts.pro_api('your token')


df = pro.pledge_stat(ts_code='000014.SZ')
```

或者

```python

df = pro.query('pledge_stat', ts_code='000014.SZ')
```

**数据示例**

```
             ts_code  end_date  pledge_count  unrest_pledge  rest_pledge  \
0    000014.SZ  20180928            23          63.16          0.0   
1    000014.SZ  20180921            24          63.17          0.0   
2    000014.SZ  20180914            24          63.17          0.0   
3    000014.SZ  20180907            28          63.69          0.0   
4    000014.SZ  20180831            28          63.69          0.0   
5    000014.SZ  20180824            29          64.74          0.0   
6    000014.SZ  20180817            29          64.74          0.0   
7    000014.SZ  20180810            29          64.74          0.0   
8    000014.SZ  20180803            29          64.74          0.0   
9    000014.SZ  20180727            29          64.74          0.0   
10   000014.SZ  20180720            29          64.74          0.0   
11   000014.SZ  20180713            29          64.74          0.0   
12   000014.SZ  20180706            30          64.77          0.0   
13   000014.SZ  20180629            30          64.77          0.0   
14   000014.SZ  20180622            30          64.77          0.0   
15   000014.SZ  20180615            28          66.50          0.0 
```

## 股权质押明细

---

接口：pledge_detail  
描述：获取股票质押明细数据  
限量：单次最大1000  
积分：用户需要至少500积分才可以调取，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|Y|股票代码|

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|TS股票代码|
|ann_date|str|Y|公告日期|
|holder_name|str|Y|股东名称|
|pledge_amount|float|Y|质押数量（万股）|
|start_date|str|Y|质押开始日期|
|end_date|str|Y|质押结束日期|
|is_release|str|Y|是否已解押|
|release_date|str|Y|解押日期|
|pledgor|str|Y|质押方|
|holding_amount|float|Y|持股总数（万股）|
|pledged_amount|float|Y|质押总数（万股）|
|p_total_ratio|float|Y|本次质押占总股本比例|
|h_total_ratio|float|Y|持股总数占总股本比例|
|is_buyback|str|Y|是否回购|

**接口使用**

```pyhton
pro = ts.pro_api()
#或者
#pro = ts.pro_api('your token')


df = pro.pledge_detail(ts_code='000014.SZ')
```

或者

```python

df = pro.query('pledge_detail', ts_code='000014.SZ')
```

**数据示例**

```
             ts_code  ann_date         holder_name          pledge_amount start_date  \
0  000014.SZ  20180106  中科汇通(深圳)股权投资基金有限公司       500.0000   20171114   
1  000014.SZ  20180106  中科汇通(深圳)股权投资基金有限公司       922.0055   20171114   
2  000014.SZ  20171221  中科汇通(深圳)股权投资基金有限公司       600.0000   20171114   
3  000014.SZ  20171216  中科汇通(深圳)股权投资基金有限公司       300.0000   20171114   
4  000014.SZ  20171111  中科汇通(深圳)股权投资基金有限公司       2321.9955   20151127   
5  000014.SZ  20170616  中科汇通(深圳)股权投资基金有限公司       0.0100   20151127   
6  000014.SZ  20060927  深圳市沙河实业(集团)有限公司             1936.3698   20050119  
```

## 股票回购

---

接口：repurchase  
描述：获取上市公司回购股票数据  
积分：用户需要至少600积分才可以调取，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ann_date|str|N|公告日期（任意填参数，如果都不填，单次默认返回2000条）|
|start_date|str|N|公告开始日期|
|end_date|str|N|公告结束日期|

以上日期格式为：YYYYMMDD，比如20181010

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|TS代码|
|ann_date|str|Y|公告日期|
|end_date|str|Y|截止日期|
|proc|str|Y|进度|
|exp_date|str|Y|过期日期|
|vol|float|Y|回购数量|
|amount|float|Y|回购金额|
|high_limit|float|Y|回购最高价|
|low_limit|float|Y|回购最低价|

**接口示例**

```python

pro = ts.pro_api()

df = pro.repurchase(ann_date='', start_date='20180101', end_date='20180510')

#取某日
df = pro.repurchase(ann_date='20181010')
```

**数据示例**

```
  ts_code  ann_date  end_date    proc  exp_date         vol        amount  \
0   300451.SZ  20181010  20181008      完成      None     51900.0  4.498500e+05   
1   300396.SZ  20181010      None  股东大会通过  20191010         NaN  5.000000e+07   
2   000813.SZ  20181010  20180930      实施      None  15450767.0  1.243010e+08   
3   300451.SZ  20181010  20181008      完成      None      4500.0  3.708000e+04   
4   002334.SZ  20181010  20181009      实施      None   7749553.0  3.826948e+07   
5   600351.SH  20181010  20181010      实施      None   7035198.0  4.999188e+07   
6   002104.SZ  20181010  20180930      实施      None    569100.0  3.584390e+06   
7   603017.SH  20181010  20181009      实施      None   4418358.0  4.398425e+07   
8   002511.SZ  20181010      None  股东大会通过  20190410         NaN  2.000000e+08   
9   603180.SH  20181010  20181009      实施      None    315700.0  1.817800e+07   
10  002567.SZ  20181010  20180930      实施      None   1743273.0  7.815226e+06 


    high_limit  low_limit  
0       12.350      8.240  
1       21.000        NaN  
2        8.400      7.800  
3        8.240      8.240  
4        6.060      4.370  
5        7.490      6.850  
6        6.352      6.160  
7       10.600      9.080  
8        9.500        NaN  
9       59.860     55.060  
10       4.600      4.370  
```

## 限售股解禁

---

接口：share_float  
描述：获取限售股解禁  
限量：单次最大6000条，总量不限制  
积分：120分可调取，每分钟内限制次数，超过5000积分频次相对较高，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

  
  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|TS股票代码|
|ann_date|str|N|公告日期（日期格式：YYYYMMDD，下同）|
|float_date|str|N|解禁日期|
|start_date|str|N|解禁开始日期|
|end_date|str|N|解禁结束日期|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|TS代码|
|ann_date|str|Y|公告日期|
|float_date|str|Y|解禁日期|
|float_share|float|Y|流通股份(股)|
|float_ratio|float|Y|流通股份占总股本比率|
|holder_name|str|Y|股东名称|
|share_type|str|Y|股份类型|

  
  

**接口使用**

```pyhton

pro = ts.pro_api()

df = pro.share_float(ann_date='20181220')
```

  
  

**数据示例**

```
    ts_code    ann_date float_date  float_share  float_ratio         holder_name  \
0   000998.SZ  20181220   20211221   25076106.0       1.9041              王义波   
1   000998.SZ  20181220   20211221   11265340.0       0.8554              彭泽斌   
2   000998.SZ  20181220   20211221   10820446.0       0.8216               杨蔚   
3   000998.SZ  20181220   20211221    2704317.0       0.2053               王宏   
4   000998.SZ  20181220   20211221    2704317.0       0.2053              姜书贤   
5   000998.SZ  20181220   20211221    2952186.0       0.2242              谢玉迁   
6   000998.SZ  20181220   20211221    3022098.0       0.2295              陆利行   
7   000998.SZ  20181220   20211221     190668.0       0.0145              史泽琪   
8   000998.SZ  20181220   20211221     190668.0       0.0145               张林   
9   000998.SZ  20181220   20211221      95334.0       0.0072              孙继明   
10  000998.SZ  20181220   20211221      95334.0       0.0072              王青才   
11  000998.SZ  20181220   20211221      95334.0       0.0072               刘榜   
12  000998.SZ  20181220   20211221      63556.0       0.0048               朱静   
13  000998.SZ  20181220   20211221      63556.0       0.0048              陈亮亮   
14  000998.SZ  20181220   20211221      63556.0       0.0048              杜培林   
15  000998.SZ  20181220   20211221      63556.0       0.0048               高飞   
16  000998.SZ  20181220   20211221      63556.0       0.0048              胡素华   
17  000998.SZ  20181220   20211221      63556.0       0.0048              王明磊   
18  000998.SZ  20181220   20211221      63556.0       0.0048              刘占才   
19  000998.SZ  20181220   20211221      63556.0       0.0048              傅兆作   
20  000998.SZ  20181220   20211221      63556.0       0.0048              应银链   

     share_type  
0        定增股份  
1        定增股份  
2        定增股份  
3        定增股份  
4        定增股份  
5        定增股份  
6        定增股份  
7        定增股份  
8        定增股份  
9        定增股份  
10       定增股份  
11       定增股份  
12       定增股份  
13       定增股份  
14       定增股份  
15       定增股份  
16       定增股份  
17       定增股份  
18       定增股份  
19       定增股份  
20       定增股份  
```

## 大宗交易

---

接口：block_trade  
描述：大宗交易  
限量：单次最大1000条，总量不限制  
积分：300积分可调取，每分钟内限制次数，超过5000积分频次相对较高，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

  
  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|TS代码（股票代码和日期至少输入一个参数）|
|trade_date|str|N|交易日期（格式：YYYYMMDD，下同）|
|start_date|str|N|开始日期|
|end_date|str|N|结束日期|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|TS代码|
|trade_date|str|Y|交易日历|
|price|float|Y|成交价|
|vol|float|Y|成交量（万股）|
|amount|float|Y|成交金额|
|buyer|str|Y|买方营业部|
|seller|str|Y|卖方营业部|

  
  

**接口使用**

```pyhton

pro = ts.pro_api()

df = pro.block_trade(trade_date='20181227')
```

  
  

**数据示例**

```
    ts_code   trade_date  price      vol     amount  \
0   600436.SH   20181227  86.95     9.49     825.16   
1   603160.SH   20181227  70.00    28.57    2000.00   
2   601318.SH   20181227  55.76  1800.00  100368.00   
3   601318.SH   20181227  55.76   332.00   18512.32   
4   601318.SH   20181227  55.76   288.00   16058.88   
5   601318.SH   20181227  55.76   170.00    9479.20   
6   601318.SH   20181227  55.76    72.00    4014.72   
7   603508.SH   20181227  35.72    56.00    2000.32   
8   600681.SH   20181227  10.69   111.00    1186.59   
9   603606.SH   20181227   8.93    23.92     213.61   
10  601108.SH   20181227   6.76  2000.00   13520.00   
11  601108.SH   20181227   6.41   700.00    4487.00   
12  600746.SH   20181227   5.75   244.71    1407.08   
13  600016.SH   20181227   5.65  1326.00    7491.90   
14  600016.SH   20181227   5.54  3500.00   19390.00   
15  601011.SH   20181227   5.00   659.26    3296.30   
16  601011.SH   20181227   5.00   596.75    2983.77   
17  600984.SH   20181227   4.96   296.00    1468.16   
18  601398.SH   20181227   4.74   172.20     816.23  

                                                 buyer                     seller  
0   安信证券股份有限公司成都交子大道证券营业部      安信证券股份有限公司成都交子大道证券营业部  
1   中国银河证券股份有限公司总部      长江证券股份有限公司武汉巨龙大道证券营业部  
2   恒泰证券股份有限公司总部                       机构专用  
3   华鑫证券有限责任公司合肥梅山路证券营业部                       机构专用  
4   华泰证券股份有限公司上海徐汇区天钥桥路证券营业部                       机构专用  
5   东兴证券股份有限公司上海肇嘉浜路证券营业部                       机构专用  
6   长江证券股份有限公司荆州北京西路证券营业部                       机构专用  
7   东方证券股份有限公司公司总部         江海证券有限公司深圳民田路证券营业部  
8   国信证券股份有限公司深圳振华路证券营业部         中航证券有限公司深圳春风路证券营业部  
9   广发证券股份有限公司广州天河北路大都会广场证券营业部    第一创业证券股份有限公司深圳深南大道证券营业部  
10  中国国际金融股份有限公司北京建国门外大街证券营业部       财通证券股份有限公司杭州体育馆证券营业部  
11  中国银河证券股份有限公司杭州庆春路证券营业部      财通证券股份有限公司淳安新安大街证券营业部  
12  中信证券股份有限公司镇江正东路证券营业部        中信证券股份有限公司总部(非营业场所)  
13  太平洋证券股份有限公司厦门高林中路证券营业部      华福证券有限责任公司厦门湖滨南路证券营业部  
14  中信证券股份有限公司北京安外大街证券营业部                       机构专用  
15  中国中投证券有限责任公司合肥长江中路证券营业部      中信证券股份有限公司中山中山四路证券营业部  
16  中国中投证券有限责任公司合肥长江中路证券营业部         海通证券股份有限公司北京光华路营业部  
17  财富证券有限责任公司长沙八一路证券营业部         中航证券有限公司北京慧忠路证券营业部  
18  九州证券股份有限公司重庆分公司            九州证券股份有限公司重庆分公司  
```

## 股东增减持

---

接口：stk_holdertrade  
描述：获取上市公司增减持数据，了解重要股东近期及历史上的股份增减变化  
限量：单次最大提取3000行记录，总量不限制  
积分：用户需要至少2000积分才可以调取。基础积分有流量控制，积分越多权限越大，5000积分以上无明显限制，请自行提高积分，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

  
  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|TS股票代码|
|ann_date|str|N|公告日期|
|start_date|str|N|公告开始日期|
|end_date|str|N|公告结束日期|
|trade_type|str|N|交易类型IN增持DE减持|
|holder_type|str|N|股东类型C公司P个人G高管|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|TS代码|
|ann_date|str|Y|公告日期|
|holder_name|str|Y|股东名称|
|holder_type|str|Y|股东类型G高管P个人C公司|
|in_de|str|Y|类型IN增持DE减持|
|change_vol|float|Y|变动数量|
|change_ratio|float|Y|占流通比例（%）|
|after_share|float|Y|变动后持股|
|after_ratio|float|Y|变动后占流通比例（%）|
|avg_price|float|Y|平均价格|
|total_share|float|Y|持股总数|
|begin_date|str|N|增减持开始日期|
|close_date|str|N|增减持结束日期|

  
  

**接口示例**

```python

#获取单日全部增减持数据
df = pro.stk_holdertrade(ann_date='20190426')

#获取单个股票数据
df = pro.stk_holdertrade(ts_code='002149.SZ')

#获取当日增持数据
df = pro.stk_holdertrade(ann_date='20190426', trade_type='IN')
```

  
  

**数据示例**

```
    ts_code    ann_date          holder_name     holder_type in_de  \
0   300216.SZ  20190426          郑国胜           P    DE   
1   300216.SZ  20190426          黄盛秋           P    DE   
2   300216.SZ  20190426          刘燕             G    DE   
3   300216.SZ  20190426          邓铁山           G    DE   
4   002806.SZ  20190426          广东省科技创业投资有限公司           C    DE   
5   603801.SH  20190426          尚志有限公司           C    DE   
6   600728.SH  20190426          重庆中新融鑫投资中心(有限合伙)           C    DE   
7   300115.SZ  20190426          新疆长盈粤富股权投资有限公司           C    DE   
8   300115.SZ  20190426           新疆长盈粤富股权投资有限公司           C    DE   
9   601288.SH  20190426          上海锦江国际旅游股份有限公司           C    DE   
10  603906.SH  20190426          建投嘉驰(上海)投资有限公司           C    DE   

change_vol  change_ratio  after_share  after_ratio  avg_price  total_share  
0     387871.0        0.1356    3385659.0       1.1834     3.8100    3385659.0  
1      49056.0        0.0171    1194457.0       0.4175     3.7800    1194457.0  
2     498062.0        0.1741          0.0          NaN     3.6700    8892000.0  
3    2358900.0        0.8245         25.0       0.0000     3.2100    7076800.0  
4    1086100.0        1.8826   10836700.0      18.7838    21.5100   25499200.0  
5    3200000.0        3.8450    6808299.0       8.1806    31.5500    6808299.0  
6   14710000.0        0.9170   76942195.0       4.7965     9.9400   76942195.0  
7    9470000.0        1.0457  378846759.0      41.8343    13.6400  378846759.0  
8    8690000.0        0.9596  370156759.0      40.8748    13.6800  370156759.0  
9   14868500.0        0.0051          0.0          NaN        NaN          0.0  
10   2540640.0        2.7223   22144800.0      23.7286    13.0241   22144800.0  
```


# 特色数据

## 卖方盈利预测数据

---

接口：report_rc  
描述：获取券商（卖方）每天研报的盈利预测数据，数据从2010年开始，每晚19~22点更新当日数据  
限量：单次最大3000条，可分页和循环提取所有数据  
权限：本接口120积分可以试用，每天10次请求，正式权限需8000积分，每天可请求100000次，10000积分以上无总量限制。

  
  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|股票代码|
|report_date|str|N|报告日期|
|start_date|str|N|报告开始日期|
|end_date|str|N|报告结束日期|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|股票代码|
|name|str|Y|股票名称|
|report_date|str|Y|研报日期|
|report_title|str|Y|报告标题|
|report_type|str|Y|报告类型|
|classify|str|Y|报告分类|
|org_name|str|Y|机构名称|
|author_name|str|Y|作者|
|quarter|str|Y|预测报告期|
|op_rt|float|Y|预测营业收入（万元）|
|op_pr|float|Y|预测营业利润（万元）|
|tp|float|Y|预测利润总额（万元）|
|np|float|Y|预测净利润（万元）|
|eps|float|Y|预测每股收益（元）|
|pe|float|Y|预测市盈率|
|rd|float|Y|预测股息率|
|roe|float|Y|预测净资产收益率|
|ev_ebitda|float|Y|预测EV/EBITDA|
|rating|str|Y|卖方评级|
|max_price|float|Y|预测最高目标价|
|min_price|float|Y|预测最低目标价|
|imp_dg|str|N|机构关注度|
|create_time|datetime|N|TS数据更新时间|

  
  

**接口用法**

```python

pro = ts.pro_api()

df = pro.report_rc(ts_code='', report_date='20220429')
```

  
  

**数据样例**

```
    ts_code        name      report_date   classify   org_name quarter     eps       pe
0     000733.SZ  振华科技    20220429     一般报告     安信证券  2024Q4  6.7800  14.2000
1     000858.SZ   五粮液    20220429     一般报告     华西证券  2022Q4  6.9800  23.7700
2     000858.SZ   五粮液    20220429     一般报告     华西证券  2023Q4  8.2200  20.1800
3     000858.SZ   五粮液    20220429     一般报告     华西证券  2024Q4  9.5800  17.3100
4     000858.SZ   五粮液    20220429     一般报告     信达证券  2022Q4  7.1100  23.3100
...         ...   ...         ...      ...      ...     ...     ...      ...
2552  688385.SH  复旦微电    20220429     一般报告     方正证券  2022Q4  0.9100  62.7000
2553  688385.SH  复旦微电    20220429     一般报告     方正证券  2023Q4  1.1600  49.1900
2554  688385.SH  复旦微电    20220429     一般报告     方正证券  2024Q4  1.5800  36.3200
2555  000733.SZ  振华科技    20220429     一般报告     安信证券  2022Q4  4.3000  22.4000
2556  000733.SZ  振华科技    20220429     一般报告     安信证券  2023Q4  5.4100  17.8000
```


## 每日筹码及胜率

---

接口：cyq_perf  
描述：获取A股每日筹码平均成本和胜率情况，每天17~18点左右更新，数据从2018年开始  
来源：Tushare社区  
限量：单次最大5000条，可以分页或者循环提取  
积分：120积分可以试用(查看数据)，5000积分每天20000次，10000积分每天200000次，15000积分每天不限总量

  
  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|股票代码|
|trade_date|str|N|交易日期（YYYYMMDD）|
|start_date|str|N|开始日期|
|end_date|str|N|结束日期|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|股票代码|
|trade_date|str|Y|交易日期|
|his_low|float|Y|历史最低价|
|his_high|float|Y|历史最高价|
|cost_5pct|float|Y|5分位成本|
|cost_15pct|float|Y|15分位成本|
|cost_50pct|float|Y|50分位成本|
|cost_85pct|float|Y|85分位成本|
|cost_95pct|float|Y|95分位成本|
|weight_avg|float|Y|加权平均成本|
|winner_rate|float|Y|胜率|

  
  

**接口用法**

```python

pro = ts.pro_api()

df = pro.cyq_perf(ts_code='600000.SH', start_date='20220101', end_date='20220429')
```

  
  

**数据样例**

```
      ts_code trade_date his_low his_high cost_5pct cost_95pct weight_avg winner_rate
0   600000.SH   20220429    0.72    12.16      8.18      11.34       9.76        3.52
1   600000.SH   20220428    0.72    12.16      8.24      11.34       9.76        3.08
2   600000.SH   20220427    0.72    12.16      8.30      11.34       9.76        1.71
3   600000.SH   20220426    0.72    12.16      8.34      11.34       9.76        2.02
4   600000.SH   20220425    0.72    12.16      8.36      11.34       9.77        1.44
..        ...        ...     ...      ...       ...        ...        ...         ...
72  600000.SH   20220110    0.72    12.16      8.60      11.36       9.89        7.62
73  600000.SH   20220107    0.72    12.16      8.60      11.36       9.89        7.59
74  600000.SH   20220106    0.72    12.16      8.60      11.36       9.89        3.92
75  600000.SH   20220105    0.72    12.16      8.60      11.36       9.89        5.65
76  600000.SH   20220104    0.72    12.16      8.60      11.36       9.89        3.93
```

## 每日筹码分布

---

接口：cyq_chips  
描述：获取A股每日的筹码分布情况，提供各价位占比，数据从2018年开始，每天17~18点之间更新当日数据  
来源：Tushare社区  
限量：单次最大2000条，可以按股票代码和日期循环提取  
积分：120积分可以试用查看数据，5000积分每天20000次，10000积分每天200000次，15000积分每天不限总量

  
  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|股票代码|
|trade_date|str|N|交易日期（YYYYMMDD）|
|start_date|str|N|开始日期|
|end_date|str|N|结束日期|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|股票代码|
|trade_date|str|Y|交易日期|
|price|float|Y|成本价格|
|percent|float|Y|价格占比（%）|

  
  

**接口用法**

```python

pro = ts.pro_api()

df = pro.cyq_chips(ts_code='600000.SH', start_date='20220101', end_date='20220429')
```

  
  

**数据样例**

```
         ts_code trade_date price percent
0    600000.SH   20220429  8.96    0.56
1    600000.SH   20220429  8.94    0.40
2    600000.SH   20220429  8.92    0.34
3    600000.SH   20220429  8.90    0.32
4    600000.SH   20220429  8.88    0.27
..         ...        ...   ...     ...
995  600000.SH   20220418  7.26    0.01
996  600000.SH   20220418  7.24    0.01
997  600000.SH   20220418  7.22    0.01
998  600000.SH   20220418  7.20    0.01
999  600000.SH   20220418  7.18    0.01
```

## 股票技术因子（量化因子）

---

接口：stk_factor  
描述：获取股票每日技术面因子数据，用于跟踪股票当前走势情况，数据由Tushare社区自产，覆盖全历史  
限量：单次最大10000条，可以循环或者分页提取  
积分：5000积分每分钟可以请求100次，8000积分以上每分钟500次，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

```
注：
1、本接口的前复权行情是从最新一个交易日开始往前复权，是历史当日的数据快照数据不更新
2、pro_bar接口的前复权是动态复权，即以end_date参数开始往前复权，与本接口会存在不一致的可能
3、本接口技术指标都是基于前复权价格计算
```

  
  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|股票代码|
|trade_date|str|N|交易日期 （yyyymmdd，下同）|
|start_date|str|N|开始日期|
|end_date|str|N|结束日期|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|股票代码|
|trade_date|str|Y|交易日期|
|close|float|Y|收盘价|
|open|float|Y|开盘价|
|high|float|Y|最高价|
|low|float|Y|最低价|
|pre_close|float|Y|昨收价|
|change|float|Y|涨跌额|
|pct_change|float|Y|涨跌幅|
|vol|float|Y|成交量 （手）|
|amount|float|Y|成交额 （千元）|
|adj_factor|float|Y|复权因子|
|open_hfq|float|Y|开盘价后复权|
|open_qfq|float|Y|开盘价前复权|
|close_hfq|float|Y|收盘价后复权|
|close_qfq|float|Y|收盘价前复权|
|high_hfq|float|Y|最高价后复权|
|high_qfq|float|Y|最高价前复权|
|low_hfq|float|Y|最低价后复权|
|low_qfq|float|Y|最低价前复权|
|pre_close_hfq|float|Y|昨收价后复权|
|pre_close_qfq|float|Y|昨收价前复权|
|macd_dif|float|Y|MCAD_DIF (基于前复权价格计算，下同)|
|macd_dea|float|Y|MCAD_DEA|
|macd|float|Y|MCAD|
|kdj_k|float|Y|KDJ_K|
|kdj_d|float|Y|KDJ_D|
|kdj_j|float|Y|KDJ_J|
|rsi_6|float|Y|RSI_6|
|rsi_12|float|Y|RSI_12|
|rsi_24|float|Y|RSI_24|
|boll_upper|float|Y|BOLL_UPPER|
|boll_mid|float|Y|BOLL_MID|
|boll_lower|float|Y|BOLL_LOWER|
|cci|float|Y|CCI|

## 股票技术面因子(专业版)

---

接口：stk_factor_pro  
描述：获取股票每日技术面因子数据，用于跟踪股票当前走势情况，数据由Tushare社区自产，覆盖全历史；输出参数_bfq表示不复权，_qfq表示前复权 _hfq表示后复权，描述中说明了因子的默认传参，如需要特殊参数或者更多因子可以联系管理员评估  
限量：单次调取最多返回10000条数据，可以通过日期参数循环  
积分：5000积分每分钟可以请求30次，8000积分以上每分钟500次，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|股票代码|
|trade_date|str|N|交易日期(格式：yyyymmdd，下同)|
|start_date|str|N|开始日期|
|end_date|str|N|结束日期|

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|股票代码|
|trade_date|str|Y|交易日期|
|open|float|Y|开盘价|
|open_hfq|float|Y|开盘价（后复权）|
|open_qfq|float|Y|开盘价（前复权）|
|high|float|Y|最高价|
|high_hfq|float|Y|最高价（后复权）|
|high_qfq|float|Y|最高价（前复权）|
|low|float|Y|最低价|
|low_hfq|float|Y|最低价（后复权）|
|low_qfq|float|Y|最低价（前复权）|
|close|float|Y|收盘价|
|close_hfq|float|Y|收盘价（后复权）|
|close_qfq|float|Y|收盘价（前复权）|
|pre_close|float|Y|昨收价(前复权)--为daily接口的pre_close,以当时复权因子计算值跟前一日close_qfq对不上，可不用|
|change|float|Y|涨跌额|
|pct_chg|float|Y|涨跌幅 （未复权，如果是复权请用 通用行情接口 ）|
|vol|float|Y|成交量 （手）|
|amount|float|Y|成交额 （千元）|
|turnover_rate|float|Y|换手率（%）|
|turnover_rate_f|float|Y|换手率（自由流通股）|
|volume_ratio|float|Y|量比|
|pe|float|Y|市盈率（总市值/净利润， 亏损的PE为空）|
|pe_ttm|float|Y|市盈率（TTM，亏损的PE为空）|
|pb|float|Y|市净率（总市值/净资产）|
|ps|float|Y|市销率|
|ps_ttm|float|Y|市销率（TTM）|
|dv_ratio|float|Y|股息率 （%）|
|dv_ttm|float|Y|股息率（TTM）（%）|
|total_share|float|Y|总股本 （万股）|
|float_share|float|Y|流通股本 （万股）|
|free_share|float|Y|自由流通股本 （万）|
|total_mv|float|Y|总市值 （万元）|
|circ_mv|float|Y|流通市值（万元）|
|adj_factor|float|Y|复权因子|
|asi_bfq|float|Y|振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10|
|asi_hfq|float|Y|振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10|
|asi_qfq|float|Y|振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10|
|asit_bfq|float|Y|振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10|
|asit_hfq|float|Y|振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10|
|asit_qfq|float|Y|振动升降指标-OPEN, CLOSE, HIGH, LOW, M1=26, M2=10|
|atr_bfq|float|Y|真实波动N日平均值-CLOSE, HIGH, LOW, N=20|
|atr_hfq|float|Y|真实波动N日平均值-CLOSE, HIGH, LOW, N=20|
|atr_qfq|float|Y|真实波动N日平均值-CLOSE, HIGH, LOW, N=20|
|bbi_bfq|float|Y|BBI多空指标-CLOSE, M1=3, M2=6, M3=12, M4=20|
|bbi_hfq|float|Y|BBI多空指标-CLOSE, M1=3, M2=6, M3=12, M4=21|
|bbi_qfq|float|Y|BBI多空指标-CLOSE, M1=3, M2=6, M3=12, M4=22|
|bias1_bfq|float|Y|BIAS乖离率-CLOSE, L1=6, L2=12, L3=24|
|bias1_hfq|float|Y|BIAS乖离率-CLOSE, L1=6, L2=12, L3=24|
|bias1_qfq|float|Y|BIAS乖离率-CLOSE, L1=6, L2=12, L3=24|
|bias2_bfq|float|Y|BIAS乖离率-CLOSE, L1=6, L2=12, L3=24|
|bias2_hfq|float|Y|BIAS乖离率-CLOSE, L1=6, L2=12, L3=24|
|bias2_qfq|float|Y|BIAS乖离率-CLOSE, L1=6, L2=12, L3=24|
|bias3_bfq|float|Y|BIAS乖离率-CLOSE, L1=6, L2=12, L3=24|
|bias3_hfq|float|Y|BIAS乖离率-CLOSE, L1=6, L2=12, L3=24|
|bias3_qfq|float|Y|BIAS乖离率-CLOSE, L1=6, L2=12, L3=24|
|boll_lower_bfq|float|Y|BOLL指标，布林带-CLOSE, N=20, P=2|
|boll_lower_hfq|float|Y|BOLL指标，布林带-CLOSE, N=20, P=2|
|boll_lower_qfq|float|Y|BOLL指标，布林带-CLOSE, N=20, P=2|
|boll_mid_bfq|float|Y|BOLL指标，布林带-CLOSE, N=20, P=2|
|boll_mid_hfq|float|Y|BOLL指标，布林带-CLOSE, N=20, P=2|
|boll_mid_qfq|float|Y|BOLL指标，布林带-CLOSE, N=20, P=2|
|boll_upper_bfq|float|Y|BOLL指标，布林带-CLOSE, N=20, P=2|
|boll_upper_hfq|float|Y|BOLL指标，布林带-CLOSE, N=20, P=2|
|boll_upper_qfq|float|Y|BOLL指标，布林带-CLOSE, N=20, P=2|
|brar_ar_bfq|float|Y|BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26|
|brar_ar_hfq|float|Y|BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26|
|brar_ar_qfq|float|Y|BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26|
|brar_br_bfq|float|Y|BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26|
|brar_br_hfq|float|Y|BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26|
|brar_br_qfq|float|Y|BRAR情绪指标-OPEN, CLOSE, HIGH, LOW, M1=26|
|cci_bfq|float|Y|顺势指标又叫CCI指标-CLOSE, HIGH, LOW, N=14|
|cci_hfq|float|Y|顺势指标又叫CCI指标-CLOSE, HIGH, LOW, N=14|
|cci_qfq|float|Y|顺势指标又叫CCI指标-CLOSE, HIGH, LOW, N=14|
|cr_bfq|float|Y|CR价格动量指标-CLOSE, HIGH, LOW, N=20|
|cr_hfq|float|Y|CR价格动量指标-CLOSE, HIGH, LOW, N=20|
|cr_qfq|float|Y|CR价格动量指标-CLOSE, HIGH, LOW, N=20|
|dfma_dif_bfq|float|Y|平行线差指标-CLOSE, N1=10, N2=50, M=10|
|dfma_dif_hfq|float|Y|平行线差指标-CLOSE, N1=10, N2=50, M=10|
|dfma_dif_qfq|float|Y|平行线差指标-CLOSE, N1=10, N2=50, M=10|
|dfma_difma_bfq|float|Y|平行线差指标-CLOSE, N1=10, N2=50, M=10|
|dfma_difma_hfq|float|Y|平行线差指标-CLOSE, N1=10, N2=50, M=10|
|dfma_difma_qfq|float|Y|平行线差指标-CLOSE, N1=10, N2=50, M=10|
|dmi_adx_bfq|float|Y|动向指标-CLOSE, HIGH, LOW, M1=14, M2=6|
|dmi_adx_hfq|float|Y|动向指标-CLOSE, HIGH, LOW, M1=14, M2=6|
|dmi_adx_qfq|float|Y|动向指标-CLOSE, HIGH, LOW, M1=14, M2=6|
|dmi_adxr_bfq|float|Y|动向指标-CLOSE, HIGH, LOW, M1=14, M2=6|
|dmi_adxr_hfq|float|Y|动向指标-CLOSE, HIGH, LOW, M1=14, M2=6|
|dmi_adxr_qfq|float|Y|动向指标-CLOSE, HIGH, LOW, M1=14, M2=6|
|dmi_mdi_bfq|float|Y|动向指标-CLOSE, HIGH, LOW, M1=14, M2=6|
|dmi_mdi_hfq|float|Y|动向指标-CLOSE, HIGH, LOW, M1=14, M2=6|
|dmi_mdi_qfq|float|Y|动向指标-CLOSE, HIGH, LOW, M1=14, M2=6|
|dmi_pdi_bfq|float|Y|动向指标-CLOSE, HIGH, LOW, M1=14, M2=6|
|dmi_pdi_hfq|float|Y|动向指标-CLOSE, HIGH, LOW, M1=14, M2=6|
|dmi_pdi_qfq|float|Y|动向指标-CLOSE, HIGH, LOW, M1=14, M2=6|
|downdays|float|Y|连跌天数|
|updays|float|Y|连涨天数|
|dpo_bfq|float|Y|区间震荡线-CLOSE, M1=20, M2=10, M3=6|
|dpo_hfq|float|Y|区间震荡线-CLOSE, M1=20, M2=10, M3=6|
|dpo_qfq|float|Y|区间震荡线-CLOSE, M1=20, M2=10, M3=6|
|madpo_bfq|float|Y|区间震荡线-CLOSE, M1=20, M2=10, M3=6|
|madpo_hfq|float|Y|区间震荡线-CLOSE, M1=20, M2=10, M3=6|
|madpo_qfq|float|Y|区间震荡线-CLOSE, M1=20, M2=10, M3=6|
|ema_bfq_10|float|Y|指数移动平均-N=10|
|ema_bfq_20|float|Y|指数移动平均-N=20|
|ema_bfq_250|float|Y|指数移动平均-N=250|
|ema_bfq_30|float|Y|指数移动平均-N=30|
|ema_bfq_5|float|Y|指数移动平均-N=5|
|ema_bfq_60|float|Y|指数移动平均-N=60|
|ema_bfq_90|float|Y|指数移动平均-N=90|
|ema_hfq_10|float|Y|指数移动平均-N=10|
|ema_hfq_20|float|Y|指数移动平均-N=20|
|ema_hfq_250|float|Y|指数移动平均-N=250|
|ema_hfq_30|float|Y|指数移动平均-N=30|
|ema_hfq_5|float|Y|指数移动平均-N=5|
|ema_hfq_60|float|Y|指数移动平均-N=60|
|ema_hfq_90|float|Y|指数移动平均-N=90|
|ema_qfq_10|float|Y|指数移动平均-N=10|
|ema_qfq_20|float|Y|指数移动平均-N=20|
|ema_qfq_250|float|Y|指数移动平均-N=250|
|ema_qfq_30|float|Y|指数移动平均-N=30|
|ema_qfq_5|float|Y|指数移动平均-N=5|
|ema_qfq_60|float|Y|指数移动平均-N=60|
|ema_qfq_90|float|Y|指数移动平均-N=90|
|emv_bfq|float|Y|简易波动指标-HIGH, LOW, VOL, N=14, M=9|
|emv_hfq|float|Y|简易波动指标-HIGH, LOW, VOL, N=14, M=9|
|emv_qfq|float|Y|简易波动指标-HIGH, LOW, VOL, N=14, M=9|
|maemv_bfq|float|Y|简易波动指标-HIGH, LOW, VOL, N=14, M=9|
|maemv_hfq|float|Y|简易波动指标-HIGH, LOW, VOL, N=14, M=9|
|maemv_qfq|float|Y|简易波动指标-HIGH, LOW, VOL, N=14, M=9|
|expma_12_bfq|float|Y|EMA指数平均数指标-CLOSE, N1=12, N2=50|
|expma_12_hfq|float|Y|EMA指数平均数指标-CLOSE, N1=12, N2=50|
|expma_12_qfq|float|Y|EMA指数平均数指标-CLOSE, N1=12, N2=50|
|expma_50_bfq|float|Y|EMA指数平均数指标-CLOSE, N1=12, N2=50|
|expma_50_hfq|float|Y|EMA指数平均数指标-CLOSE, N1=12, N2=50|
|expma_50_qfq|float|Y|EMA指数平均数指标-CLOSE, N1=12, N2=50|
|kdj_bfq|float|Y|KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3|
|kdj_hfq|float|Y|KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3|
|kdj_qfq|float|Y|KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3|
|kdj_d_bfq|float|Y|KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3|
|kdj_d_hfq|float|Y|KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3|
|kdj_d_qfq|float|Y|KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3|
|kdj_k_bfq|float|Y|KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3|
|kdj_k_hfq|float|Y|KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3|
|kdj_k_qfq|float|Y|KDJ指标-CLOSE, HIGH, LOW, N=9, M1=3, M2=3|
|ktn_down_bfq|float|Y|肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10|
|ktn_down_hfq|float|Y|肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10|
|ktn_down_qfq|float|Y|肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10|
|ktn_mid_bfq|float|Y|肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10|
|ktn_mid_hfq|float|Y|肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10|
|ktn_mid_qfq|float|Y|肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10|
|ktn_upper_bfq|float|Y|肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10|
|ktn_upper_hfq|float|Y|肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10|
|ktn_upper_qfq|float|Y|肯特纳交易通道, N选20日，ATR选10日-CLOSE, HIGH, LOW, N=20, M=10|
|lowdays|float|Y|LOWRANGE(LOW)表示当前最低价是近多少周期内最低价的最小值|
|topdays|float|Y|TOPRANGE(HIGH)表示当前最高价是近多少周期内最高价的最大值|
|ma_bfq_10|float|Y|简单移动平均-N=10|
|ma_bfq_20|float|Y|简单移动平均-N=20|
|ma_bfq_250|float|Y|简单移动平均-N=250|
|ma_bfq_30|float|Y|简单移动平均-N=30|
|ma_bfq_5|float|Y|简单移动平均-N=5|
|ma_bfq_60|float|Y|简单移动平均-N=60|
|ma_bfq_90|float|Y|简单移动平均-N=90|
|ma_hfq_10|float|Y|简单移动平均-N=10|
|ma_hfq_20|float|Y|简单移动平均-N=20|
|ma_hfq_250|float|Y|简单移动平均-N=250|
|ma_hfq_30|float|Y|简单移动平均-N=30|
|ma_hfq_5|float|Y|简单移动平均-N=5|
|ma_hfq_60|float|Y|简单移动平均-N=60|
|ma_hfq_90|float|Y|简单移动平均-N=90|
|ma_qfq_10|float|Y|简单移动平均-N=10|
|ma_qfq_20|float|Y|简单移动平均-N=20|
|ma_qfq_250|float|Y|简单移动平均-N=250|
|ma_qfq_30|float|Y|简单移动平均-N=30|
|ma_qfq_5|float|Y|简单移动平均-N=5|
|ma_qfq_60|float|Y|简单移动平均-N=60|
|ma_qfq_90|float|Y|简单移动平均-N=90|
|macd_bfq|float|Y|MACD指标-CLOSE, SHORT=12, LONG=26, M=9|
|macd_hfq|float|Y|MACD指标-CLOSE, SHORT=12, LONG=26, M=9|
|macd_qfq|float|Y|MACD指标-CLOSE, SHORT=12, LONG=26, M=9|
|macd_dea_bfq|float|Y|MACD指标-CLOSE, SHORT=12, LONG=26, M=9|
|macd_dea_hfq|float|Y|MACD指标-CLOSE, SHORT=12, LONG=26, M=9|
|macd_dea_qfq|float|Y|MACD指标-CLOSE, SHORT=12, LONG=26, M=9|
|macd_dif_bfq|float|Y|MACD指标-CLOSE, SHORT=12, LONG=26, M=9|
|macd_dif_hfq|float|Y|MACD指标-CLOSE, SHORT=12, LONG=26, M=9|
|macd_dif_qfq|float|Y|MACD指标-CLOSE, SHORT=12, LONG=26, M=9|
|mass_bfq|float|Y|梅斯线-HIGH, LOW, N1=9, N2=25, M=6|
|mass_hfq|float|Y|梅斯线-HIGH, LOW, N1=9, N2=25, M=6|
|mass_qfq|float|Y|梅斯线-HIGH, LOW, N1=9, N2=25, M=6|
|ma_mass_bfq|float|Y|梅斯线-HIGH, LOW, N1=9, N2=25, M=6|
|ma_mass_hfq|float|Y|梅斯线-HIGH, LOW, N1=9, N2=25, M=6|
|ma_mass_qfq|float|Y|梅斯线-HIGH, LOW, N1=9, N2=25, M=6|
|mfi_bfq|float|Y|MFI指标是成交量的RSI指标-CLOSE, HIGH, LOW, VOL, N=14|
|mfi_hfq|float|Y|MFI指标是成交量的RSI指标-CLOSE, HIGH, LOW, VOL, N=14|
|mfi_qfq|float|Y|MFI指标是成交量的RSI指标-CLOSE, HIGH, LOW, VOL, N=14|
|mtm_bfq|float|Y|动量指标-CLOSE, N=12, M=6|
|mtm_hfq|float|Y|动量指标-CLOSE, N=12, M=6|
|mtm_qfq|float|Y|动量指标-CLOSE, N=12, M=6|
|mtmma_bfq|float|Y|动量指标-CLOSE, N=12, M=6|
|mtmma_hfq|float|Y|动量指标-CLOSE, N=12, M=6|
|mtmma_qfq|float|Y|动量指标-CLOSE, N=12, M=6|
|obv_bfq|float|Y|能量潮指标-CLOSE, VOL|
|obv_hfq|float|Y|能量潮指标-CLOSE, VOL|
|obv_qfq|float|Y|能量潮指标-CLOSE, VOL|
|psy_bfq|float|Y|投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6|
|psy_hfq|float|Y|投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6|
|psy_qfq|float|Y|投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6|
|psyma_bfq|float|Y|投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6|
|psyma_hfq|float|Y|投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6|
|psyma_qfq|float|Y|投资者对股市涨跌产生心理波动的情绪指标-CLOSE, N=12, M=6|
|roc_bfq|float|Y|变动率指标-CLOSE, N=12, M=6|
|roc_hfq|float|Y|变动率指标-CLOSE, N=12, M=6|
|roc_qfq|float|Y|变动率指标-CLOSE, N=12, M=6|
|maroc_bfq|float|Y|变动率指标-CLOSE, N=12, M=6|
|maroc_hfq|float|Y|变动率指标-CLOSE, N=12, M=6|
|maroc_qfq|float|Y|变动率指标-CLOSE, N=12, M=6|
|rsi_bfq_12|float|Y|RSI指标-CLOSE, N=12|
|rsi_bfq_24|float|Y|RSI指标-CLOSE, N=24|
|rsi_bfq_6|float|Y|RSI指标-CLOSE, N=6|
|rsi_hfq_12|float|Y|RSI指标-CLOSE, N=12|
|rsi_hfq_24|float|Y|RSI指标-CLOSE, N=24|
|rsi_hfq_6|float|Y|RSI指标-CLOSE, N=6|
|rsi_qfq_12|float|Y|RSI指标-CLOSE, N=12|
|rsi_qfq_24|float|Y|RSI指标-CLOSE, N=24|
|rsi_qfq_6|float|Y|RSI指标-CLOSE, N=6|
|taq_down_bfq|float|Y|唐安奇通道(海龟)交易指标-HIGH, LOW, 20|
|taq_down_hfq|float|Y|唐安奇通道(海龟)交易指标-HIGH, LOW, 20|
|taq_down_qfq|float|Y|唐安奇通道(海龟)交易指标-HIGH, LOW, 20|
|taq_mid_bfq|float|Y|唐安奇通道(海龟)交易指标-HIGH, LOW, 20|
|taq_mid_hfq|float|Y|唐安奇通道(海龟)交易指标-HIGH, LOW, 20|
|taq_mid_qfq|float|Y|唐安奇通道(海龟)交易指标-HIGH, LOW, 20|
|taq_up_bfq|float|Y|唐安奇通道(海龟)交易指标-HIGH, LOW, 20|
|taq_up_hfq|float|Y|唐安奇通道(海龟)交易指标-HIGH, LOW, 20|
|taq_up_qfq|float|Y|唐安奇通道(海龟)交易指标-HIGH, LOW, 20|
|trix_bfq|float|Y|三重指数平滑平均线-CLOSE, M1=12, M2=20|
|trix_hfq|float|Y|三重指数平滑平均线-CLOSE, M1=12, M2=20|
|trix_qfq|float|Y|三重指数平滑平均线-CLOSE, M1=12, M2=20|
|trma_bfq|float|Y|三重指数平滑平均线-CLOSE, M1=12, M2=20|
|trma_hfq|float|Y|三重指数平滑平均线-CLOSE, M1=12, M2=20|
|trma_qfq|float|Y|三重指数平滑平均线-CLOSE, M1=12, M2=20|
|vr_bfq|float|Y|VR容量比率-CLOSE, VOL, M1=26|
|vr_hfq|float|Y|VR容量比率-CLOSE, VOL, M1=26|
|vr_qfq|float|Y|VR容量比率-CLOSE, VOL, M1=26|
|wr_bfq|float|Y|W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6|
|wr_hfq|float|Y|W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6|
|wr_qfq|float|Y|W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6|
|wr1_bfq|float|Y|W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6|
|wr1_hfq|float|Y|W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6|
|wr1_qfq|float|Y|W&R 威廉指标-CLOSE, HIGH, LOW, N=10, N1=6|
|xsii_td1_bfq|float|Y|薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7|
|xsii_td1_hfq|float|Y|薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7|
|xsii_td1_qfq|float|Y|薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7|
|xsii_td2_bfq|float|Y|薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7|
|xsii_td2_hfq|float|Y|薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7|
|xsii_td2_qfq|float|Y|薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7|
|xsii_td3_bfq|float|Y|薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7|
|xsii_td3_hfq|float|Y|薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7|
|xsii_td3_qfq|float|Y|薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7|
|xsii_td4_bfq|float|Y|薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7|
|xsii_td4_hfq|float|Y|薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7|
|xsii_td4_qfq|float|Y|薛斯通道II-CLOSE, HIGH, LOW, N=102, M=7|


## 机构调研表

---

接口：stk_surv  
描述：获取上市公司机构调研记录数据  
限量：单次最大获取100条数据，可循环或分页提取  
积分：用户积5000积分可使用

  
  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|股票代码|
|trade_date|str|N|调研日期|
|start_date|str|N|调研开始日期|
|end_date|str|N|调研结束日期|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|股票代码|
|name|str|Y|股票名称|
|surv_date|str|Y|调研日期|
|fund_visitors|str|Y|机构参与人员|
|rece_place|str|Y|接待地点|
|rece_mode|str|Y|接待方式|
|rece_org|str|Y|接待的公司|
|org_type|str|Y|接待公司类型|
|comp_rece|str|Y|上市公司接待人员|
|content|None|N|调研内容|

  
  

**接口用法**

```python

pro = ts.pro_api()

df = pro.stk_surv(ts_code='002223.SZ', trade_date='20211024', fields='ts_code,name,surv_date,fund_visitors,rece_place,rece_mode,rece_org')
```

**数据样例**

```
      ts_code  name  surv_date fund_visitors rece_place      rece_mode                          rece_org
1   002223.SZ  鱼跃医疗  20211024            郝淼       电话会议    特定对象调研                              宝盈基金
2   002223.SZ  鱼跃医疗  20211024           秦瑶函       电话会议    特定对象调研                           贝莱德资产管理
3   002223.SZ  鱼跃医疗  20211024            谭飞       电话会议    特定对象调研                              博远基金
4   002223.SZ  鱼跃医疗  20211024            李晗       电话会议    特定对象调研                            创金合信基金
..        ...   ...       ...           ...        ...       ...                               ...
77  002223.SZ  鱼跃医疗  20211024           李虹达       电话会议    特定对象调研                              中信建投
78  002223.SZ  鱼跃医疗  20211024           李明蔚       电话会议    特定对象调研                              中银国际
79  002223.SZ  鱼跃医疗  20211024            王俊       电话会议    特定对象调研                            重庆穿石投资
80  002223.SZ  鱼跃医疗  20211024            李扬       电话会议    特定对象调研                              朱雀基金
81  002223.SZ  鱼跃医疗  20211024           徐烨程       电话会议    特定对象调研                            逐流资产管理
```

## 券商每月荐股

---

接口：broker_recommend  
描述：获取券商月度金股，一般1日~3日内更新当月数据  
限量：单次最大1000行数据，可循环提取  
积分：积分达到2000即可调用，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|month|str|Y|月度（YYYYMM）|

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|month|str|Y|月度|
|broker|str|Y|券商|
|ts_code|str|Y|股票代码|
|name|str|Y|股票简称|

**接口示例**

```python

#获取查询月份券商金股
df = pro.broker_recommend(month='202106')
```

**数据示例**

```
             month broker    ts_code  name
0    202106   东兴证券  000066.SZ  中国长城
1    202106   东兴证券  000708.SZ  中信特钢
2    202106   东兴证券  002304.SZ  洋河股份
3    202106   东兴证券  003816.SZ  中国广核
4    202106   东兴证券  300196.SZ  长海股份
..      ...    ...        ...   ...
263  202106   长城证券  600096.SH   云天化
264  202106   长城证券  600809.SH  山西汾酒
265  202106   长城证券  603596.SH   伯特利
266  202106   长城证券  603885.SH  吉祥航空
267  202106   长城证券  605068.SH  明新旭腾
```

# 资金流向

## 个股资金流向

---

接口：moneyflow，可以通过[**数据工具**](https://tushare.pro/webclient/)调试和查看数据。  
描述：获取沪深A股票资金流向数据，分析大单小单成交情况，用于判别资金动向，数据开始于2010年。  
限量：单次最大提取6000行记录，总量不限制  
积分：用户需要至少2000积分才可以调取，基础积分有流量控制，积分越多权限越大，请自行提高积分，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

  
  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|股票代码 （股票和时间参数至少输入一个）|
|trade_date|str|N|交易日期|
|start_date|str|N|开始日期|
|end_date|str|N|结束日期|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|ts_code|str|Y|TS代码|
|trade_date|str|Y|交易日期|
|buy_sm_vol|int|Y|小单买入量（手）|
|buy_sm_amount|float|Y|小单买入金额（万元）|
|sell_sm_vol|int|Y|小单卖出量（手）|
|sell_sm_amount|float|Y|小单卖出金额（万元）|
|buy_md_vol|int|Y|中单买入量（手）|
|buy_md_amount|float|Y|中单买入金额（万元）|
|sell_md_vol|int|Y|中单卖出量（手）|
|sell_md_amount|float|Y|中单卖出金额（万元）|
|buy_lg_vol|int|Y|大单买入量（手）|
|buy_lg_amount|float|Y|大单买入金额（万元）|
|sell_lg_vol|int|Y|大单卖出量（手）|
|sell_lg_amount|float|Y|大单卖出金额（万元）|
|buy_elg_vol|int|Y|特大单买入量（手）|
|buy_elg_amount|float|Y|特大单买入金额（万元）|
|sell_elg_vol|int|Y|特大单卖出量（手）|
|sell_elg_amount|float|Y|特大单卖出金额（万元）|
|net_mf_vol|int|Y|净流入量（手）|
|net_mf_amount|float|Y|净流入额（万元）|

  

各类别统计规则如下：  
**小单**：5万以下 **中单**：5万～20万 **大单**：20万～100万 **特大单**：成交额>=100万 ，数据基于主动买卖单统计

  
  

**接口示例**

```python

pro = ts.pro_api('your token')

#获取单日全部股票数据
df = pro.moneyflow(trade_date='20190315')

#获取单个股票数据
df = pro.moneyflow(ts_code='002149.SZ', start_date='20190115', end_date='20190315')

```

  
  

**数据示例**

```
        ts_code trade_date  buy_sm_vol  buy_sm_amount  sell_sm_vol  \
0     000779.SZ   20190315       11377        1150.17        11100   
1     000933.SZ   20190315       94220        4803.22       105924   
2     002270.SZ   20190315       43979        2330.96        45893   
3     002319.SZ   20190315       21502        2952.88        17155   
4     002604.SZ   20190315       31944         607.35        58667   
5     300065.SZ   20190315       16048        2294.71        16425   
6     600062.SH   20190315       55439        7432.13        65765   
7     002735.SZ   20190315        3220         797.10         4598   
8     300196.SZ   20190315       12534        1286.02         8340   
9     300350.SZ   20190315       15346        1120.12        18853   
10    600193.SH   20190315       12183         503.73        19576   
11    002866.SZ   20190315       16932        2213.68        16037   
12    300481.SZ   20190315       21386        4275.33        21863   
13    600527.SH   20190315      115462        2975.44        79272   
14    603980.SH   20190315       13957        1924.69        11718   
15    600658.SH   20190315       71767        4826.73        69535   
16    600812.SH   20190315       26140        1247.47        34923   
17    002013.SZ   20190315      170234       12286.02       148509   
18    600789.SH   20190315      211012       21644.56       150598   
19    601636.SH   20190315       70737        3117.43        68073   
20    000807.SZ   20190315      129668        6361.06       122077   

...

     sell_sm_amount  buy_md_vol  buy_md_amount  sell_md_vol  sell_md_amount  \
0            1122.97       13012        1316.72        14812         1498.90   
1            5411.72      135976        6935.40       154023         7863.00   
2            2435.98       57679        3059.15        47279         2507.55   
3            2358.68       27245        3742.52        26708         3670.05   
4            1114.40       69897        1327.41        41108          781.19   
5            2353.34       31232        4472.05        26771         3834.95   
6            8817.75       86617       11615.40        79551        10676.99   
7            1140.61        4602        1141.61         2730          676.72   
8             855.45        9401         963.72        10478         1074.32   
9            1380.31       24224        1770.90        21588         1577.92   
10            812.58       28696        1185.17        31087         1286.11   
11           2100.70       19197        2511.62        20269         2650.56   
12           4379.14       31692        6345.72        32873         6578.36   
13           2046.54      107103        2763.00        84883         2191.24   
14           1619.33       14621        2019.41        14528         2005.69   
15           4691.29       92788        6232.80        93273         6280.13   
16           1669.97       38812        1855.78        39211         1874.05   
17          10726.22      154979       11190.69       164090        11855.76   
18          15479.08      269470       27660.18       236958        24338.36   
19           3000.73       90416        3984.68       115162         5075.50   
20           5999.66      175692        8627.77       178044         8751.08 
```

## 个股资金流向（THS）

---

接口：moneyflow_ths  
描述：获取同花顺个股资金流向数据，每日盘后更新  
限量：单次最大6000，可根据日期或股票代码循环提取数据  
积分：用户需要至少5000积分才可以调取，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

  
  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|股票代码|
|trade_date|str|N|交易日期（YYYYMMDD格式，下同）|
|start_date|str|N|开始日期|
|end_date|str|N|结束日期|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|trade_date|str|Y|交易日期|
|ts_code|str|Y|股票代码|
|name|str|Y|股票名称|
|pct_change|float|Y|涨跌幅|
|latest|float|Y|最新价|
|net_amount|float|Y|资金净流入(万元)|
|net_d5_amount|float|Y|5日主力净额(万元)|
|buy_lg_amount|float|Y|今日大单净流入额(万元)|
|buy_lg_amount_rate|float|Y|今日大单净流入占比(%)|
|buy_md_amount|float|Y|今日中单净流入额(万元)|
|buy_md_amount_rate|float|Y|今日中单净流入占比(%)|
|buy_sm_amount|float|Y|今日小单净流入额(万元)|
|buy_sm_amount_rate|float|Y|今日小单净流入占比(%)|

  
  

**接口示例**

```python

pro = ts.pro_api()

#获取单日全部股票数据
df = pro.moneyflow_ths(trade_date='20241011')

#获取单个股票数据
df = pro.moneyflow_ths(ts_code='002149.SZ', start_date='20241001', end_date='20241011')

```

```
    trade_date ts_code  name  pct_change  ...  buy_md_amount  buy_md_amount_rate  buy_sm_amount  buy_sm_amount_rate
0   20241011  002149.SZ  西部材料        2.47  ...         -589.0                5.43         -191.0                1.76
1   20241010  002149.SZ  西部材料        1.22  ...        -2732.0               15.38        -1031.0                5.81
2   20241009  002149.SZ  西部材料        7.00  ...        -1941.0                9.25        -2079.0                9.90
3   20241008  002149.SZ  西部材料        5.17  ...        -2985.0                7.93        -2507.0                6.66
```

## 个股资金流向（DC）

---

接口：moneyflow_dc  
描述：获取东方财富个股资金流向数据，每日盘后更新，数据开始于20230911  
限量：单次最大获取6000条数据，可根据日期或股票代码循环提取数据  
积分：用户需要至少5000积分才可以调取，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

  
  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|股票代码|
|trade_date|str|N|交易日期（YYYYMMDD格式，下同）|
|start_date|str|N|开始日期|
|end_date|str|N|结束日期|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|trade_date|str|Y|交易日期|
|ts_code|str|Y|股票代码|
|name|str|Y|股票名称|
|pct_change|float|Y|涨跌幅|
|close|float|Y|最新价|
|net_amount|float|Y|今日主力净流入额（万元）|
|net_amount_rate|float|Y|今日主力净流入净占比（%）|
|buy_elg_amount|float|Y|今日超大单净流入额（万元）|
|buy_elg_amount_rate|float|Y|今日超大单净流入占比（%）|
|buy_lg_amount|float|Y|今日大单净流入额（万元）|
|buy_lg_amount_rate|float|Y|今日大单净流入占比（%）|
|buy_md_amount|float|Y|今日中单净流入额（万元）|
|buy_md_amount_rate|float|Y|今日中单净流入占比（%）|
|buy_sm_amount|float|Y|今日小单净流入额（万元）|
|buy_sm_amount_rate|float|Y|今日小单净流入占比（%）|

  
  

**接口示例**

```python

pro = ts.pro_api()

#获取单日全部股票数据
df = pro.moneyflow_dc(trade_date='20241011')

#获取单个股票数据
df = pro.moneyflow_dc(ts_code='002149.SZ', start_date='20240901', end_date='20240913')

```

  
  

```
    trade_date ts_code  name  pct_change  ...  buy_md_amount  buy_md_amount_rate  buy_sm_amount  buy_sm_amount_rate
0   20240913  002149.SZ  西部材料       -1.34  ...         -12.65               -0.35         -62.43               -1.72
1   20240912  002149.SZ  西部材料        1.43  ...          13.71                0.33        -388.43               -9.25
2   20240911  002149.SZ  西部材料       -0.79  ...         -26.10               -1.68          95.69                6.15
3   20240910  002149.SZ  西部材料       -0.08  ...        -199.50               -7.26         -69.29               -2.52
4   20240909  002149.SZ  西部材料        1.12  ...          66.76                2.48        -198.12               -7.37
5   20240906  002149.SZ  西部材料       -2.49  ...        -104.57               -2.74         769.65               20.19
6   20240905  002149.SZ  西部材料       -0.70  ...        -307.62               -8.11         346.51                9.14
7   20240904  002149.SZ  西部材料       -0.92  ...         370.98                9.56         -23.25               -0.60
8   20240903  002149.SZ  西部材料        0.93  ...        -195.45               -3.87         643.41               12.75
9   20240902  002149.SZ  西部材料       -3.44  ...         195.50                2.32         988.69               11.71
```

## 同花顺概念板块资金流向（THS）

---

接口：moneyflow_cnt_ths  
描述：获取同花顺概念板块每日资金流向  
限量：单次最大可调取5000条数据，可以根据日期和代码循环提取全部数据  
积分：5000积分可以调取，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

  
  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|代码|
|trade_date|str|N|交易日期(格式：YYYYMMDD，下同)|
|start_date|str|N|开始日期|
|end_date|str|N|结束日期|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|trade_date|str|Y|交易日期|
|ts_code|str|Y|板块代码|
|name|str|Y|板块名称|
|lead_stock|str|Y|领涨股票名称|
|close_price|float|Y|最新价|
|pct_change|float|Y|行业涨跌幅|
|industry_index|float|Y|板块指数|
|company_num|int|Y|公司数量|
|pct_change_stock|float|Y|领涨股涨跌幅|
|net_buy_amount|float|Y|流入资金(亿元)|
|net_sell_amount|float|Y|流出资金(亿元)|
|net_amount|float|Y|净额(亿元)|

  
  

**接口示例**

```python

#获取当日同花顺板块资金流向
df = pro.moneyflow_cnt_ths(trade_date='20250320')
```

  
  

**数据示例**

```
     trade_date    ts_code     name lead_stock close_price pct_change industry_index  company_num pct_change_stock net_buy_amount net_sell_amount net_amount
0     20250320  885748.TI      可燃冰       海默科技        7.99       4.76        1307.56           12             4.76          21.00           19.00       1.00
1     20250320  886008.TI      减速器       大叶股份       21.22       2.60        1862.58          103             2.60         227.00          235.00      -8.00
2     20250320  885426.TI     海工装备       天海防务        6.97       2.56        2711.31           85             2.56         171.00          148.00      23.00
3     20250320  885372.TI      页岩气       海默科技        7.99       2.21        2103.88           40             2.21          53.00           42.00      10.00
4     20250320  886000.TI    一体化压铸       今飞凯达        5.57       1.78        1213.60           50             1.78          95.00           86.00       9.00
..         ...        ...      ...        ...         ...        ...            ...          ...              ...            ...             ...        ...
389   20250320  885881.TI      云办公      *ST鹏博        1.72      -1.36        1862.72           45            -1.36          54.00           63.00      -9.00
390   20250320  885947.TI  DRG/DIP       国新健康       12.82      -1.38        1092.62           23            -1.38          25.00           30.00      -5.00
391   20250320  885975.TI    电子身份证        拓尔思       24.16      -1.40        1438.42           40            -1.40          28.00           39.00     -11.00
392   20250320  885874.TI      云游戏      *ST鹏博        1.72      -1.75        1330.68           27            -1.75          67.00           91.00     -23.00
393   20250320  886091.TI     华为手机       凯格精机       37.23      -2.25        1183.33           35            -2.25          49.00           68.00     -18.00
```

## 同花顺行业资金流向（THS）

---

接口：moneyflow_ind_ths  
描述：获取同花顺行业资金流向，每日盘后更新  
限量：单次最大可调取5000条数据，可以根据日期和代码循环提取全部数据  
积分：5000积分可以调取，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

  
  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|代码|
|trade_date|str|N|交易日期(YYYYMMDD格式，下同)|
|start_date|str|N|开始日期|
|end_date|str|N|结束日期|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|trade_date|str|Y|交易日期|
|ts_code|str|Y|板块代码|
|industry|str|Y|板块名称|
|lead_stock|str|Y|领涨股票名称|
|close|float|Y|收盘指数|
|pct_change|float|Y|指数涨跌幅|
|company_num|int|Y|公司数量|
|pct_change_stock|float|Y|领涨股涨跌幅|
|close_price|float|Y|领涨股最新价|
|net_buy_amount|float|Y|流入资金(亿元)|
|net_sell_amount|float|Y|流出资金(亿元)|
|net_amount|float|Y|净额(亿元)|

  
  

**接口示例**

```python

#获取当日所有同花顺行业资金流向
df = pro.moneyflow_ind_ths(trade_date='20240927')
```

  
  

**数据示例**

```
  trade_date   ts_code industry     close  company_num net_buy_amount net_sell_amount net_amount
0    20240927  881267.TI     能源金属  15021.70           16         490.00           46.00       3.00
1    20240927  881273.TI       白酒   3251.85           20        1890.00          179.00      10.00
2    20240927  881279.TI     光伏设备   5940.19           70        1120.00           94.00      17.00
3    20240927  881157.TI       证券   1407.41           50        3680.00          319.00      49.00
4    20240927  877137.TI     软件开发   1375.49          137        2260.00          204.00      22.00
..        ...        ...      ...       ...          ...            ...             ...        ...
85   20240927  881148.TI     港口航运    901.87           37         190.00           20.00      -1.00
86   20240927  881105.TI   煤炭开采加工   2271.57           34         220.00           26.00      -4.00
87   20240927  881169.TI      贵金属   2141.46           12         240.00           32.00      -8.00
88   20240927  881149.TI   公路铁路运输   1224.59           31         210.00           29.00      -7.00
89   20240927  877035.TI       银行   1080.14           84        1190.00          159.00     -40.00

[90 rows x 8 columns]
```

## 东财概念及行业板块资金流向（DC）

---

接口：moneyflow_ind_dc  
描述：获取东方财富板块资金流向，每天盘后更新  
限量：单次最大可调取5000条数据，可以根据日期和代码循环提取全部数据  
积分：5000积分可以调取，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

  
  

**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|ts_code|str|N|代码|
|trade_date|str|N|交易日期（YYYYMMDD格式，下同）|
|start_date|str|N|开始日期|
|end_date|str|N|结束日期|
|content_type|str|N|资金类型(行业、概念、地域)|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|trade_date|str|Y|交易日期|
|content_type|str|Y|数据类型|
|ts_code|str|Y|DC板块代码（行业、概念、地域）|
|name|str|Y|板块名称|
|pct_change|float|Y|板块涨跌幅（%）|
|close|float|Y|板块最新指数|
|net_amount|float|Y|今日主力净流入 净额（元）|
|net_amount_rate|float|Y|今日主力净流入净占比%|
|buy_elg_amount|float|Y|今日超大单净流入 净额（元）|
|buy_elg_amount_rate|float|Y|今日超大单净流入 净占比%|
|buy_lg_amount|float|Y|今日大单净流入 净额（元）|
|buy_lg_amount_rate|float|Y|今日大单净流入 净占比%|
|buy_md_amount|float|Y|今日中单净流入 净额（元）|
|buy_md_amount_rate|float|Y|今日中单净流入 净占比%|
|buy_sm_amount|float|Y|今日小单净流入 净额（元）|
|buy_sm_amount_rate|float|Y|今日小单净流入 净占比%|
|buy_sm_amount_stock|str|Y|今日主力净流入最大股|
|rank|int|Y|序号|

  
  

**接口示例**

```python

#获取当日所有板块资金流向
df = pro.moneyflow_ind_dc(trade_date='20240927', fields='trade_date,name,pct_change, close, net_amount,net_amount_rate,rank')
```

  
  

**数据示例**

```
     trade_date   name    pct_change      close      net_amount net_amount_rate  rank
0    20240927  互联网服务       6.28   16883.55   3056382208.00            3.93     1
1    20240927     证券       8.23  135249.80   2875528704.00            4.64     2
2    20240927   软件开发       8.28     721.35   2733378816.00            3.18     3
3    20240927   酿酒行业       6.47   49330.63   2568183040.00            5.24     4
4    20240927     电池       8.37     731.85   1328346624.00            3.05     5
..        ...    ...        ...        ...             ...             ...   ...
81   20240927   石油行业       2.31    4654.40   -611530368.00           -9.39    82
82   20240927   汽车整车       4.05    1386.22   -629528064.00           -2.42    83
83   20240927   综合行业       3.06    7437.08   -667341600.00           -7.28    84
84   20240927   家电行业       3.95   15815.68   -670035968.00           -2.37    85
85   20240927     银行      -0.33    3401.83  -2340180224.00           -6.41    86
```

## 大盘资金流向（DC）

---

接口：moneyflow_mkt_dc  
描述：获取东方财富大盘资金流向数据，每日盘后更新  
限量：单次最大3000条，可根据日期或日期区间循环获取  
积分：120积分可试用，5000积分可正式调取，具体请参阅[积分获取办法](https://tushare.pro/document/1?doc_id=13)

  
  
**输入参数**

|名称|类型|必选|描述|
|---|---|---|---|
|trade_date|str|N|交易日期(YYYYMMDD格式，下同）|
|start_date|str|N|开始日期|
|end_date|str|N|结束日期|

  
  

**输出参数**

|名称|类型|默认显示|描述|
|---|---|---|---|
|trade_date|str|Y|交易日期|
|close_sh|float|Y|上证收盘价（点）|
|pct_change_sh|float|Y|上证涨跌幅(%)|
|close_sz|float|Y|深证收盘价（点）|
|pct_change_sz|float|Y|深证涨跌幅(%)|
|net_amount|float|Y|今日主力净流入 净额（元）|
|net_amount_rate|float|Y|今日主力净流入净占比%|
|buy_elg_amount|float|Y|今日超大单净流入 净额（元）|
|buy_elg_amount_rate|float|Y|今日超大单净流入 净占比%|
|buy_lg_amount|float|Y|今日大单净流入 净额（元）|
|buy_lg_amount_rate|float|Y|今日大单净流入 净占比%|
|buy_md_amount|float|Y|今日中单净流入 净额（元）|
|buy_md_amount_rate|float|Y|今日中单净流入 净占比%|
|buy_sm_amount|float|Y|今日小单净流入 净额（元）|
|buy_sm_amount_rate|float|Y|今日小单净流入 净占比%|

  
  

**接口示例**

```python

#获取当日所有板块资金流向
df = pro.moneyflow_mkt_dc(start_date='20240901', end_date='20240930')
```

  
  

**数据示例**

```
     trade_date close_sh ptc_change_sh  close_sz pct_change_sz   buy_elg_amount    buy_lg_amount
0    20240930  3336.50          8.06  10529.76         10.67   -6500884480.00  -29199228928.00
1    20240927  3087.53          2.89   9514.86          6.71   17175101440.00   -3564773376.00
2    20240926  3000.95          3.61   8916.65          4.44   18894807552.00   -2446319616.00
3    20240925  2896.31          1.16   8537.73          1.21   -4010342144.00  -10390331392.00
4    20240924  2863.13          4.15   8435.70          4.36   22524846080.00    5433212928.00
5    20240923  2748.92          0.44   8083.38          0.10    -926530816.00   -5776028928.00
6    20240920  2736.81          0.03   8075.14         -0.15   -4991644160.00   -6899648256.00
7    20240919  2736.02          0.69   8087.60          1.19    3472006400.00    1882220032.00
8    20240918  2717.28          0.49   7992.25          0.11   -5056087040.00   -7836610048.00
9    20240913  2704.09         -0.48   7983.55         -0.88   -5527845376.00   -9092720640.00
10   20240912  2717.12         -0.17   8054.24         -0.63   -3747197184.00   -5645509632.00
11   20240911  2721.80         -0.82   8105.38          0.39   -3585276416.00   -6461025792.00
12   20240910  2744.19          0.28   8073.83          0.13   -2726709504.00   -3818158336.00
13   20240909  2736.49         -1.06   8063.27         -0.83   -7874987776.00   -8608827904.00
14   20240906  2765.81         -0.81   8130.77         -1.44   -5892936960.00  -13908542976.00
15   20240905  2788.31          0.14   8249.66          0.28    1211718400.00   -3910650112.00
16   20240904  2784.28         -0.67   8226.24         -0.51   -7008298240.00  -11212970496.00
17   20240903  2802.98         -0.29   8268.05          1.17     263304192.00   -3680828928.00
18   20240902  2811.04         -1.10   8172.21         -2.11  -18689678336.00  -20967354368.00
```



下载数据有限制，我的积分是5000分，如果api限制单位时间下载速率，帮我同步适配。我只要沪深a股的相关数据，不用港股、北交所的。行情数据只需要日线的所有数据，分钟、tick、周线月线都不需要。
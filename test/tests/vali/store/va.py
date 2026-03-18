import os
import tushare as ts
os.environ["HTTP_PROXY"] = "http://tushare.xyz:5000"
pro = ts.pro_api('81df46dcdf60768a4bffc2242e46a47d388076f3de9d8b1e31ac568a35ec60ff')
df = pro.index_basic(**{"limit": 5}, fields=["ts_code", "name", "market", "publisher", "category", "base_date"])
print(df)
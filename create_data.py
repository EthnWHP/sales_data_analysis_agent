import pandas as pd

data = {
    "month": ["Jan", "Jan", "Jan", "Feb", "Feb", "Feb", "Mar", "Mar", "Mar"],
    "region": ["East", "West", "South", "East", "West", "South", "East", "West", "South"],
    "product": ["A", "B", "A", "B", "A", "B", "A", "B", "A"],
    "sales": [1000, 1500, 1200, 1300, 1400, 1100, 2000, 1800, 1600],
    "profit": [200, 300, 240, 260, 280, 220, 400, 360, 320],
    "quantity": [100, 150, 120, 130, 140, 110, 200, 180, 160]
}
# pd.DataFrame(data) 转换原理：
# 1. 字典 data 的键（如 "month", "region" 等）会被自动转换为 DataFrame 的列名。
# 2. 字典 data 的值（即对应的列表）会被自动转换为 DataFrame 中每一列的数据。
# 3. 列表的长度必须一致，以确保每一行的数据能够正确对齐。
df = pd.DataFrame(data)
df.to_csv("sales.csv", index=False)
print(df)

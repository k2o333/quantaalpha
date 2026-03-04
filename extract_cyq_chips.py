#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提取 cyq_chips 接口的股票代码
从 /home/quan/testdata/aspipe_v4/log/app4.log 中提取
"""

import re


def extract_cyq_chips_stocks(log_file_path, output_file_path):
    """
    从日志文件中提取 cyq_chips 接口的股票代码
    """
    stock_codes = set()

    # 正则表达式匹配 cyq_chips/xxxxxx.XX 格式的股票代码
    pattern = re.compile(r"cyq_chips/([0-9]{6}\.[A-Z]{2})")

    with open(log_file_path, "r", encoding="utf-8") as f:
        for line in f:
            matches = pattern.findall(line)
            for match in matches:
                stock_codes.add(match)

    # 排序并保存
    sorted_stocks = sorted(stock_codes)

    with open(output_file_path, "w", encoding="utf-8") as f:
        for stock in sorted_stocks:
            f.write(f"{stock}\n")

    return len(sorted_stocks)


if __name__ == "__main__":
    log_file = "/home/quan/testdata/aspipe_v4/log/app4.log"
    output_file = "/home/quan/testdata/aspipe_v4/p/2026-3-2/cyq_chips_stocks.txt"

    count = extract_cyq_chips_stocks(log_file, output_file)
    print(f"提取完成！共找到 {count} 个股票代码")
    print(f"结果已保存到: {output_file}")

#!/usr/bin/env python3
"""
清理历史下载标记文件的独立脚本
"""
import json
import os
from pathlib import Path


def remove_historical_download_markers():
    """移除所有历史下载标记文件"""
    # 确定缓存目录路径 (匹配 CoverageManager 中的路径逻辑)
    script_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/cache')
    cache_dir = script_dir
    marker_path = cache_dir / 'historical_download_marker.json'

    if marker_path.exists():
        try:
            # 读取当前标记文件
            with open(marker_path, 'r', encoding='utf-8') as f:
                markers = json.load(f)

            print(f"发现历史下载标记文件，包含 {len(markers)} 个接口的标记:")
            for interface in markers:
                print(f"  - {interface}")

            # 删除文件
            marker_path.unlink()
            print(f"已删除历史下载标记文件: {marker_path}")
            return True

        except Exception as e:
            print(f"删除历史下载标记文件失败: {e}")
            return False
    else:
        print("未找到历史下载标记文件")
        return False


if __name__ == "__main__":
    success = remove_historical_download_markers()
    if success:
        print("清理完成")
    else:
        print("清理失败或无需清理")
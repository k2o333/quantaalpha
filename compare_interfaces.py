#!/usr/bin/env python3

# 读取两个接口列表文件
with open('/tmp/download_interfaces.txt', 'r') as f:
    download_interfaces = set(line.strip() for line in f.readlines())

with open('/tmp/tu_interfaces.txt', 'r') as f:
    tu_interfaces = set(line.strip() for line in f.readlines())

print("date_param_download_interfaces.txt中有，但tu.md中没有的接口：")
diff1 = download_interfaces - tu_interfaces
for interface in sorted(diff1):
    print(f"- {interface}")

print("\ntu.md中有，但date_param_download_interfaces.txt中没有的接口：")
diff2 = tu_interfaces - download_interfaces
for interface in sorted(diff2):
    print(f"- {interface}")

print(f"\n总结：")
print(f"- date_param_download_interfaces.txt中的接口数量: {len(download_interfaces)}")
print(f"- tu.md中的接口数量: {len(tu_interfaces)}")
print(f"- 两个文件中都有的接口数量: {len(download_interfaces & tu_interfaces)}")
print(f"- 仅在date_param_download_interfaces.txt中的接口数量: {len(diff1)}")
print(f"- 仅在tu.md中的接口数量: {len(diff2)}")
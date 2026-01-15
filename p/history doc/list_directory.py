import os

# 查看testdata目录结构
testdata_path = '/home/quan/testdata'
aspipe_path = '/home/quan/testdata/aspipe_v4'
app_path = '/home/quan/testdata/aspipe_v4/app'

print("=== testdata目录内容 ===")
if os.path.exists(testdata_path):
    print(os.listdir(testdata_path))
else:
    print("testdata目录不存在")

print("\n=== aspipe_v4目录内容 ===")
if os.path.exists(aspipe_path):
    print(os.listdir(aspipe_path))
else:
    print("aspipe_v4目录不存在")

print("\n=== app目录内容 ===")
if os.path.exists(app_path):
    print(os.listdir(app_path))
else:
    print("app目录不存在")

# 检查关键文件是否存在
print("\n=== 关键文件检查 ===")
files_to_check = [
    '/home/quan/testdata/aspipe_v4/p/2025-12-26/detailed_test_plan.md',
    '/home/quan/testdata/aspipe_v4/p/2025-12-26/pro_bar_cache_duplicate_analysis.md'
]

for file_path in files_to_check:
    if os.path.exists(file_path):
        print(f"✓ {file_path} 存在")
        print(f"  文件大小: {os.path.getsize(file_path)} bytes")
    else:
        print(f"✗ {file_path} 不存在")
"""完整工作流测试脚本"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

# 测试用的MinIO URLs（请替换为实际的URL）
TEST_MINIO_URLS = [
    "http://43.139.19.144:9000/gauz-documents/documents/test1.md",
    "http://43.139.19.144:9000/gauz-documents/documents/test2.md",
]

PROJECT_ID = "test202511241125"


def print_section(title):
    """打印分隔线"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_step1_batch_upload():
    """步骤1: 批量上传文档到知识库"""
    print_section("步骤1: 批量上传文档到知识库")
    
    print(f"上传 {len(TEST_MINIO_URLS)} 个文档...")
    
    response = requests.post(f"{BASE_URL}/batch-upload-to-kb", json={
        "minio_urls": TEST_MINIO_URLS,
        "project_id": PROJECT_ID,
        "enable_vlm": False
    }, timeout=120)
    
    result = response.json()
    
    if result.get("success"):
        print(f"✓ 上传成功: {result['success_count']}/{result['total']}")
    else:
        print(f"✗ 上传失败: {result.get('failed_count', 0)} 个失败")
    
    print("\n等待知识库索引...")
    time.sleep(5)  # 等待索引完成
    
    return result.get("success", False)


def test_step2_consistency_check():
    """步骤2: 执行一致性检查"""
    print_section("步骤2: 文档一致性检查")
    
    # 模拟用户修改第一个文档
    print(f"当前编辑文档: {TEST_MINIO_URLS[0]}")
    print("修改点: 早季分类")
    print("修改要求: 将LSTM模型改为Transformer模型\n")
    
    response = requests.post(f"{BASE_URL}/check-consistency", json={
        "modification_point": "早季分类",
        "modification_request": "将所有LSTM模型改为Transformer模型，包括模型描述、参数配置和实验结果",
        "project_id": PROJECT_ID,
        "current_file": TEST_MINIO_URLS[0],
        "current_file_content": "# 示例文档\n本研究使用LSTM模型进行早季作物分类...",
        "current_modification": "# 示例文档\n本研究使用Transformer模型进行早季作物分类...",
        "top_k": 10
    }, timeout=120)
    
    result = response.json()
    
    if not result.get("success"):
        print(f"✗ 一致性检查失败: {result.get('message')}")
        return False
    
    print("✓ 一致性检查成功!\n")
    
    # 显示结果
    print(f"找到相关文档: {result.get('total_files', 0)} 个")
    
    analysis = result.get("consistency_analysis", {})
    print(f"\nAI分析:")
    print(f"  修改类型: {analysis.get('modification_type', '未知')}")
    print(f"  全局一致性: {'需要' if analysis.get('global_consistency_required') else '不需要'}")
    print(f"  说明: {analysis.get('consistency_analysis', '无')}")
    
    modifications = result.get("modifications", [])
    print(f"\n需要修改的文档: {len(modifications)} 个")
    
    for i, mod in enumerate(modifications, 1):
        print(f"\n[{i}] {mod['file_path'].split('/')[-1]}")
        print(f"    {mod['diff_summary']}")
        print(f"    原长度: {mod['original_length']} → 新长度: {mod['modified_length']}")
    
    return True


def main():
    """主测试流程"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║  文档一致性检查系统 - 完整工作流测试" + " " * 38 + "║")
    print("╚" + "=" * 78 + "╝")
    
    # 检查服务状态
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print("✗ 服务未运行")
            return
        print("✓ 服务运行正常\n")
    except:
        print("✗ 无法连接到服务，请先运行: python run.py")
        return
    
    # 注意事项
    print("注意：运行此测试前，请确保：")
    print("1. 知识库服务运行在 localhost:8001")
    print("2. RAG服务运行在 localhost:1234")
    print("3. 测试的MinIO URLs有效且可访问")
    print("4. 修改脚本中的 TEST_MINIO_URLS 为实际URL\n")
    
    choice = input("是否继续测试? (y/n): ")
    if choice.lower() != 'y':
        print("测试已取消")
        return
    
    try:
        # 步骤1: 上传文档
        if not test_step1_batch_upload():
            print("\n✗ 上传步骤失败，测试终止")
            return
        
        # 步骤2: 一致性检查
        test_step2_consistency_check()
        
        print_section("测试完成")
        print("✓ 所有测试步骤执行完成")
        print("\n提示: 在实际使用中，可以通过前端界面进行操作")
        print("访问: http://localhost:8000 → '一致性检查' 标签页\n")
        
    except requests.exceptions.Timeout:
        print("\n✗ 请求超时（可能是知识库处理较慢）")
    except Exception as e:
        print(f"\n✗ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


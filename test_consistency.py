"""文档一致性检查测试脚本"""
import requests
import json

BASE_URL = "http://localhost:8000"


def test_consistency_check():
    """测试文档一致性检查"""
    print("=" * 80)
    print("文档一致性检查测试")
    print("=" * 80)
    print()
    
    # 模拟场景：用户在系统中生成了几篇论文，现在要修改其中一篇的"LSTM"改成"Transformer"
    request_data = {
        "modification_point": "早季分类",
        "modification_request": "将LSTM模型改为Transformer模型，包括模型描述、参数配置和实验结果",
        "project_id": "test202511241125",  # 替换为你的项目ID
        "current_file": "论文1.md",
        "current_file_content": """
# 1. Introduction
本研究采用LSTM模型进行早季作物分类，LSTM能够有效捕捉时序特征...

# 2. Methodology  
我们使用3层LSTM网络，每层128个隐藏单元...

# 3. Results
LSTM模型在测试集上的准确率达到92.5%...
        """.strip(),
        "current_modification": """
# 1. Introduction
本研究采用Transformer模型进行早季作物分类，Transformer能够通过自注意力机制有效捕捉时序特征...

# 2. Methodology
我们使用标准的Transformer编码器，包含6层，每层512维...

# 3. Results  
Transformer模型在测试集上的准确率达到94.8%...
        """.strip(),
        "top_k": 10
    }
    
    print("请求参数:")
    print(json.dumps({
        "modification_point": request_data["modification_point"],
        "project_id": request_data["project_id"],
        "current_file": request_data["current_file"],
        "top_k": request_data["top_k"]
    }, ensure_ascii=False, indent=2))
    print()
    
    # 发送请求
    try:
        response = requests.post(
            f"{BASE_URL}/check-consistency",
            json=request_data,
            timeout=120  # 2分钟超时
        )
        
        if response.status_code != 200:
            print(f"✗ 请求失败: HTTP {response.status_code}")
            print(response.text)
            return
        
        result = response.json()
        
        if not result.get("success"):
            print(f"✗ 检查失败: {result.get('message')}")
            return
        
        # 显示结果
        print("✓ 一致性检查成功!")
        print()
        
        print("=" * 80)
        print("1. RAG召回的相关文档")
        print("=" * 80)
        related_files = result.get("related_files", {})
        print(f"找到 {result.get('total_files', 0)} 个相关文档:")
        for file_path, chunks in related_files.items():
            print(f"\n  📄 {file_path}")
            print(f"     召回 {len(chunks)} 个相关片段")
            if chunks:
                print(f"     最高得分: {chunks[0].get('score', 0):.3f}")
                print(f"     预览: {chunks[0].get('content', '')[:100]}...")
        print()
        
        print("=" * 80)
        print("2. AI一致性分析")
        print("=" * 80)
        analysis = result.get("consistency_analysis", {})
        print(json.dumps(analysis, ensure_ascii=False, indent=2))
        print()
        
        print("=" * 80)
        print("3. 修改建议（Diff对比）")
        print("=" * 80)
        modifications = result.get("modifications", [])
        print(f"需要修改 {len(modifications)} 个文档:\n")
        
        for i, mod in enumerate(modifications, 1):
            print(f"[{i}] 文件: {mod['file_path']}")
            print(f"    {mod['diff_summary']}")
            print()
            print(f"    原文预览 ({mod['original_length']} 字符):")
            print(f"    {mod['original_content'][:200]}...")
            print()
            print(f"    修改后预览 ({mod['modified_length']} 字符):")
            print(f"    {mod['modified_content'][:200]}...")
            print()
            print("-" * 80)
            print()
        
        print("=" * 80)
        print("测试完成!")
        print("=" * 80)
        
    except requests.exceptions.Timeout:
        print("✗ 请求超时（可能是文档太多或网络较慢）")
    except requests.exceptions.ConnectionError:
        print("✗ 无法连接到服务，请确保服务已启动")
    except Exception as e:
        print(f"✗ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


def main():
    print()
    print("╔" + "=" * 78 + "╗")
    print("║  文档一致性检查系统 - 测试脚本" + " " * 44 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    # 检查服务状态
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print("✗ 服务未正常运行")
            return
        print("✓ 服务运行正常")
        print()
    except:
        print("✗ 无法连接到服务，请先运行: python run.py")
        return
    
    # 运行测试
    test_consistency_check()


if __name__ == "__main__":
    main()


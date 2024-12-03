from nlm_client import NotebookLMClient
import os
from dotenv import load_dotenv
import json

def test_nlm_client():
    load_dotenv()
    
    # 测试场景1：模拟正常的播客内容
    test_podcast_content = {
        "title": "Test Podcast",
        "description": "Test Description",
        "paper_link": "https://arxiv.org/abs/2106.09685",
        "prompt_text": "This is a test prompt for audio generation."
    }
    
    print("\n=== 测试场景1：正常内容 ===")
    test_with_content(test_podcast_content)
    
    # 测试场景2：空的提示文本
    test_podcast_content_empty_text = {
        "title": "Test Podcast",
        "description": "Test Description",
        "paper_link": "https://arxiv.org/abs/2106.09685",
        "prompt_text": ""
    }
    
    print("\n=== 测试场景2：空的提示文本 ===")
    test_with_content(test_podcast_content_empty_text)
    
    # 测试场景3：空的论文链接
    test_podcast_content_empty_link = {
        "title": "Test Podcast",
        "description": "Test Description",
        "paper_link": "",
        "prompt_text": "This is a test prompt"
    }
    
    print("\n=== 测试场景3：空的论文链接 ===")
    test_with_content(test_podcast_content_empty_link)

def test_with_content(content_data):
    print(f"测试内容: {json.dumps(content_data, indent=2)}")
    
    resources = [
        {"content": content_data.get('paper_link', ''), "type": "website"}
    ]
    text = content_data.get('prompt_text', '')
    
    print(f"Resources: {resources}")
    print(f"Text: {text}")
    
    # 验证内容
    is_valid = True
    if not text.strip():
        print("❌ 错误: 生成的文本内容为空")
        is_valid = False
    
    if not resources[0]["content"].strip():
        print("❌ 错误: 论文链接为空")
        is_valid = False
    
    if is_valid:
        try:
            client = NotebookLMClient(
                os.getenv("NotebookLM_API_KEY"),
                webhook_url="http://localhost:5000/webhook"
            )
            
            request_id = client.send_content(resources, text)
            print(f"Request ID: {request_id}")
            
            if request_id:
                print("✅ 请求发送成功")
                
                # 检查状态
                status = client.check_status(request_id)
                print(f"Status: {status}")
            else:
                print("❌ 请求发送失败")
                
        except Exception as e:
            print(f"❌ 错误: {str(e)}")
    else:
        print("❌ 验证失败，未发送请求")

if __name__ == "__main__":
    test_nlm_client() 
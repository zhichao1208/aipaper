from nlm_client import NotebookLMClient
from dotenv import load_dotenv
import os
import time
import json

def test_audio_generation():
    # 加载环境变量
    load_dotenv()
    
    # 测试数据
    test_content = {
        "title": "Test Podcast",
        "description": "Test Description",
        "paper_link": "https://arxiv.org/abs/2106.09685",
        "prompt_text": "Let's discuss this innovative approach to AI research."
    }
    
    print("\n=== 开始音频生成测试 ===")
    
    try:
        # 初始化客户端
        client = NotebookLMClient(
            api_key=os.getenv("NotebookLM_API_KEY"),
            webhook_url="http://localhost:5000/webhook"
        )
        
        # 准备请求数据
        resources = [
            {"content": test_content["paper_link"], "type": "website"}
        ]
        text = test_content["prompt_text"]
        
        print("\n1. 发送音频生成请求...")
        request_id = client.send_content(resources, text)
        
        if not request_id:
            print("❌ 发送请求失败")
            return
            
        print(f"✓ 请求发送成功，Request ID: {request_id}")
        
        # 检查状态
        print("\n2. 开始检查状态...")
        max_checks = 30
        check_count = 0
        
        while check_count < max_checks:
            status_data = client.check_status(request_id)
            
            if status_data:
                status = status_data.get("status", 0)
                print(f"\n当前状态: {status}%")
                
                if status_data.get("error_message"):
                    print(f"❌ 错误: {status_data['error_message']}")
                    break
                    
                if status_data.get("audio_url"):
                    print(f"✓ 音频生成成功！")
                    print(f"音频 URL: {status_data['audio_url']}")
                    break
                    
                if status == 100:
                    print("✓ 处理完成")
                    break
            else:
                print(".", end="", flush=True)
            
            check_count += 1
            time.sleep(20)  # 每20秒检查一次
        
        if check_count >= max_checks:
            print("\n❌ 超时：状态检查次数超过限制")
            
    except Exception as e:
        print(f"\n❌ 测试过程中出错: {str(e)}")

if __name__ == "__main__":
    test_audio_generation() 
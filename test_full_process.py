from nlm_client import NotebookLMClient
from audio_handler import AudioHandler
from podbean_uploader import PodbeanUploader
from dotenv import load_dotenv
import os
import time
import json
import argparse

def test_full_process(request_id=None):
    """
    测试音频生成和播客发布流程
    Args:
        request_id: 可选，指定要检查的请求ID。如果不提供，将发送新请求。
    """
    # 加载环境变量
    load_dotenv()
    
    # 测试内容
    test_content = {
        "title": "Unleashing Mathematical Potential: The MC-NEST Revolution",
        "description": """Explore the groundbreaking MC-NEST algorithm, elevating mathematical reasoning in large language models. Combining Monte Carlo strategies with Nash Equilibrium and self-refinement, MC-NEST tackles complex multi-step problems. Discover how this approach improves decision-making and sets a new standard for AI in mathematics.**Paper Details:**   - **Title:** [MC-NEST -- Enhancing Mathematical Reasoning in Large Language Models with a Monte Carlo Nash Equilibrium Self-Refine Tree](https://arxiv.org/abs/2411.15645)   - **Published Date:** November 2024   - **Authors:** Gollam Rabby, Farhana Keya, Parvez Zamil, Sören Auer""",
        "paper_link": "https://arxiv.org/abs/2411.15645",
        "prompt_text": "Explore the transformative MC-NEST method and its impact on AI's mathematical capabilities!"
    }
    # 临时文件路径
    temp_wav = "temp_audio.wav"
    output_mp3 = "podcast_audio.mp3"
    
    try:
        print("\n=== 开始测试完整流程 ===")
        
        # 1. 初始化 NotebookLM 客户端
        print("\n1. 初始化 NotebookLM 客户端...")
        client = NotebookLMClient(
            os.getenv("NotebookLM_API_KEY"),
            webhook_url="http://localhost:5000/webhook"
        )
        
        # 2. 获取或发送请求
        if request_id:
            print(f"\n2. 使用指定的请求ID: {request_id}")
        else:
            print("\n2. 发送新的音频生成请求...")
            resources = [
                {"content": test_content["paper_link"], "type": "website"}
            ]
            text = test_content["prompt_text"]
            
            request_id = client.send_content(resources, text)
            if not request_id:
                raise Exception("发送请求失败")
                
            print(f"✓ 请求已发送，Request ID: {request_id}")
        
        # 3. 检查处理状态
        print("\n3. 开始检查处理状态...")
        max_checks = 20  # 最多检查10分钟 (20次 * 30秒)
        check_count = 0
        audio_url = None
        
        while check_count < max_checks:
            check_count += 1
            current_time = time.strftime("%H:%M:%S")
            
            print(f"\n检查 #{check_count} - {current_time}")
            status_data = client.check_status(request_id)
            
            if status_data:
                status = status_data.get("status", 0)
                print(f"当前状态: {status}%")
                print("\n原始状态返回:")
                print(json.dumps(status_data, indent=2, ensure_ascii=False))
                print(request_id)

                
                if status_data.get("audio_url"):
                    audio_url = status_data["audio_url"]
                    print("✓ 音频生成成功！")
                    break
                
                if status_data.get("error_message"):
                    print(f"⚠️ 收到错误信息: {status_data['error_message']}")
                    if status_data['error_message'] != "Error. Reported automatically.":
                        raise Exception(f"处理出错: {status_data['error_message']}")
                    else:
                        print("继续等待状态更新...")
            
            time.sleep(30)  # 每30秒检查一次
        
        if not audio_url:
            if check_count >= max_checks:
                raise Exception("检查超时：已达到最大检查次数（10分钟）")
            else:
                raise Exception("音频生成失败")
        
        # 4. 下载音频文件
        print("\n4. 下载音频文件...")
        audio_handler = AudioHandler()
        if not audio_handler.download_audio(audio_url, temp_wav):
            raise Exception("下载音频文件失败")
        
        # 5. 转换音频格式
        print("\n5. 转换音频格式...")
        if not audio_handler.convert_wav_to_mp3(temp_wav, output_mp3):
            raise Exception("音频格式转换失败")
        
        # 6. 上传到 Podbean
        print("\n6. 上传到 Podbean...")
        podbean_client = PodbeanUploader(
            os.getenv("PODBEAN_CLIENT_ID"),
            os.getenv("PODBEAN_CLIENT_SECRET")
        )
        
        # 获取上传授权
        upload_auth = podbean_client.authorize_file_upload(
            "podcast_audio.mp3",
            output_mp3
        )
        
        if not upload_auth:
            raise Exception("获取 Podbean 上传授权失败")
        
        # 上传文件
        if podbean_client.upload_file_to_presigned_url(
            upload_auth["presigned_url"],
            output_mp3
        ):
            print("✓ 文件上传成功")
            
            # 发布播客
            description = test_content["description"][:490]  # 限制描述内容长度为500字符
            print(f"\n描述内容长度: {len(description)}/500 字符")
            
            episode_data = podbean_client.publish_episode(
                title=test_content["title"],
                content=description,
                file_key=upload_auth["file_key"]
            )
            
            if episode_data:
                print("\n✨ 播客发布成功！")
                print(f"播客链接: {episode_data.get('episode_url')}")
            else:
                print("❌ 播客发布失败")
        else:
            print("❌ 文件上传失败")
        
    except Exception as e:
        print(f"\n❌ 测试过程中出错: {str(e)}")
        
    finally:
        # 清理临时文件
        print("\n7. 清理临时文件...")
        for temp_file in [temp_wav, output_mp3]:
            if os.path.exists(temp_file):
                os.remove(temp_file)
                print(f"已删除: {temp_file}")

if __name__ == "__main__":
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='测试音频生成和播客发布流程')
    parser.add_argument('--request-id', type=str, help='指定要检查的请求ID')
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 运行测试
    test_full_process(request_id=args.request_id) 
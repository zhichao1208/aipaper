import json
import time
import os
from dotenv import load_dotenv
from nlm_client import NotebookLMClient
from podbean_uploader import PodbeanUploader
from webhook_server import start_webhook_server
from cloud_storage import CloudStorage
import requests
import threading

def check_status_periodically(nlm_client, request_id, stop_event, status_callback=None):
    """定期检查处理状态"""
    while not stop_event.is_set():
        try:
            status_data = nlm_client.check_status(request_id)
            if status_data:
                print("\n状态检查结果:")
                print(f"状态: {status_data.get('status')}")
                print(f"更新时间: {status_data.get('updated_on')}")
                if status_data.get('audio_url'):
                    print(f"音频 URL: {status_data.get('audio_url')}")
                    if status_callback:
                        status_callback(status_data)
                    break
                if status_data.get('error_message'):
                    print(f"错误信息: {status_data.get('error_message')}")
        except Exception as e:
            print(f"状态检查出错: {str(e)}")
        time.sleep(20)  # 固定20秒的检查间隔

def wait_for_webhook_update(max_wait_time=600):  # 增加到10分钟
    """等待并获取 webhook 更新"""
    start_time = time.time()
    while (time.time() - start_time) < max_wait_time:
        try:
            response = requests.get('http://localhost:5000/status')
            if response.status_code == 200:
                return response.json()
        except:
            pass
        time.sleep(5)
    return None

def test_workflow():
    # 加载环境变量
    load_dotenv()
    
    # 验证必要的环境变量
    required_env_vars = [
        'NotebookLM_API_KEY',
        'PODBEAN_CLIENT_ID',
        'PODBEAN_CLIENT_SECRET',
        'CLOUDINARY_CLOUD_NAME',
        'CLOUDINARY_API_KEY',
        'CLOUDINARY_API_SECRET'
    ]
    
    for var in required_env_vars:
        if not os.getenv(var):
            print(f"错误：未找到环境变量 {var}")
            return
    
    # 启动 webhook 服务器
    print("启动 webhook 服务器...")
    webhook_thread = start_webhook_server()
    
    # 初始化各个客户端
    nlm_client = NotebookLMClient(
        os.getenv('NotebookLM_API_KEY'),
        webhook_url="http://localhost:5000/webhook"
    )
    
    podbean_client = PodbeanUploader(
        os.getenv('PODBEAN_CLIENT_ID'),
        os.getenv('PODBEAN_CLIENT_SECRET')
    )
    
    cloud_storage = CloudStorage(
        os.getenv('CLOUDINARY_CLOUD_NAME'),
        os.getenv('CLOUDINARY_API_KEY'),
        os.getenv('CLOUDINARY_API_SECRET')
    )
    
    # 测试数据
    test_content = {
        "raw": '''{
            "title": "Navigating the AI Frontier: Insights from Leading Experts",
            "description": "Join us as we engage in a compelling dialogue about the future of AI, drawing insights from thousands of AI experts. Explore predictions, risks, and transformative opportunities in this evolving field. This enlightening discussion will shape your understanding of AI's impact on society. Paper Title: Thousands of AI Authors on the Future of AI; Paper Link: http://arxiv.org/abs/2401.02843; Publish Date: January 2024; Authors: Katja Grace et al.",
            "paper_link": "http://arxiv.org/abs/2401.02843",
            "prompt_text": "Welcome to today's episode where we decode the future of AI with insights from the leading voices in the field. This enlightening discussion promises to broaden your perspective on the potential paths AI could take!"
        }'''
    }
    
    try:
        # 1. 发送内容到 NLM
        print("\n1. 发送内容到 NLM...")
        
        # 首先解析外层的raw字段
        if isinstance(test_content, str):
            content_data = json.loads(test_content)
        elif isinstance(test_content, dict) and 'raw' in test_content:
            content_data = json.loads(test_content['raw'])
        else:
            content_data = test_content
                
        print("解析后的内容:")
        print(json.dumps(content_data, indent=2, ensure_ascii=False))
        
        resources = [
            {"content": content_data['paper_link'], "type": "website"}
        ]
        text = content_data['prompt_text']
        
        request_id = nlm_client.send_content(resources, text)
        if not request_id:
            print("发送内容失败")
            return
        print(f"发送成功！Request ID: {request_id}")
        
        # 用于在状态检查中存储音频 URL
        audio_url_from_status = {'url': None}
        def status_callback(status_data):
            if status_data.get('audio_url'):
                audio_url_from_status['url'] = status_data.get('audio_url')
        
        # 启动定期状态检查
        stop_status_check = threading.Event()
        status_check_thread = threading.Thread(
            target=check_status_periodically,
            args=(nlm_client, request_id, stop_status_check, status_callback)
        )
        status_check_thread.daemon = True
        status_check_thread.start()
        
        # 2. 等待 webhook 通知或状态检查结果
        print("\n2. 等待处理完成...")
        webhook_data = wait_for_webhook_update()
        
        # 停止状态检查
        stop_status_check.set()
        status_check_thread.join(timeout=1)
        
        # 使用 webhook 数据或状态检查数据
        if webhook_data:
            print("收到 webhook 通知:")
            print(json.dumps(webhook_data, indent=2, ensure_ascii=False))
            audio_url = webhook_data.get('audio_url')
        elif audio_url_from_status['url']:
            print("从状态检查获取到音频 URL")
            audio_url = audio_url_from_status['url']
        else:
            print("未能获取音频 URL")
            return
        
        # 3. 处理音频
        if not audio_url:
            print("未收到音频 URL")
            return
        
        # 4. 下载并上传到 Cloudinary
        print("\n3. 处理音频文件...")
        temp_audio = "temp_audio.wav"
        if cloud_storage.download_audio(audio_url, temp_audio):
            upload_result = cloud_storage.upload_audio(temp_audio)
            if upload_result["success"]:
                print("音频已上传到 Cloudinary")
                cloudinary_url = upload_result["url"]
                
                # 5. 上传到 Podbean
                print("\n4. 上传到 Podbean...")
                podbean_response = podbean_client.authorize_file_upload(
                    "podcast_audio.mp3",
                    temp_audio
                )
                
                if podbean_response:
                    presigned_url = podbean_response['presigned_url']
                    upload_success = podbean_client.upload_file_to_presigned_url(
                        presigned_url,
                        temp_audio
                    )
                    
                    if upload_success:
                        print("音频已成功上传到 Podbean！")
                        
                        # 发布播客
                        episode_data = podbean_client.publish_episode(
                            title=content_data['title'],
                            content=content_data['description'],
                            file_key=podbean_response.get('file_key')
                        )
                        
                        if episode_data:
                            print("播客已发布！")
                            print(f"播客链接: {episode_data.get('episode_url')}")
                        else:
                            print("发布播客失败")
                    else:
                        print("上传到 Podbean 失败")
                else:
                    print("获取 Podbean 上传授权失败")
                
                # 清理临时文件
                if os.path.exists(temp_audio):
                    os.remove(temp_audio)
            else:
                print("上传到 Cloudinary 失败")
        else:
            print("下载音频失败")
    
    except Exception as e:
        print(f"测试过程中出错: {str(e)}")
        # 确保停止状态检查线程
        if 'stop_status_check' in locals():
            stop_status_check.set()
    
    print("\n测试完成！")

if __name__ == "__main__":
    test_workflow() 
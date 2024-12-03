__import__('pysqlite3') # This is a workaround to fix the error "sqlite3 module is not found" on live streamlit.
import sys 
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3') # This is a workaround to fix the error "sqlite3 module is not found" on live streamlit.

import streamlit as st
from nlm_client import NotebookLMClient
from audio_handler import AudioHandler
from podbean_uploader import PodbeanUploader
from aipaper_agents import NewsroomCrew
import openai
import requests  # 添加  requests 库
from aipaper_crew import AIPaperCrew, PapersList, ChosenPaper, PodcastContent
import json
from cloud_storage import CloudStorage
import os

# 初始化 OpenAI API
openai.api_key = st.secrets["OPENAI_API_KEY"]
openai_model_name = st.secrets["OPENAI_MODEL_NAME"]  # 获取 OpenAI 模型名称
exa_api_key = st.secrets["EXA_API_KEY"]  # 获取 EXA API 密钥
serper_api_key = st.secrets["SERPER_API_KEY"]  # 获取 Serper API 密钥

# 初始化 Cloudinary
cloud_storage = CloudStorage(
    cloud_name=st.secrets["cloudinary_cloud_name"],
    api_key=st.secrets["cloudinary_api_key"],
    api_secret=st.secrets["cloudinary_api_secret"]
)

# 初始化
st.title("AI Paper Podcast Generator")

# 用户输入
topic = st.text_input("请输入主题:", "AI music")

# 创建实例
client = NotebookLMClient(st.secrets["NotebookLM_API_KEY"], webhook_url="YOUR_WEBHOOK_URL")
audio_handler = AudioHandler()
podbean_uploader = PodbeanUploader(st.secrets["podbean_client_id"], st.secrets["podbean_client_secret"])

inputs = {
        "topic": f"{topic}"
}

# 步骤 1: 查找论文
if st.button("查找相关论文"):
    st.write("正在查找相关论文...")
    
    # 第一步：创建 crew 实例
    find_papers_crew = AIPaperCrew().find_papers_crew()
    
    # 第二步：调用 kickoff 方法
    try:
        paper_result = find_papers_crew.kickoff(inputs=inputs)  # 尝试调用 kickoff 方法
        st.write("paper_result:", paper_result)  # 调试信息
        
        # 检查 paper_result 是否有内容
        if paper_result:  # 确保 paper_result 不为空
            st.session_state.papers = paper_result  # 将查找结果存储到会话状态
            st.success("找到相关论文！")
            st.write("相关论文列表:")
            st.markdown(paper_result)  # 显示论文标题
        else:
            st.error("未找到相关论文。")
    except Exception as e:
        st.error(f"调用 kickoff 方法时发生错误: {e}")  # 捕获并显示错误信息

# 步骤 3: 生成播客内容
if st.button("生成播客内容"):
    st.write("正在生成播客内容...")

    # 检查 paper_result 是否已定义
    if 'papers' in st.session_state:
        paper_result = st.session_state.papers  # 确保从会话状态中获取 paper_result
        podcast_inputs = {
            "papers_list": paper_result  # 使用Markdown格式的论文列表
        }

        # 第一步：创建生成播客内容的 crew 实例

        generate_podcast_crew = AIPaperCrew().generate_podcast_content_crew()
        
        # 第二步：调用 kickoff 方法
        generate_podcast_content = generate_podcast_crew.kickoff(inputs=podcast_inputs)  # 使用之前存储的论文列表
        st.write("generate_podcast_content:", generate_podcast_content)  # 调试信息
        # 检查结果
        if generate_podcast_content:
            st.session_state.podcast_content = generate_podcast_content  # 将生成内容存储到会话状态
            st.success("播客内容生成成功！")
            st.write(st.session_state.podcast_content)
        else:
            st.error("生成播客内容失败。")
    else:
        st.error("未找到相关论文，无法生成播客内容。")

# 步骤 4: 发送内容到 NLM
if 'podcast_content' in st.session_state and st.button("发送内容到 NLM"):
    resources = [
        {"content": st.session_state.podcast_content['paper_link'], "type": "website"},
    ]
    text = st.session_state.podcast_content['prompt']
    request_id = client.send_content(resources, text)

    if request_id:
        st.success("内容已发送到 NLM，您将通过 Webhook 接收状态更新。")
    else:
        st.error("发送内容失败。")

# 步骤 5: 处理 NLM 状态更新
if st.button("检查 NLM 状态"):
    status_data = client.check_status(request_id)

    if status_data:
        st.write("状态更新:")
        st.write("状态:", status_data.get("status"))
        st.write("音频 URL:", status_data.get("audio_url"))

        audio_url = status_data.get("audio_url")
        if audio_url:
            st.write("正在下载音频...")
            temp_wav_path = "temp_audio.wav"
            temp_mp3_path = "temp_audio.mp3"
            
            # 下载音频
            if cloud_storage.download_audio(audio_url, temp_wav_path):
                # 转换音频
                audio_handler.convert_wav_to_mp3(temp_wav_path, temp_mp3_path)
                
                # 上传到 Cloudinary
                upload_result = cloud_storage.upload_audio(temp_mp3_path)
                if upload_result["success"]:
                    st.session_state.audio_url = upload_result["url"]
                    st.session_state.audio_public_id = upload_result["public_id"]
                    st.success("音频处理完成并上传到云存储！")
                    
                    # 清理临时文件
                    os.remove(temp_wav_path)
                    os.remove(temp_mp3_path)
                else:
                    st.error("上传到云存储失败。")
            else:
                st.error("下载音频失败。")

# 步骤 6: 上传到 Podbean
if 'audio_url' in st.session_state and st.button("发布到 Podbean"):
    # 使用云存储的 URL
    podbean_response = podbean_uploader.authorize_file_upload(
        "podcast_audio.mp3",
        st.session_state.audio_url
    )
    if podbean_response:
        presigned_url = podbean_response['presigned_url']
        # 从云存储下载并上传到 Podbean
        temp_mp3_path = "temp_podbean.mp3"
        if cloud_storage.download_audio(st.session_state.audio_url, temp_mp3_path):
            upload_success = podbean_uploader.upload_file_to_presigned_url(
                presigned_url,
                temp_mp3_path
            )
            os.remove(temp_mp3_path)  # 清理临时文件
            
            if upload_success:
                st.success("音频发布到 Podbean 成功！")
            else:
                st.error("音频发布到 Podbean 失败。")
        else:
            st.error("从云存储下载音频失败。")
    else:
        st.error("获取 Podbean 上传授权失败。")

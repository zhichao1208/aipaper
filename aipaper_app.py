__import__('pysqlite3') # This is a workaround to fix the error "sqlite3 module is not found" on live streamlit.
import sys 
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3') # This is a workaround to fix the error "sqlite3 module is not found" on live streamlit.

import streamlit as st
from nlm_client import NotebookLMClient
from audio_handler import AudioHandler
from podbean_uploader import PodbeanUploader
from aipaper_agents import NewsroomCrew
from config.aipaper_tasks import AIPaperTasks
import openai
import requests  # 添加  requests 库
from aipaper_crew import AIPaperCrew
from aipaper_crew import PapersList, ChosenPaper, PodcastContent
import json
# 初始化 OpenAI API
openai.api_key = st.secrets["OPENAI_API_KEY"]
openai_model_name = st.secrets["OPENAI_MODEL_NAME"]  # 获取 OpenAI 模型名称
exa_api_key = st.secrets["EXA_API_KEY"]  # 获取 EXA API 密钥
serper_api_key = st.secrets["SERPER_API_KEY"]  # 获取 Serper API 密钥

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
    crew = AIPaperCrew().crew().kickoff(inputs=inputs)
    papers = PapersList.model_validate_json(open("papers_list.json").read())

    if papers:
        st.success("找到以下论文:")
        for paper in papers:
            st.write(f"- {paper['title']} (链接: {paper['link']})")
        st.session_state.papers = papers  # 保存论文列表到会话状态
    else:
        st.error("未找到相关论文，请尝试其他主题。")

# 步骤 2: 直接读取论文内容
if 'papers' in st.session_state:
    # 从 chosenpaper.json 中读取论文
    with open("chosenpaper.json", "r", encoding="utf-8") as f:
        chosen_paper_data = json.load(f)

    # 假设 chosen_paper_data 是一个字典，包含所需的论文信息
    if chosen_paper_data:
        selected_paper = chosen_paper_data  # 直接使用 JSON 中的论文数据

        if st.button("显示选择的论文内容"):
            st.write("您选择的论文内容:")
            st.write(selected_paper['title'])
            st.write(selected_paper['description'])  # 假设 JSON 中有 content 字

# 步骤 3: 生成播客内容
if 'papers' in st.session_state and st.button("生成播客内容"):
    st.write("正在生成播客内容...")
    crew = AIPaperCrew(topic)
    podcast_content = crew.generate_podcast_content(selected_paper)

    if podcast_content:
        st.success("播客内容生成成功！")
        st.write("播客标题:", podcast_content['title'])
        st.write("播客描述:", podcast_content['description'])
        st.session_state.podcast_content = podcast_content  # 保存播客内容到会话状态
    else:
        st.error("生成播客内容失败。")

# 步骤 4: 发送内容到 NLM
if 'podcast_content' in st.session_state and st.button("发送内容到 NLM"):
    resources = [
        {"content": st.session_state.podcast_content['description'], "type": "text"},
        {"content": selected_paper['link'], "type": "website"},
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
            wav_path = "downloaded_audio.wav"
            mp3_path = "converted_audio.mp3"
            audio_handler.download_audio(audio_url, wav_path)
            audio_handler.convert_wav_to_mp3(wav_path, mp3_path)

# 步骤 6: 上传到 Podbean
if 'mp3_path' in locals():  # 确保 mp3_path 已定义
    podbean_response = podbean_uploader.authorize_file_upload("converted_audio.mp3", mp3_path)
    if podbean_response:
        presigned_url = podbean_response['presigned_url']
        upload_success = podbean_uploader.upload_file_to_presigned_url(presigned_url, mp3_path)
        if upload_success:
            st.success("音频上传成功！")
        else:
            st.error("音频上传失败。")
    else:
        st.error("获取上传授权失败。")
else:
    st.error("mp3_path 未定义，无法上传音频。")

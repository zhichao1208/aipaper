import streamlit as st
from nlm_client import NotebookLMClient
from audio_handler import AudioHandler
from podbean_uploader import PodbeanUploader
from aipaper_agents import NewsroomCrew
from config.aipaper_tasks import AIPaperTasks
import openai
import requests  # 添加 requests 库
import pydub  # 添加 pydub 库
import pyaudio  # 添加 pyaudio 库

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
tasks = AIPaperTasks()

class AIPaperCrew:
    def __init__(self, topic):
        self.topic = topic
        self.newsroom_crew = NewsroomCrew()
        self.paper_finder_agent = self.newsroom_crew.paper_finder_agent()
        self.writer_agent = self.newsroom_crew.writer_agent()

    def find_papers(self):
        find_paper_task = tasks.find_paper_task(agent=self.paper_finder_agent)
        return find_paper_task.execute(inputs={'topic': self.topic})

    def generate_podcast_content(self, selected_paper):
        write_task = tasks.write_task(agent=self.writer_agent)
        return write_task.execute(inputs={'selected_paper': selected_paper})

# 步骤 1: 查找论文
if st.button("查找相关论文"):
    st.write("正在查找相关论文...")
    crew = AIPaperCrew(topic)
    papers = crew.find_papers()

    if papers:
        st.success("找到以下论文:")
        for paper in papers:
            st.write(f"- {paper['title']} (链接: {paper['link']})")
        st.session_state.papers = papers  # 保存论文列表到会话状态
    else:
        st.error("未找到相关论文，请尝试其他主题。")

# 步骤 2: 选择论文
if 'papers' in st.session_state:
    selected_paper_title = st.selectbox("选择一篇论文:", [paper['title'] for paper in st.session_state.papers])
    selected_paper = next(paper for paper in st.session_state.papers if paper['title'] == selected_paper_title)

    if st.button("显示选择的论文内容"):
        st.write("您选择的论文内容:")
        st.write(selected_paper['content'])

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
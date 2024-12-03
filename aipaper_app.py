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
import time
import threading

# 页面配置
st.set_page_config(
    page_title="AI Paper Podcast Generator",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 20px;
        height: 3em;
        background-color: #FF4B4B;
        color: white;
        font-weight: bold;
    }
    .stTextInput>div>div>input {
        border-radius: 10px;
    }
    .status-box {
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .success-box {
        background-color: #D4EDDA;
        color: #155724;
    }
    .error-box {
        background-color: #F8D7DA;
        color: #721C24;
    }
    .info-box {
        background-color: #D1ECF1;
        color: #0C5460;
    }
    </style>
    """, unsafe_allow_html=True)

# 初始化 session state
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False

# 侧边栏配置
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/podcast.png", width=100)
    st.title("⚙️ 配置")
    
    # API 状态检查
    st.subheader("API 状态")
    api_status = {
        "OpenAI": bool(st.secrets["OPENAI_API_KEY"]),
        "NotebookLM": bool(st.secrets["NotebookLM_API_KEY"]),
        "Podbean": bool(st.secrets["podbean_client_id"]),
        "Cloudinary": bool(st.secrets["CLOUDINARY_CLOUD_NAME"])
    }
    
    for api, status in api_status.items():
        if status:
            st.success(f"{api} ✓")
        else:
            st.error(f"{api} ✗")

# 主界面
st.title("🎙️ AI Paper Podcast Generator")
st.markdown("""
    将学术论文转换为引人入胜的播客内容。
    只需输入主题，我们将：
    1. 🔍 查找相关论文
    2. 📝 生成播客脚本
    3. 🎵 创建音频内容
    4. 📢 发布到播客平台
""")

# 创建两列布局
col1, col2 = st.columns([2, 1])

with col1:
    # 用户输入区
    with st.container():
        st.subheader("📚 输入研究主题")
        topic = st.text_input(
            "请输入主题:",
            placeholder="例如：AI music, Quantum Computing...",
            help="输入你感兴趣的研究主题，我们将为你找到相关的学术论文"
        )

    # 论文搜索和选择区
    if st.button("🔍 查找相关论文", key="search_button"):
        with st.spinner("正在搜索相关论文..."):
            try:
                find_papers_crew = AIPaperCrew().find_papers_crew()
                paper_result = find_papers_crew.kickoff(inputs={"topic": topic})
                
                if paper_result:
                    st.session_state.papers = paper_result
                    st.success("✨ 找到相关论文！")
                    with st.expander("📄 查看论文列表", expanded=True):
                        st.markdown(paper_result)
                else:
                    st.error("❌ 未找到相关论文。")
            except Exception as e:
                st.error(f"❌ 搜索过程中出错: {str(e)}")

with col2:
    # 处理状态和进度区
    st.subheader("📊 处理状态")
    if 'papers' in st.session_state:
        status_container = st.container()
        with status_container:
            st.info("✓ 论文搜索完成")
            
            if st.button("🎯 生成播客内容"):
                with st.spinner("正在生成播客内容..."):
                    try:
                        podcast_inputs = {"papers_list": st.session_state.papers}
                        generate_podcast_crew = AIPaperCrew().generate_podcast_content_crew()
                        generate_podcast_content = generate_podcast_crew.kickoff(inputs=podcast_inputs)
                        
                        if generate_podcast_content:
                            st.session_state.podcast_content = generate_podcast_content
                            st.success("✨ 播客内容生成成功！")
                            
                            # 显示生成的内容
                            with st.expander("📝 查看生成的内容", expanded=True):
                                content_data = json.loads(str(generate_podcast_content))
                                st.markdown(f"**标题**: {content_data.get('title')}")
                                st.markdown(f"**描述**: {content_data.get('description')}")
                                st.markdown(f"**提示文本**: {content_data.get('prompt_text')}")
                        else:
                            st.error("❌ 生成播客内容失败。")
                    except Exception as e:
                        st.error(f"❌ 生成过程中出错: {str(e)}")

# 音频处理区
if 'podcast_content' in st.session_state:
    st.subheader("🎵 音频处理")
    audio_col1, audio_col2 = st.columns(2)
    
    with audio_col1:
        if st.button("🎙️ 生成音频"):
            with st.spinner("正在生成音频..."):
                try:
                    content_data = json.loads(str(st.session_state.podcast_content))
                    resources = [
                        {"content": content_data.get('paper_link', ''), "type": "website"}
                    ]
                    text = content_data.get('prompt_text', '')
                    
                    client = NotebookLMClient(
                        st.secrets["NotebookLM_API_KEY"],
                        webhook_url="http://localhost:5000/webhook"
                    )
                    
                    request_id = client.send_content(resources, text)
                    if request_id:
                        st.session_state.request_id = request_id
                        st.session_state.audio_status = {"status": "processing"}
                        st.success("✨ 音频生成请求已发送！")
                        
                        # 启动状态检查
                        def check_status():
                            while st.session_state.audio_status["status"] == "processing":
                                try:
                                    status_data = client.check_status(request_id)
                                    if status_data:
                                        st.session_state.audio_status = {
                                            "status": status_data.get("status"),
                                            "updated_on": status_data.get("updated_on"),
                                            "audio_url": status_data.get("audio_url"),
                                            "error_message": status_data.get("error_message")
                                        }
                                        if status_data.get("audio_url"):
                                            st.session_state.audio_url = status_data.get("audio_url")
                                            break
                                        elif status_data.get("error_message"):
                                            break
                                except Exception as e:
                                    print(f"状态检查出错: {str(e)}")
                                time.sleep(20)
                        
                        # 在后台线程中运行状态检查
                        status_thread = threading.Thread(target=check_status)
                        status_thread.daemon = True
                        status_thread.start()
                    else:
                        st.error("❌ 发送音频生成请求失败。")
                except Exception as e:
                    st.error(f"❌ 音频生成过程中出错: {str(e)}")
    
    with audio_col2:
        if 'audio_status' in st.session_state:
            status = st.session_state.audio_status
            st.write("当前状态:", status.get("status"))
            if status.get("updated_on"):
                st.write("更新时间:", status.get("updated_on"))
            if status.get("error_message"):
                st.error(f"❌ 错误: {status.get('error_message')}")
            if status.get("audio_url"):
                st.success("✨ 音频生成完成！")
                st.session_state.audio_url = status.get("audio_url")

# 发布区域
if 'audio_url' in st.session_state:
    st.subheader("📢 发布播客")
    if st.button("🚀 发布到 Podbean"):
        with st.spinner("正在发布到 Podbean..."):
            try:
                # 初始化所需的客户端
                cloud_storage = CloudStorage(
                    st.secrets["CLOUDINARY_CLOUD_NAME"],
                    st.secrets["CLOUDINARY_API_KEY"],
                    st.secrets["CLOUDINARY_API_SECRET"]
                )
                
                podbean_client = PodbeanUploader(
                    st.secrets["podbean_client_id"],
                    st.secrets["podbean_client_secret"]
                )
                
                # 下载音频
                temp_audio = "temp_audio.wav"
                if cloud_storage.download_audio(st.session_state.audio_url, temp_audio):
                    # 上传到 Podbean
                    podbean_response = podbean_client.authorize_file_upload(
                        "podcast_audio.mp3",
                        temp_audio
                    )
                    
                    if podbean_response:
                        upload_success = podbean_client.upload_file_to_presigned_url(
                            podbean_response['presigned_url'],
                            temp_audio
                        )
                        
                        if upload_success:
                            # 发布播客
                            content_data = json.loads(str(st.session_state.podcast_content))
                            episode_data = podbean_client.publish_episode(
                                title=content_data.get('title'),
                                content=content_data.get('description'),
                                file_key=podbean_response.get('file_key')
                            )
                            
                            if episode_data:
                                st.success("🎉 播客发布成功！")
                                st.markdown(f"[点击查看播客]({episode_data.get('episode_url')})")
                            else:
                                st.error("❌ 发布播客失败")
                        else:
                            st.error("❌ 上传到 Podbean 失败")
                    else:
                        st.error("❌ 获取 Podbean 上传授权失败")
                    
                    # 清理临时文件
                    if os.path.exists(temp_audio):
                        os.remove(temp_audio)
                else:
                    st.error("❌ 下载音频失败")
            except Exception as e:
                st.error(f"❌ 发布过程中出错: {str(e)}")

# 页脚
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center'>
        <p>Made with ❤️ by AI Paper Podcast Team</p>
    </div>
    """,
    unsafe_allow_html=True
)

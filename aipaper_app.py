__import__('pysqlite3')
import sys 
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import streamlit as st
from nlm_client import NotebookLMClient
from audio_handler import AudioHandler
from podbean_uploader import PodbeanUploader
from aipaper_agents import NewsroomCrew
import openai
import requests
from aipaper_crew import AIPaperCrew, PapersList, ChosenPaper, PodcastContent
import json
from cloud_storage import CloudStorage
import os
import time
import threading
from datetime import datetime
import re
import html
from queue import Queue
from typing import Optional, Dict, Any
from podcast_schema import PodcastContent, normalize_content

# 状态映射字典
status_mapping = {
    "unknown": "未知状态",
    0: "等待处理",
    10: "正在初始化",
    20: "正在处理",
    30: "正在生成音频",
    60: "处理中",
    80: "即将完成"
}

def parse_podbean_feed(feed_url: str) -> list:
    """解析 Podbean Feed 获取播客列表"""
    try:
        response = requests.get(feed_url)
        response.raise_for_status()
        
        # 使用正则表达式提取每个播客条目
        episodes = []
        pattern = r'<item>.*?<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>.*?<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>.*?<pubDate>(.*?)</pubDate>.*?<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>.*?<itunes:duration>(.*?)</itunes:duration>.*?</item>'
        
        episode_matches = re.finditer(pattern, response.text, re.DOTALL)
        
        for match in episode_matches:
            try:
                title = html.unescape(match.group(1).strip())
                link = html.unescape(match.group(2).strip())
                date = datetime.strptime(match.group(3).strip(), '%a, %d %b %Y %H:%M:%S %z').strftime('%Y-%m-%d')
                description = html.unescape(match.group(4).strip())
                duration = match.group(5).strip()
                
                episode = {
                    'title': title,
                    'link': link,
                    'date': date,
                    'description': description,
                    'duration': duration
                }
                episodes.append(episode)
            except Exception as e:
                print(f"处理单个播客条目时出错: {str(e)}")
                continue
                
        return episodes
        
    except Exception as e:
        print(f"获取播客列表失败: {str(e)}")
        return []

def normalize_podcast_content(content: dict) -> Optional[Dict[str, Any]]:
    """规范化播客内容，确保所有必需字段存在且格式正确"""
    try:
        # 创建新字典以避免修改原始数据
        normalized = content.copy()
        
        # 处理prompt/prompt_text字段
        if 'prompt' in normalized and 'prompt_text' not in normalized:
            normalized['prompt_text'] = normalized.pop('prompt')
        
        # 验证必需字段
        required_fields = ['title', 'description', 'paper_link', 'prompt_text']
        missing_fields = [field for field in required_fields if not normalized.get(field)]
        
        if missing_fields:
            print(f"缺少必需字段: {', '.join(missing_fields)}")
            return None
            
        return normalized
    except Exception as e:
        print(f"规范化内容时出错: {str(e)}")
        return None

def generate_content_with_chatgpt(paper_link: str) -> Optional[Dict[str, Any]]:
    """使用ChatGPT直接生成播客内容"""
    try:
        system_prompt = """你是一个专业的学术播客内容生成助手。请生成一个包含以下字段的JSON格式内容：
        {
            "title": "播客标题",
            "description": "播客描述",
            "paper_link": "论文链接",
            "prompt_text": "用于生成音频的详细内容"
        }
        
        注意：
        1. 必须使用prompt_text作为字段名（不是prompt）
        2. prompt_text应包含完整的播客脚本
        3. 所有字段都必须存在且不能为空
        4. 内容必须是有效的JSON格式"""
        
        user_prompt = f"""请根据以下论文链接生成播客内容：
        
        论文链接: {paper_link}
        
        要求：
        1. 生成的内容必须是完整的JSON格式
        2. 必须包含所有必需字段（title, description, paper_link, prompt_text）
        3. prompt_text字段应该包含完整的播客脚本，包括论文的背景、主要发现和影响
        4. 内容应该专业、准确且易于理解"""
        
        response = openai.ChatCompletion.create(
            model=os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        
        # 解析JSON响应
        content = json.loads(response.choices[0].message.content)
        
        # 规范化内容
        normalized_content = normalize_content(content)
        return normalized_content.dict()
        
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {str(e)}")
        return None
    except Exception as e:
        print(f"生成内容时出错: {str(e)}")
        return None

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
if 'should_stop_check' not in st.session_state:
    st.session_state.should_stop_check = False
if 'status_queue' not in st.session_state:
    st.session_state.status_queue = Queue()

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

# 在主界面标题之后添加播客列表展示区域
st.markdown("""
    <style>
    .podcast-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 1rem;
        padding: 1rem 0;
    }
    .podcast-card {
        background: white;
        border-radius: 10px;
        padding: 1rem;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        transition: transform 0.2s;
    }
    .podcast-card:hover {
        transform: translateY(-5px);
    }
    .podcast-title {
        color: #1E88E5;
        font-size: 1.1rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .podcast-meta {
        color: #666;
        font-size: 0.9rem;
        margin-bottom: 0.5rem;
    }
    .podcast-description {
        color: #333;
        font-size: 0.95rem;
        margin-bottom: 0.5rem;
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .podcast-link {
        color: #FF4B4B;
        text-decoration: none;
        font-weight: bold;
    }
    .podcast-link:hover {
        text-decoration: underline;
    }
    </style>
""", unsafe_allow_html=True)

# 添加播客列表标和展开选项
with st.expander("🎧 最新播客列表", expanded=True):
    feed_url = "https://feed.podbean.com/zhichao1208/feed.xml"
    episodes = parse_podbean_feed(feed_url)
    
    if episodes:
        st.markdown('<div class="podcast-grid">', unsafe_allow_html=True)
        
        for episode in episodes:
            st.markdown(f"""
                <div class="podcast-card">
                    <div class="podcast-title">{episode['title']}</div>
                    <div class="podcast-meta">
                        📅 {episode['date']} | ⏱️ {episode['duration']}
                    </div>
                    <div class="podcast-description">
                        {episode['description']}
                    </div>
                    <a href="{episode['link']}" target="_blank" class="podcast-link">
                        🎧 收听播客
                    </a>
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("暂无播客内容")

# 添加分隔线
st.markdown("---")

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
        st.subheader("📚 输入研究主题或论文链接")
        
        # 创建两列用于并排显示输入框
        input_col1, input_col2 = st.columns(2)
        
        with input_col1:
            topic = st.text_input(
                "输入研究主题:",
                placeholder="例如：AI music, Quantum Computing...",
                help="输入你感兴趣的研究主题，我们将为你找到相关的学术论文"
            )
            
            if st.button("🔍 查找相关论文", key="search_button"):
                with st.spinner("正在搜索相关论文..."):
                    try:
                        find_papers_crew = AIPaperCrew().find_papers_crew()
                        paper_result = find_papers_crew.kickoff(inputs={"topic": topic})
                        
                        if paper_result:
                            st.session_state.papers = paper_result
                            st.success(" 找到相关论文！")
                            with st.expander("📄 查看论文列表", expanded=True):
                                st.markdown(paper_result)
                        else:
                            st.error("❌ 未找到相论文。")
                    except Exception as e:
                        st.error(f"❌ 搜索过程中出错: {str(e)}")
        
        with input_col2:
            paper_link = st.text_input(
                "直接输入论文链接:",
                placeholder="https://arxiv.org/abs/2312.12345",
                help="直接输入论文链接，我们将为你生成播客内容"
            )
            
            if st.button("📝 直接生成内容", key="generate_direct_button"):
                with st.spinner("正在使用ChatGPT生成内容..."):
                    try:
                        # 直接使用ChatGPT生成内容
                        content = generate_content_with_chatgpt(paper_link)
                        
                        if content:
                            st.session_state.podcast_content = content
                            st.success("✨ 内容生成成功！")
                            
                            # 显示生成的内容
                            with st.expander("查看生成的内容", expanded=True):
                                st.markdown(f"**标题**: {content['title']}")
                                st.markdown(f"**描述**: {content['description']}")
                                st.markdown(f"**提示文本**: {content['prompt_text']}")
                        else:
                            st.error("❌ 生成内容失败，请检查论文链接是否正确。")
                    except Exception as e:
                        st.error(f"❌ 生成过程中出错: {str(e)}")
                        st.write("错误详情:", str(e))  # 添加详细错误信息

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
                                st.write("Debug - Raw Content:", generate_podcast_content)
                                st.write("Debug - Type:", type(generate_podcast_content))
                                
                                try:
                                    # 处理 CrewOutput 类型
                                    if hasattr(generate_podcast_content, 'raw'):
                                        raw_content = generate_podcast_content.raw
                                        st.write("Debug - CrewOutput Raw Content:", raw_content)
                                        
                                        # 如果是 JSON 字符串，尝试解析
                                        if isinstance(raw_content, str):
                                            # 除可的 JSON 代码块标记
                                            json_str = re.sub(r'^```json\s*|\s*```$', '', raw_content.strip())
                                            content_data = json.loads(json_str)
                                        else:
                                            content_data = raw_content
                                    else:
                                        content_data = generate_podcast_content
                                    
                                    st.write("Debug - Parsed Content:", content_data)
                                    
                                    # 显示内容
                                    st.markdown(f"**标题**: {content_data.get('title', 'N/A')}")
                                    st.markdown(f"**描述**: {content_data.get('description', 'N/A')}")
                                    st.markdown(f"**提示文本**: {content_data.get('prompt_text', content_data.get('prompt', 'N/A'))}")
                                    
                                    # 保存解析后的内容到 session_state
                                    st.session_state.podcast_content = content_data
                                    
                                except Exception as e:
                                    st.error(f"❌ 内容处理错误: {str(e)}")
                                    st.write("Debug - Error Details:", str(e))
                        else:
                            st.error("❌ 生成播客内容失败。")
                    except Exception as e:
                        st.error(f"❌ 生成过程中出错: {str(e)}")

# 音频处理区域
if 'podcast_content' in st.session_state:
    st.subheader("🎵 音频处理")
    audio_col1, audio_col2 = st.columns(2)
    
    with audio_col1:
        if st.button("🎙️ 生成音频"):
            with st.spinner("正在发送音频生成请求..."):
                try:
                    # 调试输出原始内容
                    st.write("Debug - Raw Content:", st.session_state.podcast_content)
                    
                    # 处理 podcast_content
                    content_data = None
                    if hasattr(st.session_state.podcast_content, 'raw'):
                        # 处理 CrewOutput 类型
                        raw_content = st.session_state.podcast_content.raw
                        st.write("Debug - CrewOutput Raw Content:", raw_content)
                        
                        # 如果是 JSON 字符串，尝试解析
                        if isinstance(raw_content, str):
                            # 移除可能的 JSON 代码块标记
                            json_str = re.sub(r'^```json\s*|\s*```$', '', raw_content.strip())
                            content_data = json.loads(json_str)
                        else:
                            content_data = raw_content
                    elif isinstance(st.session_state.podcast_content, str):
                        content_data = json.loads(st.session_state.podcast_content)
                    elif isinstance(st.session_state.podcast_content, dict):
                        content_data = st.session_state.podcast_content
                    else:
                        st.error(f"❌ 未知的内容格式: {type(st.session_state.podcast_content)}")
                    
                    # 只有当content_data有效时继续处理
                    if content_data is not None:
                        # 验证 API 密钥
                        if st.secrets.get("NotebookLM_API_KEY"):
                            client = NotebookLMClient(
                                st.secrets["NotebookLM_API_KEY"],
                                webhook_url="http://localhost:5000/webhook"
                            )
                            
                            # 准备请求数据
                            resources = [
                                {"content": content_data['paper_link'], "type": "website"}
                            ]
                            text = content_data['prompt_text']
                            
                            # 发送请求并获取request_id
                            request_id = client.send_content(resources, text)
                            
                            if request_id:
                                # 发送成功，更新状态
                                st.success("✅ 音频生成请求已发送！")
                                st.info("⌛ 正在等待处理...")
                                
                                # 重置停止标志
                                st.session_state.should_stop_check = False
                                
                                # 初始化状态
                                st.session_state.request_id = request_id
                                st.session_state.audio_status = {"status": 0}
                                st.session_state.start_time = time.time()
                                
                                # 定义状态检查函数
                                def check_status_thread():
                                    """检查音频生成状态的后台任务"""
                                    check_count = 0
                                    max_checks = 180  # 最多检查3分钟
                                    last_status = None
                                    
                                    while check_count < max_checks and not st.session_state.should_stop_check:
                                        try:
                                            # 每次检查前更新状态
                                            check_count += 1
                                            current_time = time.time()
                                            elapsed_time = int(current_time - st.session_state.start_time)
                                            
                                            # 检查音频状态
                                            status_data = client.check_status(request_id)
                                            
                                            # 准备基础状态信息
                                            base_status = {
                                                'check_count': check_count,
                                                'elapsed_time': elapsed_time,
                                                'check_time': time.strftime("%H:%M:%S"),
                                                'last_status': last_status,
                                                'status': status_data.get('status', 0) if status_data else 0
                                            }
                                            
                                            if status_data:
                                                # 记录最后一次状态
                                                last_status = f"状态码: {status_data.get('status', 0)}, 消息: {status_data.get('message', '无')}"
                                                # 合并状态信息
                                                status_data.update(base_status)
                                                st.session_state.status_queue.put(status_data)
                                            else:
                                                # 即使没有新状态也发送基础信息
                                                st.session_state.status_queue.put(base_status)
                                                
                                            # 如果处理完成或出错，结束检查
                                            if status_data and (status_data.get("audio_url") or status_data.get("error_message")):
                                                break
                                                    
                                        except Exception as e:
                                            error_status = {
                                                **base_status,
                                                'error_message': f"状态检查出错: {str(e)}"
                                            }
                                            st.session_state.status_queue.put(error_status)
                                            print(f"状态检查出错: {str(e)}")
                                        
                                        time.sleep(5)  # 每5秒检查一次
                                    
                                    # 标记检查结束
                                    st.session_state.status_queue.put(None)
                                
                                # 启动状态检查线程
                                status_thread = threading.Thread(target=check_status_thread)
                                status_thread.daemon = True
                                status_thread.start()
                                
                                # 等待初始状态更新
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("❌ 发送音频生成请求失败")
                        else:
                            st.error("❌ NotebookLM API 密钥未设置")
                    
                except json.JSONDecodeError as e:
                    st.error(f"❌ JSON解析失败: {str(e)}")
                except Exception as e:
                    st.error(f"❌ 发送请求时出错: {str(e)}")
                    st.write("错误详情:", str(e))
    
    # 在同一个if语句内处理audio_col2
    with audio_col2:
        if 'audio_status' in st.session_state:
            status = st.session_state.audio_status
            current_status = status.get("status", "unknown")
            
            # 创建状态显示容器
            status_container = st.empty()
            with status_container:
                # 显示当前状态
                status_text = status_mapping.get(current_status, status_mapping["unknown"])
                st.markdown(f"### 当前状态: {status_text}")
                
                # 显示检查信息
                col1, col2 = st.columns(2)
                with col1:
                    st.text(f"检查次数: {status.get('check_count', 0)}")
                    st.text(f"最后检查时间: {status.get('check_time', '未知')}")
                with col2:
                    elapsed_time = status.get('elapsed_time', 0)
                    minutes = elapsed_time // 60
                    seconds = elapsed_time % 60
                    st.text(f"总处理时间: {minutes}分{seconds}秒")
                
                # 显示最后一次状态信息
                if status.get('last_status'):
                    st.info(status.get('last_status'))
                
                # 显示进度条
                if isinstance(current_status, (int, float)) and current_status < 100:
                    progress = int(current_status)
                    st.progress(progress)
                    st.text(f"进度: {progress}%")
                
                # 显示错误信息（如果有）
                if status.get("error_message"):
                    st.error(f"错误信息: {status.get('error_message')}")
                
                # 显示音频（如果已生成）
                if status.get("audio_url"):
                    st.success("✨ 音频生成完成！")
                    st.audio(status.get("audio_url"))
                    
                    # 更新播客内容的音频链接
                    if 'podcast_content' in st.session_state:
                        content = st.session_state.podcast_content
                        content['audio_link'] = status.get("audio_url")
                        # 规范化内容格式
                        st.session_state.podcast_content = normalize_content(content)
                    
                    # 添加下载按钮
                    st.markdown(f"[📥 下载音频]({status.get('audio_url')})")

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
                st.write("正在下载音频文件...")
                if cloud_storage.download_audio(st.session_state.audio_url, temp_audio):
                    st.write("音频文件下载成功，准备上传到 Cloudinary...")
                    
                    # 上传到 Cloudinary
                    upload_result = cloud_storage.upload_audio(temp_audio)
                    
                    if upload_result["success"]:
                        st.write("音频文件上传到 Cloudinary 成功，准备发布到 Podbean...")
                        cloudinary_url = upload_result["url"]
                        
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
                    else:
                        st.error(f"❌ 上传到 Cloudinary 失败: {upload_result.get('error')}")
                else:
                    st.error("❌ 下载音频失败")
                    
                # 清理临时文件
                if os.path.exists(temp_audio):
                    os.remove(temp_audio)
                    st.write("临时文件已清理")
                    
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

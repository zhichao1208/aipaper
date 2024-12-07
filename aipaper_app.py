__import__('pysqlite3')
import sys 
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import streamlit as st
from nlm_client import NotebookLMClient, CrewOutput
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
from cloudinary_storage import CloudStorage
from podbean_client import PodbeanClient

# 状态映射字典
status_mapping = {
    "unknown": "⏳ Unknown Status",
    "pending": "⏳ Pending",
    "processing": "🔄 Processing",
    "completed": "✅ Completed",
    "failed": "❌ Failed",
    "error": "❌ Error"
}

def parse_podbean_feed(feed_url: str) -> list:
    """解析 Podbean Feed 获取播客列表"""
    try:
        response = requests.get(feed_url)
        response.raise_for_status()
        
        # 使用正则表达式提个播客条目
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
        print(f"获取播客列表失: {str(e)}")
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
        system_prompt = """你是一个专业的学术播客内容生成助手。请生成一个包含以下字段的JSON格��内容：
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

def generate_podcast_content(paper_link: str) -> PodcastContent:
    """生成播客内容"""
    try:
        # 初始化 NotebookLM 客户端
        client = NotebookLMClient(
            api_key=os.getenv("NotebookLM_API_KEY"),
            webhook_url="http://localhost:5000/webhook"
        )
        
        # 发送内容生成请求
        resources = [{"content": paper_link, "type": "website"}]
        text = "Today, we dive into this fascinating research paper and explore its key findings!"
        
        request_id = client.send_content(resources, text)
        
        if not request_id:
            raise ValueError("生成请求失败")
            
        # 等待音频生成完成
        status = None
        while True:
            status = client.check_status(request_id)
            if status and (status.get("audio_url") or status.get("error_message")):
                break
            time.sleep(30)
            
        if status and status.get("audio_url"):
            # 创建播客内容
            return PodcastContent(
                title=f"AI Paper Review: {paper_link}",
                description="An AI-generated review of the latest research paper",
                prompt_text=text,
                paper_link=paper_link,
                audio_link=status["audio_url"]
            )
        else:
            error_msg = status.get("error_message") if status else "未知错误"
            raise ValueError(f"音频生成失败: {error_msg}")
            
    except Exception as e:
        raise Exception(f"生成播客内容时出错: {str(e)}")

# 页面配置
st.set_page_config(
    page_title="AI Paper+",
    page_icon="📚",
    layout="centered"
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

# 初始化 session state 变
if 'nlm_client' not in st.session_state:
    api_key = os.getenv("NotebookLM_API_KEY")
    webhook_url = "http://localhost:5000/webhook"  # 本地webhook服务器地址
    st.session_state.nlm_client = NotebookLMClient(api_key=api_key, webhook_url=webhook_url)

if 'should_stop_check' not in st.session_state:
    st.session_state.should_stop_check = False

if 'status_thread' not in st.session_state:
    st.session_state.status_thread = None

if 'current_request_id' not in st.session_state:
    st.session_state.current_request_id = None

if 'check_count' not in st.session_state:
    st.session_state.check_count = 0

if 'last_check_time' not in st.session_state:
    st.session_state.last_check_time = None

# 初始化 session state 变量
if 'generate_podcast' not in st.session_state:
    st.session_state.generate_podcast = False

# 主界面布局
st.title("AI Paper+ 🎙️")
st.markdown("""
    Transform academic papers into engaging podcast episodes with AI.
    Just paste your paper link below to get started!
""")

# 输入部分
with st.form("paper_input"):
    paper_link = st.text_input(
        "Paper Link",
        placeholder="Enter the URL of your academic paper"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        paper_title = st.text_input(
            "Paper Title (Optional)",
            placeholder="Enter paper title if URL is unavailable"
        )
    with col2:
        paper_authors = st.text_input(
            "Authors (Optional)",
            placeholder="Enter paper authors"
        )
    
    paper_abstract = st.text_area(
        "Abstract (Optional)",
        placeholder="Enter paper abstract if URL is unavailable",
        height=150
    )
    
    submit_button = st.form_submit_button("Generate Podcast 🎙️")

if submit_button:
    if not paper_link and not (paper_title and paper_abstract):
        st.error("Please provide either a paper link or both title and abstract")
    else:
        try:
            # Initialize clients
            client = NotebookLMClient(
                os.getenv("NotebookLM_API_KEY"),
                webhook_url="http://localhost:5000/webhook"
            )
            request_data = {
                "paper_link": paper_link if paper_link else None,
                "paper_title": paper_title if paper_title else None,
                "paper_authors": paper_authors if paper_authors else None,
                "paper_abstract": paper_abstract if paper_abstract else None
            }
            with st.spinner("正在发送请求..."):
                response = client.send_request(request_data)
                if response and response.get("request_id"):
                    st.session_state.current_request_id = response["request_id"]
                    st.session_state.should_stop_check = False
                    st.success("✨ 请求发送成功！")
                    st.session_state.content_generated = True
                    st.rerun()
                else:
                    st.error("❌ 请求发送失败")
                    with st.expander("查看错误详情"):
                        st.json(response)
        except Exception as e:
            st.error(f"请求出错: {str(e)}")
            with st.expander("查看错误详情"):
                st.exception(e)

# Display generated content
if st.session_state.get('content_generated', False):
    with st.expander("View Generated Content", expanded=True):
        try:
            content_data = None
            
            if 'content_data' in st.session_state:
                content_data = st.session_state.content_data
            
            if content_data:
                if isinstance(content_data, dict):
                    # Handle dictionary format
                    st.markdown("### Episode Title")
                    st.write(content_data.get('title', 'Title not available'))
                    
                    st.markdown("### Episode Description")
                    st.write(content_data.get('description', 'Description not available'))
                    
                    st.markdown("### Show Notes")
                    st.write(content_data.get('show_notes', 'Show notes not available'))
                    
                elif isinstance(content_data, CrewOutput):
                    # Handle CrewOutput format
                    st.markdown("### Episode Title")
                    st.write(getattr(content_data, 'title', 'Title not available'))
                    
                    st.markdown("### Episode Description")
                    st.write(getattr(content_data, 'description', 'Description not available'))
                    
                    st.markdown("### Show Notes")
                    st.write(getattr(content_data, 'show_notes', 'Show notes not available'))
                    
                else:
                    # Handle string format (JSON)
                    try:
                        json_data = json.loads(content_data)
                        st.markdown("### Episode Title")
                        st.write(json_data.get('title', 'Title not available'))
                        
                        st.markdown("### Episode Description")
                        st.write(json_data.get('description', 'Description not available'))
                        
                        st.markdown("### Show Notes")
                        st.write(json_data.get('show_notes', 'Show notes not available'))
                    except json.JSONDecodeError:
                        st.error("Invalid content format")
                        st.text(content_data)
            
        except Exception as e:
            st.error(f"Error displaying content: {str(e)}")

# 状态显示区域
if 'current_request_id' in st.session_state and st.session_state.current_request_id:
    st.subheader("📊 Processing Status")
    
    # 显示检查信息
    col1, col2 = st.columns(2)
    with col1:
        if 'check_count' not in st.session_state:
            st.session_state.check_count = 0
        st.text(f"Check Count: {st.session_state.check_count}")
        check_time = datetime.now().strftime("%H:%M:%S")
        st.text(f"Last Check: {check_time}")
    
    with col2:
        if 'start_time' not in st.session_state:
            st.session_state.start_time = time.time()
        elapsed_time = int(time.time() - st.session_state.start_time)
        minutes = elapsed_time // 60
        seconds = elapsed_time % 60
        st.text(f"Processing Time: {minutes}m {seconds}s")
    
    # 动态状态容器
    status_container = st.empty()
    
    try:
        # 获取最新状态
        client = NotebookLMClient(
            os.getenv("NotebookLM_API_KEY"),
            webhook_url="http://localhost:5000/webhook"
        )
        status_data = client.check_status(st.session_state.current_request_id)
        
        if status_data:
            # 更新检查次数
            st.session_state.check_count += 1
            
            with status_container:
                # 显示状态文本
                current_status = status_data.get("status", "unknown")
                status_text = status_mapping.get(current_status, status_mapping["unknown"])
                st.markdown(f"### Current Status: {status_text}")
                
                # 显示原始状态数据
                st.markdown("### Raw Status Response")
                # 清理 JSON 字符串中的控制字符
                cleaned_data = {
                    k: str(v).replace('\n', ' ').replace('\r', '') 
                    if isinstance(v, str) else v 
                    for k, v in status_data.items()
                }
                st.code(json.dumps(cleaned_data, indent=2, ensure_ascii=False))
                st.text(f"Request ID: {st.session_state.current_request_id}")
                
                # 显示进度条
                if isinstance(current_status, (int, float)):
                    progress = min(int(current_status), 100)
                    st.progress(progress / 100)
                    st.text(f"Progress: {progress}%")
                
                # 显示音频（如果已生成）
                if status_data.get("audio_url"):
                    st.success("✨ Audio generation complete!")
                    st.audio(status_data["audio_url"])
                    st.markdown(f"[📥 Download Audio]({status_data['audio_url']})")
                    
                    # Auto upload to Podbean
                    try:
                        if not st.session_state.get('upload_started', False):
                            st.session_state.upload_started = True
                            
                            # Initialize Podbean client
                            podbean = PodbeanClient(
                                client_id=os.getenv("PODBEAN_CLIENT_ID"),
                                client_secret=os.getenv("PODBEAN_CLIENT_SECRET")
                            )
                            
                            # Initialize cloud storage
                            cloud_storage = CloudStorage()
                            
                            # Download and upload to Cloudinary
                            with st.spinner("Uploading to podcast platform..."):
                                # Get content data
                                content = st.session_state.get('content_data', {})
                                if isinstance(content, str):
                                    try:
                                        content = json.loads(content)
                                    except json.JSONDecodeError:
                                        content = {}
                                elif isinstance(content, CrewOutput):
                                    content = {
                                        'title': getattr(content, 'title', ''),
                                        'description': getattr(content, 'description', ''),
                                        'show_notes': getattr(content, 'show_notes', '')
                                    }
                                
                                # Upload to Cloudinary
                                audio_url = status_data["audio_url"]
                                cloudinary_url = cloud_storage.upload_audio(audio_url)
                                
                                if cloudinary_url:
                                    # Prepare podcast data
                                    podcast_data = {
                                        'title': content.get('title', 'New AI Paper+ Episode'),
                                        'content': content.get('description', '') + '\n\n' + content.get('show_notes', ''),
                                        'status': 'publish',
                                        'type': 'public',
                                        'media_url': cloudinary_url
                                    }
                                    
                                    # Upload to Podbean
                                    upload_result = podbean.upload_episode(podcast_data)
                                    
                                    if upload_result.get('episode'):
                                        st.success("✨ Episode published successfully!")
                                        st.markdown(f"[🎙️ Listen on Podbean]({upload_result['episode'].get('permalink_url', '')})")
                                    else:
                                        st.error("Failed to publish episode")
                                        st.json(upload_result)
                                else:
                                    st.error("Failed to upload audio to cloud storage")
                            
                    except Exception as e:
                        st.error(f"❌ Error during publishing: {str(e)}")
                    finally:
                        st.session_state.should_stop_check = True
                        if 'start_time' in st.session_state:
                            del st.session_state.start_time
                
                # 显示错误信息
                if status_data.get("error_message"):
                    st.error(f"Error: {status_data['error_message']}")
                    st.session_state.should_stop_check = True
                    if 'start_time' in st.session_state:
                        del st.session_state.start_time
                
                # 自动刷新
                if not st.session_state.should_stop_check:
                    time.sleep(30)  # Check every 30 seconds
                    st.rerun()
                    
    except Exception as e:
        with status_container:
            st.error(f"Status update error: {str(e)}")
        if not st.session_state.should_stop_check:
            time.sleep(30)
            st.rerun()

# 页脚前添加 Podbean 播放器
st.markdown("""
    <iframe 
        title="AI Paper+" 
        allowtransparency="true" 
        height="315" 
        width="100%" 
        style="border: none; min-width: min(100%, 430px);height:315px;" 
        scrolling="no" 
        data-name="pb-iframe-player" 
        src="https://www.podbean.com/player-v2/?i=t65yp-12d7e0b-pbblog-playlist&share=1&download=1&rtl=0&fonts=Arial&skin=1&font-color=auto&logo_link=episode_page&order=episodic&limit=10&filter=all&ss=a713390a017602015775e868a2cf26b0&btn-skin=3267a3&size=315" 
        loading="lazy" 
        allowfullscreen="">
    </iframe>
    """, unsafe_allow_html=True)

# 页脚
st.markdown("---")
st.markdown("Made with ❤️ by [AI Paper+](https://aipaper.plus)")

def check_status_thread():
    """状态检查线程函数"""
    try:
        while not st.session_state.should_stop_check:
            if st.session_state.current_request_id:
                check_generation_status(st.session_state.current_request_id)
            time.sleep(30)  # 每30秒检查一次
    except Exception as e:
        print(f"状态检查线程出错: {str(e)}")
    finally:
        print("状态检查线程结束")

def start_status_check():
    """启动状态检查"""
    if st.session_state.status_thread is None or not st.session_state.status_thread.is_alive():
        st.session_state.should_stop_check = False
        st.session_state.status_thread = threading.Thread(target=check_status_thread)
        st.session_state.status_thread.daemon = True
        st.session_state.status_thread.start()

def stop_status_check():
    """停止状态检查"""
    st.session_state.should_stop_check = True
    if st.session_state.status_thread and st.session_state.status_thread.is_alive():
        st.session_state.status_thread.join(timeout=1)
    st.session_state.status_thread = None
    st.session_state.current_request_id = None

def check_generation_status(request_id: str):
    """检查生成状态"""
    try:
        st.session_state.check_count += 1
        st.session_state.last_check_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 获取状态
        status = st.session_state.nlm_client.check_status(request_id)
        if status:
            st.session_state.status_queue.put({
                "request_id": request_id,
                "status": status,
                "check_count": st.session_state.check_count,
                "check_time": st.session_state.last_check_time
            })
    except Exception as e:
        print(f"检查状态时出错: {str(e)}")

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
st.title("🎙️ AI论文播客生成器")

# 侧边栏配置
with st.sidebar:
    st.subheader("⚙️ 配置")
    
    # API 状态检查
    st.subheader("API 状态")
    
    # 安全地检查配置（同时检查 secrets 和环境变量）
    def check_config(key):
        try:
            return bool(st.secrets.get(key)) or bool(os.getenv(key))
        except Exception:
            return bool(os.getenv(key))
    
    api_status = {
        "OpenAI": check_config("OPENAI_API_KEY"),
        "NotebookLM": check_config("NotebookLM_API_KEY"),
        "Podbean": check_config("PODBEAN_CLIENT_ID"),
        "Cloudinary": check_config("CLOUDINARY_CLOUD_NAME")
    }
    
    for api, status in api_status.items():
        if status:
            st.success(f"{api} ✓")
        else:
            st.error(f"{api} ✗")

# 主要内容区域
with st.container():
    topic = st.text_input(
        "输入研究主题:",
        placeholder="例如：AI music, Quantum Computing...",
        help="输入你感兴趣的研究主题，我们将为你找到相关的学术论文"
    )
    
    # 搜索论文
    if st.button("🔍 查找相关论文", key="search_button", type="primary"):
        with st.spinner("正在搜索相关论文..."):
            try:
                find_papers_crew = AIPaperCrew().find_papers_crew()
                paper_result = find_papers_crew.kickoff(inputs={"topic": topic})
                
                if paper_result:
                    st.session_state.papers = paper_result
                    st.success("找到相关论文！")
                    st.session_state.show_papers = True
                else:
                    st.error("❌ 未找到相关论文。")
            except Exception as e:
                st.error(f"❌ 搜索过程中出错: {str(e)}")

    # 显示论文列表和生成按钮
    if st.session_state.get('show_papers', False):
        with st.expander("📄 查看论文列表", expanded=True):
            st.markdown(st.session_state.papers)
        
        if st.button("🎯 生成播客内容", key="generate_podcast_button"):
            with st.spinner("🎙️ 正在生成播客内容..."):
                try:
                    podcast_inputs = {"papers_list": st.session_state.papers}
                    generate_podcast_crew = AIPaperCrew().generate_podcast_content_crew()
                    generate_podcast_content = generate_podcast_crew.kickoff(inputs=podcast_inputs)
                    
                    if generate_podcast_content:
                        # 保存生成的内容到 session_state
                        st.session_state.podcast_content = generate_podcast_content
                        st.session_state.content_generated = True
                        st.success("✨ 播客内容生成成功！")
                        st.rerun()
                    else:
                        st.error("❌ 生成播客内容失败。")
                except Exception as e:
                    st.error(f"❌ 生成过程中出错: {str(e)}")

        # 显示生成的内容
        if st.session_state.get('content_generated', False):
            with st.expander("📝 查看生成的内容", expanded=True):
                try:
                    content_data = None
                    podcast_content = st.session_state.podcast_content
                    
                    if hasattr(podcast_content, 'raw'):
                        raw_content = podcast_content.raw
                        if isinstance(raw_content, str):
                            json_str = re.sub(r'^```json\s*|\s*```$', '', raw_content.strip())
                            content_data = json.loads(json_str)
                        else:
                            content_data = raw_content
                    else:
                        content_data = podcast_content
                    
                    if content_data:
                        st.markdown(f"**标题**: {content_data.get('title', 'N/A')}")
                        st.markdown(f"**描述**: {content_data.get('description', 'N/A')}")
                        st.markdown(f"**提示文本**: {content_data.get('prompt_text', content_data.get('prompt', 'N/A'))}")
                        
                        # 生成音频按钮
                        if st.button("🎙️ 生成音频", key="generate_audio_button"):
                            with st.spinner("正在发送音频生成请求..."):
                                try:
                                    client = NotebookLMClient(
                                        os.getenv("NotebookLM_API_KEY"),
                                        webhook_url="http://localhost:5000/webhook"
                                    )
                                    
                                    resources = [
                                        {"content": content_data['paper_link'], "type": "website"}
                                    ]
                                    text = content_data['prompt_text']
                                    
                                    request_id = client.send_content(resources, text)
                                    
                                    if request_id:
                                        st.success("✅ 音频生成请求已发送！")
                                        st.session_state.current_request_id = request_id
                                        st.session_state.should_stop_check = False
                                        
                                        # 显示请求ID和原始状态
                                        st.code(f"Request ID: {request_id}")
                                        
                                        # 显示 JinaReader 状态
                                        with st.expander("📊 JinaReader 状态", expanded=True):
                                            st.info("正在从论文获取内容...")
                                            jina_url = f"https://r.jina.ai/{content_data['paper_link']}"
                                            st.code(f"JinaReader URL: {jina_url}")
                                        
                                        # 显示原始状态数据
                                        with st.expander("📊 原始状态数据", expanded=True):
                                            initial_status = {
                                                "id": request_id,
                                                "status": 0,
                                                "updated_on": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                                "request_json": {
                                                    "resources": resources,
                                                    "text": text,
                                                    "outputType": "audio"
                                                }
                                            }
                                            st.code(json.dumps(initial_status, indent=2, ensure_ascii=False))
                                        
                                        st.rerun()
                                    else:
                                        st.error("❌ 发送音频生成请求失败")
                                except Exception as e:
                                    st.error(f"❌ 发送请求时出错: {str(e)}")
                except Exception as e:
                    st.error(f"❌ 显示内容时出错: {str(e)}")

# 状态显示区域
if 'current_request_id' in st.session_state and st.session_state.current_request_id:
    status_container = st.container()
    with status_container:
        st.subheader("📊 处理状态")
        try:
            # 获取最新状态
            client = NotebookLMClient(
                os.getenv("NotebookLM_API_KEY"),
                webhook_url="http://localhost:5000/webhook"
            )
            status_data = client.check_status(st.session_state.current_request_id)
            
            if status_data:
                # 更新检查次数
                if 'check_count' not in st.session_state:
                    st.session_state.check_count = 0
                st.session_state.check_count += 1
                
                # 显示检查信息
                col1, col2 = st.columns(2)
                with col1:
                    st.text(f"检查次数: {st.session_state.check_count}")
                    check_time = datetime.now().strftime("%H:%M:%S")
                    st.text(f"最后检查: {check_time}")
                
                with col2:
                    if 'start_time' not in st.session_state:
                        st.session_state.start_time = time.time()
                    elapsed_time = int(time.time() - st.session_state.start_time)
                    minutes = elapsed_time // 60
                    seconds = elapsed_time % 60
                    st.text(f"处理时间: {minutes}分{seconds}秒")
                
                # 显示状态文本
                current_status = status_data.get("status", "unknown")
                status_text = status_mapping.get(current_status, status_mapping["unknown"])
                st.markdown(f"### 当前状态: {status_text}")
                
                # 显示原始状态数据
                with st.expander("📊 原始状态返回", expanded=True):
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
                    st.text(f"进度: {progress}%")
                
                # 显示音频（如果已生成）
                if status_data.get("audio_url"):
                    st.success("✨ 音频生成完成！")
                    st.audio(status_data["audio_url"])
                    st.markdown(f"[📥 下载音频]({status_data['audio_url']})")
                    st.session_state.should_stop_check = True
                    # 重置计数器
                    st.session_state.check_count = 0
                    if 'start_time' in st.session_state:
                        del st.session_state.start_time
                
                # 显示错误信息
                if status_data.get("error_message"):
                    st.error(f"错误: {status_data['error_message']}")
                    st.session_state.should_stop_check = True
                    # 重置计数器
                    st.session_state.check_count = 0
                    if 'start_time' in st.session_state:
                        del st.session_state.start_time
                
                # 自动刷新
                if not st.session_state.should_stop_check:
                    time.sleep(30)  # 每30秒检查一次
                    st.rerun()
                    
        except Exception as e:
            st.error(f"状态更新出错: {str(e)}")
            if not st.session_state.should_stop_check:
                time.sleep(30)
                st.rerun()

# 页脚前添加 Apple Podcasts 播放器
st.markdown("""
    <iframe 
        height="450" 
        width="100%" 
        title="Media player" 
        src="https://embed.podcasts.apple.com/us/podcast/ai-paper/id1779979572?itscg=30200&itsct=podcast_box_player&ls=1&mttnsubad=1779979572&theme=auto" 
        id="embedPlayer" 
        sandbox="allow-forms allow-popups allow-same-origin allow-scripts allow-top-navigation-by-user-activation" 
        allow="autoplay *; encrypted-media *; clipboard-write" 
        style="border: 0px; border-radius: 12px; width: 100%; height: 450px; max-width: 660px;">
    </iframe>
""", unsafe_allow_html=True)

# 页脚
st.markdown(
    """
    <div style="text-align: center; margin-top: 50px; color: #666;">
        <p>由 AI 驱动的论文播客生成器 | 基于 NotebookLM</p>
    </div>
    """,
    unsafe_allow_html=True
)

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

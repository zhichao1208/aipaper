import streamlit as st
from nlm_client import NotebookLMClient
from audio_handler import AudioHandler
from podbean_uploader import PodbeanUploader
from aipaper_agents import NewsroomCrew
from config.aipaper_tasks import AIPaperTasks
import openai
import requests
import pydub
import pyaudio
import json
import os
import queue
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

# 初始化 OpenAI API
openai.api_key = os.getenv("OPENAI_API_KEY")
openai_model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo")
exa_api_key = os.getenv("EXA_API_KEY")
serper_api_key = os.getenv("SERPER_API_KEY")

# 验证API密钥是否存在
if not openai.api_key:
    st.error("请在.env文件中设置OPENAI_API_KEY")
    st.stop()

# 初始化session state
if 'podcast_content' not in st.session_state:
    st.session_state.podcast_content = None
if 'request_id' not in st.session_state:
    st.session_state.request_id = None
if 'status_queue' not in st.session_state:
    st.session_state.status_queue = queue.Queue()

# 页面标题和说明
st.title("🎙️ AI Paper Podcast Generator")
st.markdown("将学术论文转换为引人入胜的播客内容。")

# 创建实例
client = NotebookLMClient(os.getenv("NotebookLM_API_KEY"))
audio_handler = AudioHandler()
podbean_uploader = PodbeanUploader(os.getenv("PODBEAN_CLIENT_ID"), os.getenv("PODBEAN_CLIENT_SECRET"))

# 创建两列布局
col1, col2 = st.columns(2)

with col1:
    st.subheader("🔍 通过主题搜索")
    topic = st.text_input("输入研究主题:", placeholder="例如: AI music, Quantum Computing...")
    
    if st.button("🔍 搜索相关论文", key="search_button"):
        with st.spinner("正在搜索相关论文..."):
            crew = AIPaperCrew(topic)
            papers = crew.find_papers()
            
            if papers:
                st.success("找到以下论文:")
                for paper in papers:
                    st.write(f"📄 {paper['title']}")
                    st.write(f"🔗 {paper['link']}")
                    st.write("---")
                st.session_state.papers = papers
            else:
                st.error("未找到相关论文，请尝试其他主题。")

with col2:
    st.subheader("🔗 直接输入论文链接")
    paper_link = st.text_input(
        "输入论文链接:",
        placeholder="https://arxiv.org/abs/2312.12345",
        key="paper_link"
    )
    
    if st.button("📝 生成播客内容", key="generate_button"):
        with st.spinner("正在使用AI生成播客内容..."):
            podcast_content = generate_content_with_chatgpt(paper_link)
            
            if podcast_content:
                st.success("✨ 内容生成成功！")
                
                # 显示生成的内容
                with st.expander("查看生成的内容", expanded=True):
                    st.write("📌 **播客标题:**", podcast_content['title'])
                    st.write("📝 **播客描述:**", podcast_content['description'])
                
                st.session_state.podcast_content = podcast_content
                
                # 添加发送到NLM的按钮
                if st.button("🎵 生成音频", key="audio_button"):
                    with st.spinner("正在生成音频..."):
                        resources = [
                            {"content": podcast_content['description'], "type": "text"},
                            {"content": podcast_content['paper_link'], "type": "website"},
                        ]
                        text = podcast_content['prompt_text']
                        request_id = client.send_content(resources, text)
                        
                        if request_id:
                            st.session_state.request_id = request_id
                            st.success("✨ 内容已发送到NLM，正在生成音频...")
                        else:
                            st.error("发送内容失败。")
            else:
                st.error("生成内容失败，请检查论文链接是否正确。")

def check_audio_status(request_id):
    """检查音频生成状态"""
    try:
        status = client.check_status(request_id)
        if status:
            st.session_state.status_queue.put(status)
        return status
    except Exception as e:
        st.error(f"检查状态时出错: {str(e)}")
        return None

# 如果存在request_id，显示音频状态
if st.session_state.request_id:
    st.markdown("---")
    st.subheader("🎵 音频生成状态")
    if st.button("检查音频状态", key="check_status"):
        with st.spinner("正在检查音频生成状态..."):
            status = check_audio_status(st.session_state.request_id)
            if status:
                st.write("当前状态:", status.get("status", "未知"))
                if status.get("audio_url"):
                    st.success("🎉 音频生成完成！")
                    st.audio(status["audio_url"])
                    
                    # 清空状态队列
                    while not st.session_state.status_queue.empty():
                        st.session_state.status_queue.get()
            else:
                st.warning("无法获取状态信息，请稍后再试。")

def normalize_content(content):
    """规范化内容字段，确保字段名称的一致性"""
    if content is None:
        return None
        
    # 创建新的字典以避免修改原始数据
    normalized = content.copy()
    
    # 处理prompt和prompt_text字段
    if 'prompt' in normalized and 'prompt_text' not in normalized:
        normalized['prompt_text'] = normalized.pop('prompt')
    elif 'prompt_text' in normalized and 'prompt' not in normalized:
        normalized['prompt'] = normalized['prompt_text']
        
    # 确保所有必需字段都存在
    required_fields = ['title', 'description', 'paper_link', 'prompt_text']
    missing_fields = [field for field in required_fields if field not in normalized]
    
    if missing_fields:
        st.error(f"生成的内容缺少必要字段: {', '.join(missing_fields)}")
        return None
        
    return normalized

def generate_content_with_chatgpt(paper_link):
    """使用ChatGPT生成播客内容"""
    try:
        system_prompt = """你是一个专业的学术播客内容生成助手。你需要生成包含以下字段的JSON格式内容：
        - title: 播客标题
        - description: 播客描述
        - paper_link: 论文链接
        - prompt_text: 用于生成音频的详细内容（必须使用prompt_text作为key）
        
        确保生成的内容专业、准确且易于理解。prompt_text字段必须包含完整的论文解读内容。
        注意：必须使用prompt_text作为字段名，不要使用prompt。"""
        
        user_prompt = f"""请根据以下论文链接生成一个学术播客的内容：
        
        论文链接: {paper_link}
        
        请确保返回的JSON包含所有必需字段，特别是prompt_text字段。"""
        
        response = openai.ChatCompletion.create(
            model=openai_model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        
        # 解析JSON响应
        content = json.loads(response.choices[0].message.content)
        
        # 验证必需字段
        required_fields = ['title', 'description', 'paper_link', 'prompt_text']
        missing_fields = [field for field in required_fields if field not in content]
        
        if missing_fields:
            st.error(f"生成的内容缺少必要字段: {', '.join(missing_fields)}")
            return None
            
        # 确保paper_link字段正确
        content['paper_link'] = paper_link
        
        return content
    except json.JSONDecodeError:
        st.error("生成的内容格式不正确")
        return None
    except Exception as e:
        st.error(f"生成内容时发生错误: {str(e)}")
        return None
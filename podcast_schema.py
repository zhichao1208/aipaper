from pydantic import BaseModel
from typing import Optional

class PodcastContent(BaseModel):
    """播客内容的标准数据结构"""
    title: str
    description: str
    prompt_text: str
    paper_link: str
    audio_link: Optional[str] = None

def normalize_content(content: dict) -> PodcastContent:
    """规范化内容格式"""
    # 处理prompt/prompt_text字段
    if 'prompt' in content and 'prompt_text' not in content:
        content['prompt_text'] = content.pop('prompt')
    
    # 确保所有必需字段存在
    required_fields = {
        'title': content.get('title', ''),
        'description': content.get('description', ''),
        'prompt_text': content.get('prompt_text', ''),
        'paper_link': content.get('paper_link', ''),
        'audio_link': content.get('audio_link', None)
    }
    
    return PodcastContent(**required_fields) 
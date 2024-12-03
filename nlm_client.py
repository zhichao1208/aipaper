import requests
import json

class NotebookLMClient:
    def __init__(self, api_key: str, webhook_url: str):
        self.api_key = api_key
        self.webhook_url = webhook_url
        self.base_url = "https://api.notebooklm.com/v1"  # 请确认这是正确的API端点
        
    def send_content(self, resources: list, text: str) -> str:
        """
        发送内容到 NotebookLM API
        
        Args:
            resources: 资源列表
            text: 提示文本
            
        Returns:
            str: 请求ID
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "resources": resources,
                "text": text,
                "webhook_url": self.webhook_url
            }
            
            response = requests.post(
                f"{self.base_url}/content",
                headers=headers,
                json=payload
            )
            
            response.raise_for_status()  # 如果响应状态码不是200，将引发异常
            
            data = response.json()
            return data.get("request_id")
            
        except requests.exceptions.RequestException as e:
            print(f"API请求错误: {str(e)}")
            return None 
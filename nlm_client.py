import requests
import json
import logging

class NotebookLMClient:
    def __init__(self, api_key: str, webhook_url: str):
        """初始化 NotebookLM 客户端"""
        if not api_key:
            raise ValueError("API key 不能为空")
        if not webhook_url:
            raise ValueError("Webhook URL 不能为空")
            
        self.api_key = api_key
        self.webhook_url = webhook_url
        self.base_url = "https://api.notebooklm.com/v1"
        
        # 设置日志
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("NotebookLMClient")
        
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
            # 验证输入
            if not resources:
                raise ValueError("资源列表不能为空")
            if not text:
                raise ValueError("提示文本不能为空")
                
            self.logger.info("准备发送请求到 NotebookLM API")
            self.logger.info(f"Resources: {json.dumps(resources, ensure_ascii=False)}")
            self.logger.info(f"Text: {text}")
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "resources": resources,
                "text": text,
                "webhook_url": self.webhook_url
            }
            
            self.logger.info(f"发送请求到: {self.base_url}/content")
            self.logger.debug(f"Headers: {headers}")
            self.logger.debug(f"Payload: {json.dumps(payload, ensure_ascii=False)}")
            
            response = requests.post(
                f"{self.base_url}/content",
                headers=headers,
                json=payload,
                timeout=30  # 添加超时设置
            )
            
            # 记录响应
            self.logger.info(f"收到响应状态码: {response.status_code}")
            self.logger.debug(f"响应内容: {response.text}")
            
            response.raise_for_status()
            
            data = response.json()
            request_id = data.get("request_id")
            
            if request_id:
                self.logger.info(f"成功获取请求ID: {request_id}")
                return request_id
            else:
                self.logger.error("响应中没有request_id")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"请求错误: {str(e)}")
            if hasattr(e.response, 'text'):
                self.logger.error(f"错误响应: {e.response.text}")
            return None
        except Exception as e:
            self.logger.error(f"未预期的错误: {str(e)}")
            return None
            
    def check_status(self, request_id: str) -> dict:
        """检查请求状态"""
        try:
            if not request_id:
                raise ValueError("Request ID 不能为空")
                
            self.logger.info(f"检查请求状态: {request_id}")
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"{self.base_url}/status/{request_id}",
                headers=headers,
                timeout=30
            )
            
            self.logger.info(f"状态检查响应码: {response.status_code}")
            self.logger.debug(f"状态检查响应: {response.text}")
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            self.logger.error(f"状态检查错误: {str(e)}")
            return None
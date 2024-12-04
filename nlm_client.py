import requests
import json
import logging
import re

class NotebookLMClient:
    def __init__(self, api_key: str, webhook_url: str):
        """初始化 NotebookLM 客户端"""
        if not api_key:
            raise ValueError("API key 不能为空")
        if not webhook_url:
            raise ValueError("Webhook URL 不能为空")
            
        self.api_key = api_key
        self.webhook_url = webhook_url
        self.base_url = "https://api.autocontentapi.com"
        
        # 设置日志
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("NotebookLMClient")
        
    def _convert_arxiv_url(self, url: str) -> list:
        """
        将arXiv URL转换为PDF和HTML URL
        
        Args:
            url: arXiv论文URL
            
        Returns:
            list: 包含PDF和HTML URL的资源列表
        """
        try:
            # 从URL中提取arXiv ID
            match = re.search(r'arxiv.org/abs/(\d+\.\d+)', url)
            if not match:
                self.logger.error(f"无法从URL中提取arXiv ID: {url}")
                return [{"content": url, "type": "website"}]
                
            arxiv_id = match.group(1)
            
            # 构建PDF和HTML URL
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
            html_url = f"https://arxiv.org/html/{arxiv_id}"
            
            return [
                {"content": pdf_url, "type": "website"},
                {"content": html_url, "type": "website"}
            ]
            
        except Exception as e:
            self.logger.error(f"转换arXiv URL时出错: {str(e)}")
            return [{"content": url, "type": "website"}]
        
    def send_content(self, resources: list, text: str) -> str:
        """
        发送内容到 AutoContent API
        
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
                
            self.logger.info("准备发送请求到 AutoContent API")
            
            # 处理资源URL
            processed_resources = []
            for resource in resources:
                if "arxiv.org/abs/" in resource["content"]:
                    processed_resources.extend(self._convert_arxiv_url(resource["content"]))
                else:
                    processed_resources.append(resource)
            
            self.logger.info(f"处理后的资源: {json.dumps(processed_resources, ensure_ascii=False)}")
            self.logger.info(f"Text: {text}")
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "resources": processed_resources,
                "text": text,
                "outputType": "audio",
                "webhook": {
                    "url": self.webhook_url
                }
            }
            
            self.logger.info(f"发送请求到: {self.base_url}/content/create")
            self.logger.debug(f"Headers: {headers}")
            self.logger.debug(f"Payload: {json.dumps(payload, ensure_ascii=False)}")
            
            response = requests.post(
                f"{self.base_url}/content/create",
                headers=headers,
                json=payload,
                timeout=30
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
                error_message = data.get("error_message")
                self.logger.error(f"响应中没有request_id，错误信息: {error_message}")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"请求错误: {str(e)}")
            if hasattr(e, 'response') and e.response:
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
            
            # 根据文档更新正确的 URL 格式
            status_url = f"{self.base_url}/content/status/{request_id}"
            
            self.logger.info(f"检查状态 URL: {status_url}")
            
            response = requests.get(
                status_url,
                headers=headers,
                timeout=30
            )
            
            self.logger.info(f"状态检查响应码: {response.status_code}")
            self.logger.debug(f"状态检查响应: {response.text}")
            
            response.raise_for_status()
            status_data = response.json()
            
            # 根据文档处理状态响应
            return {
                "status": status_data.get("status", 0),  # 0-100, 0表示排队中，100表示完成
                "updated_on": status_data.get("updated_on"),
                "audio_url": status_data.get("audio_url"),
                "error_message": status_data.get("error_message")
            }
            
        except Exception as e:
            self.logger.error(f"状态检查错误: {str(e)}")
            return None
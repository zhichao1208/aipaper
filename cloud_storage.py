import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
import os
import requests

class CloudStorage:
    def __init__(self, cloud_name: str, api_key: str, api_secret: str):
        """初始化 Cloudinary 配置"""
        # 验证参数
        if not all([cloud_name, api_key, api_secret]):
            raise ValueError("Cloudinary 配置参数不完整")
            
        self.cloud_name = cloud_name
        self.api_key = api_key
        self.api_secret = api_secret
        
        # 配置 Cloudinary
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True
        )
        
        # 验证配置
        try:
            cloudinary.api.ping()
            print("✓ Cloudinary 配置验证成功")
        except Exception as e:
            raise ValueError(f"Cloudinary 配置验证失败: {str(e)}")

    def upload_audio(self, file_path: str) -> dict:
        """
        上传音频文件到 Cloudinary
        
        Args:
            file_path: 本地音频文件路径
            
        Returns:
            dict: 包含上传结果的字典
        """
        try:
            # 验证文件
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {file_path}")
                
            if os.path.getsize(file_path) == 0:
                raise ValueError("文件大小为0")
                
            print(f"正在上传文件: {file_path}")
            
            # 使用官方的上传方法
            result = cloudinary.uploader.upload(
                file_path,
                resource_type="auto",  # 自动检测文件类型
                folder="aipaper_podcasts",  # 指定存储文件夹
                use_filename=True,  # 使用原始文件名
                unique_filename=True,  # 确保文件名唯一
                overwrite=True  # 如果文件已存在则覆盖
            )
            
            if result and result.get('secure_url'):
                return {
                    "success": True,
                    "url": result['secure_url'],
                    "public_id": result['public_id']
                }
            else:
                return {
                    "success": False,
                    "error": "上传失败，未获取到URL"
                }
                
        except Exception as e:
            print(f"上传过程中出错: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def download_audio(self, url: str, local_path: str) -> bool:
        """
        从URL下载音频文件到本地
        
        Args:
            url: 音频文件的URL
            local_path: 保存到本地的路径
            
        Returns:
            bool: 下载是否成功
        """
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()

            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            # 验证文件是否成功下载
            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                return True
            else:
                print("文件下载失败或文件大小为0")
                return False

        except Exception as e:
            print(f"下载过程中出错: {str(e)}")
            return False

    def delete_audio(self, public_id: str) -> bool:
        """
        删除 Cloudinary 上的音频文件
        
        Args:
            public_id: 文件的 public_id
            
        Returns:
            bool: 删除是否成功
        """
        try:
            response = cloudinary.uploader.destroy(public_id)
            return response['result'] == 'ok'
        except Exception as e:
            print(f"删除失败: {str(e)}")
            return False 
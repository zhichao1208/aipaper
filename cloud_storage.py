import cloudinary
import cloudinary.uploader
import cloudinary.api
import requests
import os

class CloudStorage:
    def __init__(self, cloud_name, api_key, api_secret):
        """初始化 Cloudinary 配置"""
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret
        )

    def upload_audio(self, file_path, resource_type="auto"):
        """上传音频文件到 Cloudinary"""
        try:
            response = cloudinary.uploader.upload(
                file_path,
                resource_type=resource_type,
                folder="aipaper_podcasts"
            )
            return {
                "success": True,
                "url": response['secure_url'],
                "public_id": response['public_id']
            }
        except Exception as e:
            print(f"上传失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def download_audio(self, url, output_path):
        """从 URL 下载音频文件"""
        try:
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                return True
            return False
        except Exception as e:
            print(f"下载失败: {str(e)}")
            return False

    def delete_audio(self, public_id):
        """删除 Cloudinary 上的音频文件"""
        try:
            response = cloudinary.uploader.destroy(public_id)
            return response['result'] == 'ok'
        except Exception as e:
            print(f"删除失败: {str(e)}")
            return False 
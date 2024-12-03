from cloud_storage import CloudStorage
import os
from dotenv import load_dotenv
import sys

def test_cloud_storage():
    # 在函数开始时定义 test_file
    test_file = "/Users/zhichaoli/Documents/GitHub/aipaper/temp_audio.wav"
    
    try:
        # 加载环境变量
        load_dotenv()
        
        # 打印调试信息
        print("Cloudinary 配置:")
        print(f"  CLOUD_NAME: {os.getenv('CLOUDINARY_CLOUD_NAME')}")
        print(f"  API_KEY: {os.getenv('CLOUDINARY_API_KEY')}")
        print(f"  API_SECRET: {os.getenv('CLOUDINARY_API_SECRET')}")
        
        # 验证环境变量
        required_vars = ['CLOUDINARY_CLOUD_NAME', 'CLOUDINARY_API_KEY', 'CLOUDINARY_API_SECRET']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            print("❌ 缺少必要的环境变量:")
            for var in missing_vars:
                print(f"  - {var}")
            sys.exit(1)
        
        # 初始化 CloudStorage
        print("\n1. 初始化 CloudStorage...")
        cloud_storage = CloudStorage(
            cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
            api_key=os.getenv('CLOUDINARY_API_KEY'),
            api_secret=os.getenv('CLOUDINARY_API_SECRET')
        )
        
        # 创建测试音频文件
        print("\n2. 创建测试文件...")
        with open(test_file, "wb") as f:
            f.write(b"test audio content")
        
        print(f"测试文件创建成功: {test_file}")
        print(f"文件大小: {os.path.getsize(test_file)} bytes")
        
        # 测试上传
        print("\n3. 测试上传...")
        result = cloud_storage.upload_audio(test_file)
        
        if result["success"]:
            print(f"✅ 上传成功！")
            print(f"URL: {result['url']}")
            print(f"Public ID: {result['public_id']}")
            
            # 测试下载
            print("\n4. 测试下载...")
            download_path = "downloaded_test.wav"
            if cloud_storage.download_audio(result["url"], download_path):
                print("✅ 下载成功！")
                print(f"下载文件大小: {os.path.getsize(download_path)} bytes")
            else:
                print("❌ 下载失败")
        else:
            print(f"❌ 上传失败: {result.get('error')}")
            
    except Exception as e:
        print(f"❌ 测试过程中出错: {str(e)}")
        
    finally:
        # 清理测试文件
        print("\n5. 清理测试文件...")
        if os.path.exists(test_file):
            os.remove(test_file)
            print(f"已删除: {test_file}")
        if os.path.exists("downloaded_test.wav"):
            os.remove("downloaded_test.wav")
            print(f"已删除: downloaded_test.wav")

if __name__ == "__main__":
    test_cloud_storage() 
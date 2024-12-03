import os
from dotenv import load_dotenv
from cloud_storage import CloudStorage
import wave
import numpy as np

def create_test_audio_file(filename: str, duration_seconds: float = 1.0):
    """创建一个有效的 WAV 测试音频文件"""
    # 设置参数
    sample_rate = 44100  # 采样率
    frequency = 440  # 频率 (A4 音符)
    
    # 生成音频数据
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds))
    data = np.sin(2 * np.pi * frequency * t)
    scaled = np.int16(data * 32767)
    
    # 创建 WAV 文件
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(1)  # 单声道
        wav_file.setsampwidth(2)  # 2 bytes per sample
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(scaled.tobytes())

def test_cloudinary():
    """测试 Cloudinary 的上传和下载功能"""
    # 加载环境变量
    load_dotenv()
    
    # 验证环境变量
    required_vars = ['CLOUDINARY_CLOUD_NAME', 'CLOUDINARY_API_KEY', 'CLOUDINARY_API_SECRET']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("❌ 缺少必要的环境变量:")
        for var in missing_vars:
            print(f"  - {var}")
        return
    
    try:
        # 初始化 CloudStorage
        print("\n1. 初始化 CloudStorage...")
        cloud_storage = CloudStorage(
            cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
            api_key=os.getenv('CLOUDINARY_API_KEY'),
            api_secret=os.getenv('CLOUDINARY_API_SECRET')
        )
        
        # 创建测试文件
        test_file = "test_audio.wav"
        print("\n2. 创建测试音频文件...")
        create_test_audio_file(test_file)
        
        if os.path.exists(test_file):
            print(f"✓ 测试文件创建成功: {test_file}")
            print(f"✓ 文件大小: {os.path.getsize(test_file)} bytes")
            
            # 测试上传
            print("\n3. 测试上传...")
            upload_result = cloud_storage.upload_audio(test_file)
            
            if upload_result["success"]:
                print("✓ 上传成功！")
                print(f"URL: {upload_result['url']}")
                print(f"Public ID: {upload_result['public_id']}")
                
                # 测试下载
                print("\n4. 测试下载...")
                download_path = "downloaded_test.wav"
                if cloud_storage.download_audio(upload_result["url"], download_path):
                    print("✓ 下载成功！")
                    print(f"下载文件大小: {os.path.getsize(download_path)} bytes")
                    
                    # 测试删除
                    print("\n5. 测试删除...")
                    if cloud_storage.delete_audio(upload_result["public_id"]):
                        print("✓ 文件删除成功！")
                    else:
                        print("❌ 文件删除失败")
                else:
                    print("❌ 下载失败")
            else:
                print(f"❌ 上传失败: {upload_result.get('error')}")
                
        else:
            print("❌ 测试文件创建失败")
            
    except Exception as e:
        print(f"❌ 测试过程中出错: {str(e)}")
        
    finally:
        # 清理测试文件
        print("\n6. 清理测试文件...")
        for file in [test_file, "downloaded_test.wav"]:
            if os.path.exists(file):
                os.remove(file)
                print(f"✓ 已删除: {file}")

if __name__ == "__main__":
    test_cloudinary() 
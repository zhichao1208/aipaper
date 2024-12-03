import os
from dotenv import load_dotenv

def test_env():
    load_dotenv()
    
    # 检查 Cloudinary 配置
    cloudinary_vars = {
        'CLOUDINARY_CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME'),
        'CLOUDINARY_API_KEY': os.getenv('CLOUDINARY_API_KEY'),
        'CLOUDINARY_API_SECRET': os.getenv('CLOUDINARY_API_SECRET')
    }
    
    print("\n=== Cloudinary 环境变量检查 ===")
    for key, value in cloudinary_vars.items():
        if value:
            # 只显示前后4个字符，中间用***代替
            masked_value = value[:4] + '*' * (len(value)-8) + value[-4:] if len(value) > 8 else '****'
            print(f"✓ {key}: {masked_value}")
        else:
            print(f"✗ {key}: 未设置")

if __name__ == "__main__":
    test_env() 
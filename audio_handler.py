import requests
import soundfile as sf
import scipy.io.wavfile
import os
import numpy as np
from scipy import signal

class AudioHandler:
    @staticmethod
    def download_audio(audio_url, output_path):
        """下载音频文件"""
        try:
            response = requests.get(audio_url, stream=True)
            if response.status_code == 200:
                with open(output_path, 'wb') as audio_file:
                    for chunk in response.iter_content(chunk_size=1024):
                        audio_file.write(chunk)
                print(f"✓ 音频文件已下载到: {output_path}")
                return True
            else:
                print(f"❌ 下载失败，状态码: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 下载过程出错: {str(e)}")
            return False

    @staticmethod
    def convert_wav_to_mp3(wav_path, mp3_path, target_sr=22050):
        """
        使用 soundfile 和 scipy 将 WAV 转换为 MP3，并进行压缩
        
        Args:
            wav_path: WAV文件路径
            mp3_path: 输出的MP3文件路径
            target_sr: 目标采样率（默认22050Hz，可以降低文件大小）
        """
        try:
            # 读取 WAV 文件
            data, samplerate = sf.read(wav_path)
            
            # 确保数据是 float32 类型
            if data.dtype != np.float32:
                data = data.astype(np.float32)
            
            # 如果是立体声，转换为单声道
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)
            
            # 重采样到较低的采样率
            if samplerate != target_sr:
                samples = int(len(data) * target_sr / samplerate)
                data = signal.resample(data, samples)
            
            # 标准化音频
            data = data / np.max(np.abs(data))
            
            # 写入新的音频文件
            scipy.io.wavfile.write(mp3_path, target_sr, data)
            
            print(f"✓ 音频转换成功: {wav_path} -> {mp3_path}")
            print(f"  原始采样率: {samplerate}Hz")
            print(f"  压缩后采样率: {target_sr}Hz")
            print(f"  文件大小: {os.path.getsize(mp3_path) / (1024*1024):.2f}MB")
            return True
                
        except Exception as e:
            print(f"❌ 转换过程出错: {str(e)}")
            return False 
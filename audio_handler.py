import requests
import soundfile as sf

class AudioHandler:
    @staticmethod
    def download_audio(audio_url, output_path):
        response = requests.get(audio_url, stream=True)
        if response.status_code == 200:
            with open(output_path, 'wb') as audio_file:
                for chunk in response.iter_content(chunk_size=1024):
                    audio_file.write(chunk)
            print(f"Audio file downloaded and saved as {output_path}")
        else:
            print(f"Failed to download audio file, status code: {response.status_code}")

    @staticmethod
    def convert_wav_to_mp3(wav_path, mp3_path):
        data, samplerate = sf.read(wav_path)
        sf.write(mp3_path, data, samplerate, format='MP3')
        print(f"Audio file converted from {wav_path} to {mp3_path}") 
import requests
import os

class PodbeanUploader:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.auth_url = "https://api.podbean.com/v1/oauth/token"
        self.authorize_upload_url = "https://api.podbean.com/v1/files/uploadAuthorize"
        self.publish_url = "https://api.podbean.com/v1/episodes"
        self.access_token = self.get_access_token()

    def get_access_token(self):
        auth_data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        response = requests.post(self.auth_url, data=auth_data)
        if response.ok:
            token_info = response.json()
            print("Access token obtained successfully.")
            return token_info['access_token']
        else:
            print("Failed to get access token:", response.text)
            return None

    def authorize_file_upload(self, filename, file_path, content_type="audio/mpeg"):
        filesize = os.path.getsize(file_path)
        params = {
            'access_token': self.access_token,
            'filename': filename,
            'filesize': filesize,
            'content_type': content_type
        }
        headers = {
            'User-Agent': 'MyApp/1.2.3 (Example)'
        }
        response = requests.get(self.authorize_upload_url, headers=headers, params=params)
        if response.ok:
            return response.json()
        else:
            print("Failed to authorize file upload:", response.text)
            return None

    def upload_file_to_presigned_url(self, presigned_url, file_path):
        with open(file_path, 'rb') as file_data:
            headers = {'Content-Type': 'audio/mpeg'}
            response = requests.put(presigned_url, headers=headers, data=file_data)
            if response.status_code == 200:
                print("File uploaded successfully.")
                return True
            else:
                print("Failed to upload file:", response.text)
                return False

    def publish_episode(self, title, content, file_key, season_number=1, episode_number=1):
        data = {
            'access_token': self.access_token,
            'title': title,
            'content': content,
            'status': 'publish',
            'type': 'public',
            'media_key': file_key,
            'season_number': season_number,
            'episode_number': episode_number,
            'apple_episode_type': 'full',
            'content_explicit': 'clean'
        }

        headers = {
            'User-Agent': 'AI Paper+/1.0 (Example)'
        }

        response = requests.post(self.publish_url, headers=headers, data=data)
        if response.ok:
            print("Episode published successfully!")
            return response.json()
        else:
            print("Failed to publish episode:", response.text)
            return None 
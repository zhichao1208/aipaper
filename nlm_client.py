import requests

class NotebookLMClient:
    def __init__(self, api_token, webhook_url=None):
        self.api_url = 'https://api.autocontentapi.com/content/create'
        self.status_url = 'https://api.autocontentapi.com/content/status/'
        self.headers = {
            'Authorization': f'Bearer {api_token}',
            'accept': 'application/json',
            'Content-Type': 'application/json'
        }
        self.webhook_url = webhook_url

    def send_content(self, resources, text, output_type="audio"):
        data = {
            "resources": resources,
            "text": text,
            "outputType": output_type
        }
        if self.webhook_url:
            data["webhook"] = self.webhook_url  # 添加 webhook URL

        response = requests.post(self.api_url, headers=self.headers, json=data)
        if response.ok:
            result = response.json()
            print("Request sent successfully. Request ID:", result.get("request_id"))
            return result.get("request_id")
        else:
            print("Error:", response.text)
            return None

    def check_status(self, request_id):
        status_endpoint = f"{self.status_url}/{request_id}"
        response = requests.get(status_endpoint, headers=self.headers)
        if response.ok:
            status_data = response.json()
            print("Status:", status_data.get("status"))
            print("Updated On:", status_data.get("updated_on"))
            print("Error Message:", status_data.get("error_message"))
            print("Audio URL:", status_data.get("audio_url"))
            print("Response Text:", status_data.get("response_text"))
            return status_data
        else:
            print("Error checking status:", response.text)
            return None 
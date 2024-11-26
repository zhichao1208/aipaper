 rom flask import Flask, request

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    print("Received webhook notification:", data)
    # 处理通知，例如更新数据库或发送消息到 Streamlit
    return '', 200

if __name__ == '__main__':
    app.run(port=5000)
from flask import Flask, request, jsonify
import threading
import queue

app = Flask(__name__)
# 用于存储状态更新的队列
status_updates = queue.Queue()

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    print("收到 webhook 通知:", data)
    # 将状态更新放入队列
    status_updates.put(data)
    return jsonify({"status": "success"}), 200

@app.route('/status', methods=['GET'])
def get_status():
    # 非阻塞方式获取最新状态
    try:
        status = status_updates.get_nowait()
        return jsonify(status), 200
    except queue.Empty:
        return jsonify({"status": "no_updates"}), 404

def run_webhook_server():
    app.run(host='0.0.0.0', port=5000, debug=False)

def start_webhook_server():
    server_thread = threading.Thread(target=run_webhook_server)
    server_thread.daemon = True
    server_thread.start()
    return server_thread

if __name__ == '__main__':
    start_webhook_server()
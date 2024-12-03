from flask import Flask, request, jsonify
import threading
import queue
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WebhookServer")

app = Flask(__name__)
# 用于存储状态更新的队列
status_updates = queue.Queue()

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    处理来自 AutoContent API 的 webhook 通知
    
    预期的响应格式:
    {
        "id": "38fdb402-5409-4fcd-b7a4-6971918e9323",
        "requested_on": "2024-11-17T17:57:37.933",
        "status": 100,
        "updated_on": "2024-11-17T17:58:31.847",
        "request_json": "...",
        "error_message": null,
        "audio_url": "https://autocontentapi.com/audio/sample.wav",
        "response_text": null
    }
    """
    try:
        data = request.json
        logger.info(f"收到 webhook 通知: {data}")
        
        # 验证必要字段
        required_fields = ['id', 'status', 'updated_on']
        if not all(field in data for field in required_fields):
            logger.error("Webhook 数据缺少必要字段")
            return jsonify({"status": "error", "message": "Missing required fields"}), 400
            
        # 将状态更新放入队列
        status_updates.put({
            "request_id": data.get("id"),
            "status": data.get("status"),
            "updated_on": data.get("updated_on"),
            "audio_url": data.get("audio_url"),
            "error_message": data.get("error_message"),
            "response_text": data.get("response_text")
        })
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        logger.error(f"处理 webhook 请求时出错: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/status', methods=['GET'])
def get_status():
    """获取最新的处理状态"""
    try:
        status = status_updates.get_nowait()
        logger.info(f"返回状态更新: {status}")
        return jsonify(status), 200
    except queue.Empty:
        return jsonify({"status": "no_updates"}), 404

def run_webhook_server():
    """运行 webhook 服务器"""
    try:
        logger.info("启动 Webhook 服务器...")
        app.run(host='0.0.0.0', port=5000, debug=False)
    except Exception as e:
        logger.error(f"Webhook 服务器启动失败: {str(e)}")

def start_webhook_server():
    """在后台线程中启动 webhook 服务器"""
    server_thread = threading.Thread(target=run_webhook_server)
    server_thread.daemon = True
    server_thread.start()
    logger.info("Webhook 服务器线程已启动")
    return server_thread

if __name__ == '__main__':
    start_webhook_server()
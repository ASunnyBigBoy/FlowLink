from flask import Flask, render_template_string, Response, jsonify, request
import pyautogui
import cv2
import numpy as np
from PIL import ImageGrab
import threading
import time
import io
import base64
import json
import os
import qrcode

app = Flask(__name__)

# 存储最后一次屏幕截图
last_screenshot = None
screenshot_lock = threading.Lock()

# HTML界面模板
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>电脑屏幕查看</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: Arial, sans-serif; 
            background: #1a1a1a;
            color: white;
            padding: 20px;
        }
        .container { max-width: 100%; }
        h1 { 
            text-align: center; 
            margin-bottom: 20px;
            color: #4CAF50;
        }
        .control-panel {
            background: #2d2d2d;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            justify-content: center;
        }
        button {
            padding: 10px 20px;
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            transition: background 0.3s;
        }
        button:hover { background: #45a049; }
        button:active { transform: scale(0.98); }
        .screen-container {
            background: #000;
            border-radius: 10px;
            overflow: hidden;
            margin-top: 20px;
            text-align: center;
        }
        #screen {
            max-width: 100%;
            border-radius: 5px;
            cursor: pointer;
        }
        .info {
            background: #2d2d2d;
            padding: 10px;
            border-radius: 5px;
            margin-top: 10px;
            font-size: 14px;
        }
        .mode-selector {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
        }
        .mode-btn {
            flex: 1;
            background: #555;
        }
        .mode-btn.active {
            background: #4CAF50;
        }
        .quality-control {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 10px;
        }
        input[type="range"] {
            flex: 1;
        }
    </style>
</head>
<body>
    <div class="container">
        </div>
        
        <div class="control-panel">
            <div class="mode-selector">
                <button class="mode-btn active" onclick="setMode('stream')">实时流</button>
                <button class="mode-btn" onclick="setMode('screenshot')">截图模式</button>
            </div>
            
            <button onclick="captureScreen()">手动截图</button>
            <button onclick="toggleStream()">开始实时流</button>
            <button onclick="refreshScreen()">刷新</button>
            <button onclick="fullScreen()">全屏查看</button>
            
            <div class="quality-control">
                <label>质量:</label>
                <input type="range" id="quality" min="10" max="100" value="70" onchange="updateQuality()">
                <span id="quality-value">70%</span>
            </div>
        </div>
        
        <div class="screen-container">
            <img id="screen" src="" onclick="toggleFullscreen(this)" 
                 alt="电脑屏幕将显示在这里">
        </div>
        
        <div class="info">
            <p>点击图片可全屏，实时流模式会持续更新屏幕</p>
            <p>在图片上滑动可模拟鼠标移动，点击模拟鼠标点击</p>
        </div>
    </div>

    <script>
        let currentMode = 'stream';
        let streamInterval = null;
        let isStreaming = false;
        let quality = 70;
        let clickEnabled = true;
        let lastTouch = null;
        
        // 获取IP地址
        fetch('/get_ip')
            .then(r => r.json())
            .then(data => {
                document.getElementById('ip-address').textContent = data.ip;
            });
        
        function setMode(mode) {
            currentMode = mode;
            document.querySelectorAll('.mode-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');
            
            if (mode === 'screenshot' && isStreaming) {
                toggleStream();
            }
            
            if (mode === 'stream' && !isStreaming) {
                toggleStream();
            }
        }
        
        function toggleStream() {
            if (isStreaming) {
                clearInterval(streamInterval);
                document.querySelector('button[onclick="toggleStream()"]').textContent = '开始实时流';
                isStreaming = false;
            } else {
                document.querySelector('button[onclick="toggleStream()"]').textContent = '停止实时流';
                isStreaming = true;
                startStream();
            }
        }
        
        function startStream() {
            if (currentMode === 'stream') {
                updateScreen();
                streamInterval = setInterval(updateScreen, 100);
            }
        }
        
        function updateScreen() {
            const startTime = Date.now();
            const img = document.getElementById('screen');
            const timestamp = new Date().getTime();
            
            fetch(`/screen?mode=${currentMode}&q=${quality}&t=${timestamp}`)
                .then(response => response.blob())
                .then(blob => {
                    const url = URL.createObjectURL(blob);
                    img.src = url;
                    
                    // 更新延迟信息
                    const latency = Date.now() - startTime;
                    document.getElementById('latency').textContent = latency;
                    document.getElementById('last-update').textContent = 
                        new Date().toLocaleTimeString();
                })
                .catch(error => {
                    console.error('更新失败:', error);
                });
        }
        
        function captureScreen() {
            updateScreen();
        }
        
        function refreshScreen() {
            const timestamp = new Date().getTime();
            const img = document.getElementById('screen');
            img.src = `/screen?mode=screenshot&t=${timestamp}`;
        }
        
        function updateQuality() {
            quality = document.getElementById('quality').value;
            document.getElementById('quality-value').textContent = quality + '%';
        }
        
        function fullScreen() {
            const elem = document.getElementById('screen');
            if (elem.requestFullscreen) {
                elem.requestFullscreen();
            } else if (elem.webkitRequestFullscreen) {
                elem.webkitRequestFullscreen();
            }
        }
        
        function toggleFullscreen(img) {
            if (!document.fullscreenElement) {
                fullScreen();
            } else {
                if (document.exitFullscreen) {
                    document.exitFullscreen();
                }
            }
        }
        
        // 触摸控制
        const screenImg = document.getElementById('screen');
        
        screenImg.addEventListener('touchstart', function(e) {
            if (!clickEnabled) return;
            lastTouch = {x: e.touches[0].clientX, y: e.touches[0].clientY};
        });
        
        screenImg.addEventListener('touchmove', function(e) {
            e.preventDefault();
        });
        
        screenImg.addEventListener('touchend', function(e) {
            if (!clickEnabled || !lastTouch) return;
            
            const touch = e.changedTouches[0];
            const rect = screenImg.getBoundingClientRect();
            
            // 计算相对位置
            const x = (touch.clientX - rect.left) / rect.width;
            const y = (touch.clientY - rect.top) / rect.height;
            
            // 发送点击位置到服务器
            fetch('/click', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({x: x, y: y})
            });
            
            lastTouch = null;
        });
        
        // 键盘快捷键
        document.addEventListener('keydown', function(e) {
            if (e.key === ' ') {  // 空格键刷新
                updateScreen();
            } else if (e.key === 's') {  // s键切换流
                toggleStream();
            } else if (e.key === 'f') {  // f键全屏
                fullScreen();
            }
        });
        
        // 初始加载
        updateScreen();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    """主页面"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/get_ip')
def get_ip():
    """获取服务器IP地址"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except:
        ip = "127.0.0.1"
    return jsonify({'ip': ip, 'port': PORT})

def generate_screenshot():
    """生成屏幕截图"""
    while True:
        try:
            # 截取屏幕
            screenshot = ImageGrab.grab()
            
            # 转换为JPEG
            img_byte_arr = io.BytesIO()
            screenshot.save(img_byte_arr, format='JPEG', quality=85)
            img_byte_arr = img_byte_arr.getvalue()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + img_byte_arr + b'\r\n')
            
            time.sleep(0.1)  # 10FPS
        except Exception as e:
            print(f"截图错误: {e}")
            time.sleep(1)

@app.route('/screen')
def screen():
    """获取屏幕截图"""
    mode = request.args.get('mode', 'stream')
    quality = int(request.args.get('q', 70))
    
    try:
        # 截取屏幕
        screenshot = ImageGrab.grab()
        
        # 调整质量
        img_byte_arr = io.BytesIO()
        screenshot.save(img_byte_arr, format='JPEG', quality=max(10, min(100, quality)))
        img_bytes = img_byte_arr.getvalue()
        
        return Response(img_bytes, mimetype='image/jpeg')
    except Exception as e:
        print(f"截图失败: {e}")
        # 返回错误图片
        from PIL import Image, ImageDraw
        img = Image.new('RGB', (800, 600), color='red')
        d = ImageDraw.Draw(img)
        d.text((10, 10), f"截图失败: {str(e)}", fill='white')
        
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        return Response(img_byte_arr.getvalue(), mimetype='image/jpeg')

@app.route('/click', methods=['POST'])
def handle_click():
    """处理手机点击事件"""
    try:
        data = request.json
        x = data.get('x', 0)
        y = data.get('y', 0)
        
        # 获取屏幕尺寸
        import pyautogui
        screen_width, screen_height = pyautogui.size()
        
        # 计算实际坐标
        click_x = int(x * screen_width)
        click_y = int(y * screen_height)
        
        # 移动鼠标并点击
        pyautogui.moveTo(click_x, click_y, duration=0.1)
        pyautogui.click()
        
        return jsonify({'status': 'success', 'x': click_x, 'y': click_y})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/screen_video')
def screen_video():
    """视频流端点"""
    return Response(generate_screenshot(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/info')
def server_info():
    """服务器信息"""
    import platform
    import psutil
    
    info = {
        'system': platform.system(),
        'hostname': platform.node(),
        'cpu_usage': psutil.cpu_percent(),
        'memory_usage': psutil.virtual_memory().percent,
        'timestamp': time.time()
    }
    return jsonify(info)

def get_local_ip():
    """获取本地IP地址"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"
    
    
def generate_qr_code(url):
    """生成访问二维码"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        # 在控制台打印二维码
        qr.print_ascii()
        print("\n" + "="*50)
        
    except:
        pass


def main():
    # 配置
    PORT = 5000
    HOST = '0.0.0.0'  # 监听所有网络接口
    
    local_ip = get_local_ip()

    print("=" * 50)
    print(f"电脑本地访问: http://localhost:{PORT}")
    print(f"手机访问地址: http://{local_ip}:{PORT}")
    print(f"同一WiFi下的其他设备也可以访问")
    print("=" * 50)
    print("控制功能: 手机点击屏幕可控制电脑鼠标")
    print("按 Ctrl+C 停止服务器")
    print("=" * 50)
    time.sleep(2)
    # 建议
    print("\n安全建议：")
    print("1. 仅在需要时开启服务")
    print("2. 使用后立即关闭")
    print("3. 避免在公共WiFi使用")
    print("4. 不要在屏幕上显示敏感信息")
    time.sleep
    print("-" * 40)
    generate_qr_code(f"http://{local_ip}:{PORT}")
    
    # 启动服务器
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
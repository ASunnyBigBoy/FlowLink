
"""
局域网文件互传系统 - 电脑端服务器
功能：提供Web界面、文件上传下载、目录浏览
"""

import os
import json
import shutil
import socket
import threading
import time
from datetime import datetime
from pathlib import Path
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import webbrowser
import zipfile
import hashlib
import qrcode
from io import BytesIO
import base64
import subprocess
import tempfile

def show_qrcode_as_image(url, filepath=None):
    """
    生成二维码图片，并尝试用系统默认程序打开。
    
    Args:
        url: 要编码的网址
        filepath: 图片保存路径（可选，默认保存在临时目录）
    """
    # 1. 生成二维码
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # 2. 保存图片
    if filepath is None:
        # 保存到临时文件
        temp_dir = tempfile.gettempdir()
        filepath = os.path.join(temp_dir, "flowlink_qrcode.png")
    
    img.save(filepath)
    print(f"✓ 二维码已生成: {filepath}")
    print(f"链接: {url}")
    
    # 3. 尝试用系统默认程序打开图片
    try:
        if os.name == 'nt':  # Windows
            os.startfile(filepath)
        elif os.name == 'posix':  # macOS 或 Linux
            subprocess.run(['open', filepath] if sys.platform == 'darwin' else ['xdg-open', filepath], check=False)
        print("已尝试自动打开二维码图片，请用手机扫描。")
    except Exception as e:
        print(f"无法自动打开图片，请手动查看: {filepath}")
    
    return filepath

desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")

class FileTransferServer(BaseHTTPRequestHandler):
    """HTTP请求处理器，提供文件传输接口"""
    
    def __init__(self, *args, **kwargs):
        self.base_dir = Path(desktop_path) / "FilePasser"
        self.base_dir.mkdir(exist_ok=True)
        self.uploads_dir = self.base_dir / "uploads"
        self.uploads_dir.mkdir(exist_ok=True)
        
        self.shared_dir = self.base_dir / "shared"
        self.shared_dir.mkdir(exist_ok=True)
        
        self.downloads_dir = self.base_dir / "downloads"
        self.downloads_dir.mkdir(exist_ok=True)
        
        super().__init__(*args, **kwargs)
    
    def _send_response(self, status_code=200, content_type='application/json', data=None):
        """发送HTTP响应"""
        self.send_response(status_code)
        self.send_header('Content-Type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        if data is not None:
            if content_type == 'application/json':
                self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
            else:
                if isinstance(data, str):
                    self.wfile.write(data.encode('utf-8'))
                else:
                    self.wfile.write(data)
    
    def do_OPTIONS(self):
        """处理CORS预检请求"""
        self._send_response(200, 'application/json', {'status': 'ok'})
    
    def do_GET(self):
        """处理GET请求"""
        try:
            parsed_path = urllib.parse.urlparse(self.path)
            path = parsed_path.path
            
            # 默认路径返回Web界面
            if path == '/' or path == '/index.html':
                self._serve_web_interface()
            
            # 文件列表接口
            elif path == '/api/files':
                self._get_file_list()
            
            # 下载文件接口
            elif path.startswith('/api/download/'):
                self._download_file(parsed_path)
            
            # 获取服务器信息
            elif path == '/api/info':
                self._get_server_info()
            
            # 删除文件
            elif path.startswith('/api/delete/'):
                self._delete_file(parsed_path)
            
            # 清空文件夹
            elif path == '/api/clear':
                self._clear_directory(parsed_path)
            
            # 静态文件服务
            else:
                self._serve_static_file(path)
                
        except Exception as e:
            self._send_response(500, 'application/json', {
                'status': 'error',
                'message': str(e)
            })
    
    def do_POST(self):
        """处理POST请求（文件上传）"""
        try:
            if self.path == '/api/upload':
                self._handle_file_upload()
            elif self.path == '/api/mkdir':
                self._handle_mkdir()
            else:
                self._send_response(404, 'application/json', {
                    'status': 'error',
                    'message': '接口不存在'
                })
        except Exception as e:
            self._send_response(500, 'application/json', {
                'status': 'error',
                'message': str(e)
            })
    
    def do_DELETE(self):
        """处理DELETE请求"""
        try:
            parsed_path = urllib.parse.urlparse(self.path)
            if parsed_path.path.startswith('/api/delete/'):
                self._delete_file(parsed_path)
            else:
                self._send_response(404, 'application/json', {
                    'status': 'error',
                    'message': '接口不存在'
                })
        except Exception as e:
            self._send_response(500, 'application/json', {
                'status': 'error',
                'message': str(e)
            })
    
    def _serve_web_interface(self):
        """提供Web界面"""
        html_content = """
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>局域网文件互传系统</title>
            <style>
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }
                
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    padding: 20px;
                }
                
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                }
                
                header {
                    background: rgba(255, 255, 255, 0.9);
                    backdrop-filter: blur(10px);
                    border-radius: 20px;
                    padding: 30px;
                    margin-bottom: 20px;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                }
                
                h1 {
                    color: #333;
                    margin-bottom: 10px;
                    font-size: 2.5em;
                }
                
                .subtitle {
                    color: #666;
                    font-size: 1.1em;
                    margin-bottom: 20px;
                }
                
                .server-info {
                    display: flex;
                    gap: 20px;
                    flex-wrap: wrap;
                    margin-bottom: 20px;
                }
                
                .info-card {
                    background: #fff;
                    padding: 15px 20px;
                    border-radius: 12px;
                    flex: 1;
                    min-width: 200px;
                    box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                }
                
                .info-card h3 {
                    color: #333;
                    margin-bottom: 8px;
                    font-size: 1.1em;
                }
                
                .info-card p {
                    color: #666;
                    font-size: 0.9em;
                }
                
                .qrcode-section {
                    background: white;
                    padding: 20px;
                    border-radius: 12px;
                    text-align: center;
                    box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                }
                
                .qrcode-section h3 {
                    margin-bottom: 15px;
                    color: #333;
                }
                
                #qrcode {
                    width: 200px;
                    height: 200px;
                    margin: 0 auto 15px;
                }
                
                .url-display {
                    background: #f5f5f5;
                    padding: 10px;
                    border-radius: 8px;
                    font-family: monospace;
                    word-break: break-all;
                    font-size: 0.9em;
                }
                
                .main-content {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 20px;
                }
                
                @media (max-width: 768px) {
                    .main-content {
                        grid-template-columns: 1fr;
                    }
                }
                
                .card {
                    background: rgba(255, 255, 255, 0.9);
                    backdrop-filter: blur(10px);
                    border-radius: 20px;
                    padding: 25px;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                }
                
                .card h2 {
                    color: #333;
                    margin-bottom: 20px;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }
                
                .card h2 i {
                    font-size: 1.2em;
                }
                
                .upload-area {
                    border: 3px dashed #667eea;
                    border-radius: 12px;
                    padding: 40px 20px;
                    text-align: center;
                    cursor: pointer;
                    transition: all 0.3s;
                    background: rgba(102, 126, 234, 0.05);
                }
                
                .upload-area:hover {
                    background: rgba(102, 126, 234, 0.1);
                    border-color: #764ba2;
                }
                
                .upload-area i {
                    font-size: 3em;
                    color: #667eea;
                    margin-bottom: 15px;
                }
                
                .upload-area h3 {
                    color: #333;
                    margin-bottom: 10px;
                }
                
                .upload-area p {
                    color: #666;
                    font-size: 0.9em;
                    margin-bottom: 20px;
                }
                
                .upload-btn {
                    background: #667eea;
                    color: white;
                    border: none;
                    padding: 12px 30px;
                    border-radius: 25px;
                    cursor: pointer;
                    font-size: 1em;
                    transition: all 0.3s;
                }
                
                .upload-btn:hover {
                    background: #764ba2;
                    transform: translateY(-2px);
                }
                
                .file-list {
                    max-height: 400px;
                    overflow-y: auto;
                }
                
                .file-item {
                    display: flex;
                    align-items: center;
                    padding: 12px 15px;
                    border-bottom: 1px solid #eee;
                    transition: background 0.3s;
                }
                
                .file-item:hover {
                    background: #f8f9fa;
                }
                
                .file-icon {
                    width: 40px;
                    height: 40px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 8px;
                    margin-right: 15px;
                }
                
                .file-icon.folder {
                    background: #e3f2fd;
                    color: #1976d2;
                }
                
                .file-icon.file {
                    background: #f3e5f5;
                    color: #7b1fa2;
                }
                
                .file-icon.image {
                    background: #fff3e0;
                    color: #f57c00;
                }
                
                .file-icon.video {
                    background: #e8f5e9;
                    color: #388e3c;
                }
                
                .file-info {
                    flex: 1;
                }
                
                .file-name {
                    color: #333;
                    font-weight: 500;
                    margin-bottom: 5px;
                }
                
                .file-size {
                    color: #888;
                    font-size: 0.85em;
                }
                
                .file-actions {
                    display: flex;
                    gap: 10px;
                }
                
                .action-btn {
                    padding: 6px 12px;
                    border-radius: 6px;
                    border: none;
                    cursor: pointer;
                    font-size: 0.85em;
                    transition: all 0.3s;
                }
                
                .download-btn {
                    background: #4caf50;
                    color: white;
                }
                
                .download-btn:hover {
                    background: #388e3c;
                }
                
                .delete-btn {
                    background: #f44336;
                    color: white;
                }
                
                .delete-btn:hover {
                    background: #d32f2f;
                }
                
                .progress {
                    width: 100%;
                    background: #eee;
                    border-radius: 10px;
                    margin-top: 20px;
                    overflow: hidden;
                }
                
                .progress-bar {
                    width: 0%;
                    height: 8px;
                    background: linear-gradient(90deg, #4caf50, #8bc34a);
                    transition: width 0.3s;
                }
                
                .upload-stats {
                    display: flex;
                    justify-content: space-between;
                    margin-top: 10px;
                    color: #666;
                    font-size: 0.9em;
                }
                
                .status {
                    padding: 8px 15px;
                    border-radius: 20px;
                    font-size: 0.9em;
                    display: inline-block;
                }
                
                .status.success {
                    background: #e8f5e9;
                    color: #2e7d32;
                }
                
                .status.error {
                    background: #ffebee;
                    color: #c62828;
                }
                
                .status.warning {
                    background: #fff3e0;
                    color: #ef6c00;
                }
                
                .operations {
                    display: flex;
                    gap: 10px;
                    margin-top: 20px;
                }
                
                .btn {
                    padding: 10px 20px;
                    border-radius: 8px;
                    border: none;
                    cursor: pointer;
                    font-weight: 500;
                    transition: all 0.3s;
                }
                
                .btn-primary {
                    background: #667eea;
                    color: white;
                }
                
                .btn-primary:hover {
                    background: #764ba2;
                }
                
                .btn-secondary {
                    background: #f5f5f5;
                    color: #333;
                }
                
                .btn-secondary:hover {
                    background: #e0e0e0;
                }
                
                .btn-danger {
                    background: #f44336;
                    color: white;
                }
                
                .btn-danger:hover {
                    background: #d32f2f;
                }
                
                .empty-state {
                    text-align: center;
                    padding: 40px 20px;
                    color: #999;
                }
                
                .empty-state i {
                    font-size: 3em;
                    margin-bottom: 15px;
                }
                
                .mobile-only {
                    display: none;
                }
                
                @media (max-width: 768px) {
                    .mobile-only {
                        display: block;
                    }
                    
                    header {
                        padding: 20px;
                    }
                    
                    h1 {
                        font-size: 1.8em;
                    }
                    
                    .card {
                        padding: 20px;
                    }
                }
            </style>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        </head>
        <body>
            <div class="container">
                <header>
                    <h1><i class="fas fa-exchange-alt"></i> 局域网文件互传系统</h1>
                    <p class="subtitle">在电脑和手机之间轻松传输文件</p>
                    
                    <div class="server-info">
                        <div class="info-card">
                            <h3><i class="fas fa-server"></i> 服务器状态</h3>
                            <p id="serverStatus">正在连接...</p>
                        </div>
                        <div class="info-card">
                            <h3><i class="fas fa-folder-open"></i> 存储目录</h3>
                            <p id="storagePath">正在获取...</p>
                        </div>
                        <div class="info-card">
                            <h3><i class="fas fa-sd-card"></i> 存储空间</h3>
                            <p id="storageSpace">正在获取...</p>
                        </div>
                    </div>
                    
                    <div class="qrcode-section">
                        <h3><i class="fas fa-mobile-alt"></i> 手机扫码访问</h3>
                        <div id="qrcode"></div>
                        <p>或访问网址：</p>
                        <div class="url-display" id="serverUrl">正在获取...</div>
                    </div>
                </header>
                
                <div class="main-content">
                    <div class="card">
                        <h2><i class="fas fa-upload"></i> 上传文件</h2>
                        <div class="upload-area" id="uploadArea">
                            <i class="fas fa-cloud-upload-alt"></i>
                            <h3>拖放文件到此处</h3>
                            <p>或点击选择文件</p>
                            <button class="upload-btn" onclick="document.getElementById('fileInput').click()">
                                选择文件
                            </button>
                            <input type="file" id="fileInput" multiple style="display: none" onchange="handleFileSelect()">
                            
                            <div id="filePreview" style="margin-top: 20px;"></div>
                        </div>
                        
                        <div class="progress" id="uploadProgress" style="display: none;">
                            <div class="progress-bar" id="progressBar"></div>
                        </div>
                        <div class="upload-stats" id="uploadStats" style="display: none;"></div>
                        
                        <div id="uploadStatus"></div>
                    </div>
                    
                    <div class="card">
                        <h2><i class="fas fa-folder"></i> 文件列表</h2>
                        <div class="operations">
                            <button class="btn btn-primary" onclick="loadFiles()">
                                <i class="fas fa-sync-alt"></i> 刷新
                            </button>
                            <button class="btn btn-secondary" onclick="createFolder()">
                                <i class="fas fa-folder-plus"></i> 新建文件夹
                            </button>
                            <button class="btn btn-danger" onclick="clearFiles()" style="margin-left: auto;">
                                <i class="fas fa-trash-alt"></i> 清空
                            </button>
                        </div>
                        
                        <div class="file-list" id="fileList">
                            <div class="empty-state">
                                <i class="fas fa-folder-open"></i>
                                <p>暂无文件</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="card" style="margin-top: 20px;">
                    <h2><i class="fas fa-info-circle"></i> 使用说明</h2>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px;">
                        <div>
                            <h3 style="color: #333; margin-bottom: 10px;"><i class="fas fa-mobile-alt"></i> 手机端访问</h3>
                            <p style="color: #666; line-height: 1.6; font-size: 0.9em;">
                                1. 确保手机和电脑在同一Wi-Fi网络<br>
                                2. 扫描上方二维码或输入网址<br>
                                3. 点击上传按钮选择文件<br>
                                4. 在文件列表中可以下载或删除文件
                            </p>
                        </div>
                        <div>
                            <h3 style="color: #333; margin-bottom: 10px;"><i class="fas fa-desktop"></i> 电脑端操作</h3>
                            <p style="color: #666; line-height: 1.6; font-size: 0.9em;">
                                1. 可以直接拖拽文件到上传区域<br>
                                2. 支持多文件同时上传<br>
                                3. 文件保存在：<span id="actualPath"></span><br>
                                4. 支持文件夹上传（自动压缩）
                            </p>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 文件操作确认对话框 -->
            <div id="confirmDialog" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center;">
                <div style="background: white; padding: 30px; border-radius: 12px; max-width: 400px; width: 90%;">
                    <h3 style="margin-bottom: 20px; color: #333;" id="confirmTitle"></h3>
                    <p style="margin-bottom: 25px; color: #666;" id="confirmMessage"></p>
                    <div style="display: flex; gap: 10px; justify-content: flex-end;">
                        <button class="btn btn-secondary" onclick="hideConfirmDialog()">取消</button>
                        <button class="btn btn-danger" onclick="confirmAction()">确定</button>
                    </div>
                </div>
            </div>
            
            <script src="https://cdn.jsdelivr.net/npm/qrcode@1.5.3/build/qrcode.min.js"></script>
            <script>
                let currentFile = null;
                let files = [];
                let serverUrl = '';
                
                // 初始化
                document.addEventListener('DOMContentLoaded', function() {
                    loadFiles();
                    getServerInfo();
                    
                    // 设置拖放上传
                    const uploadArea = document.getElementById('uploadArea');
                    uploadArea.addEventListener('dragover', (e) => {
                        e.preventDefault();
                        uploadArea.style.borderColor = '#764ba2';
                        uploadArea.style.background = 'rgba(102, 126, 234, 0.2)';
                    });
                    
                    uploadArea.addEventListener('dragleave', () => {
                        uploadArea.style.borderColor = '#667eea';
                        uploadArea.style.background = 'rgba(102, 126, 234, 0.05)';
                    });
                    
                    uploadArea.addEventListener('drop', (e) => {
                        e.preventDefault();
                        uploadArea.style.borderColor = '#667eea';
                        uploadArea.style.background = 'rgba(102, 126, 234, 0.05)';
                        
                        if (e.dataTransfer.items) {
                            const items = e.dataTransfer.items;
                            const files = [];
                            for (let i = 0; i < items.length; i++) {
                                if (items[i].kind === 'file') {
                                    files.push(items[i].getAsFile());
                                }
                            }
                            uploadFiles(files);
                        } else {
                            uploadFiles(e.dataTransfer.files);
                        }
                    });
                });
                
                // 获取服务器信息
                async function getServerInfo() {
                    try {
                        const response = await fetch('/api/info');
                        const data = await response.json();
                        
                        if (data.status === 'success') {
                            // 更新服务器信息
                            document.getElementById('serverStatus').innerHTML = 
                                `<span class="status success">运行中</span>`;
                            document.getElementById('storagePath').textContent = data.base_dir;
                            document.getElementById('actualPath').textContent = data.base_dir;
                            document.getElementById('storageSpace').textContent = data.free_space;
                            
                            // 更新URL和二维码
                            serverUrl = data.server_url;
                            document.getElementById('serverUrl').textContent = serverUrl;
                            
                            // 生成二维码
                            QRCode.toCanvas(document.getElementById('qrcode'), serverUrl, {
                                width: 200,
                                height: 200,
                                color: {
                                    dark: '#667eea',
                                    light: '#ffffff'
                                }
                            });
                        }
                    } catch (error) {
                        1
                    }
                }
                
                // 加载文件列表
                async function loadFiles() {
                    try {
                        const response = await fetch('/api/files');
                        const data = await response.json();
                        
                        if (data.status === 'success') {
                            files = data.files;
                            displayFiles(files);
                        }
                    } catch (error) {
                        console.error('加载文件失败:', error);
                        showMessage('加载文件失败: ' + error.message, 'error');
                    }
                }
                
                // 显示文件列表
                function displayFiles(files) {
                    const fileList = document.getElementById('fileList');
                    
                    if (files.length === 0) {
                        fileList.innerHTML = `
                            <div class="empty-state">
                                <i class="fas fa-folder-open"></i>
                                <p>暂无文件</p>
                            </div>
                        `;
                        return;
                    }
                    
                    let html = '';
                    files.forEach(file => {
                        const icon = getFileIcon(file.name, file.type);
                        const size = formatFileSize(file.size);
                        const date = new Date(file.modified).toLocaleString();
                        
                        html += `
                            <div class="file-item">
                                <div class="file-icon ${icon.type}">
                                    <i class="${icon.class}"></i>
                                </div>
                                <div class="file-info">
                                    <div class="file-name" title="${file.name}">${file.name}</div>
                                    <div class="file-size">${size} • ${date}</div>
                                </div>
                                <div class="file-actions">
                                    ${file.type === 'dir' ? '' : `
                                        <button class="action-btn download-btn" onclick="downloadFile('${file.name}')">
                                            <i class="fas fa-download"></i> 下载
                                        </button>
                                    `}
                                    <button class="action-btn delete-btn" onclick="deleteFile('${file.name}')">
                                        <i class="fas fa-trash"></i> 删除
                                    </button>
                                </div>
                            </div>
                        `;
                    });
                    
                    fileList.innerHTML = html;
                }
                
                // 获取文件图标
                function getFileIcon(filename, type) {
                    if (type === 'dir') {
                        return { class: 'fas fa-folder', type: 'folder' };
                    }
                    
                    const ext = filename.split('.').pop().toLowerCase();
                    const imageExts = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'];
                    const videoExts = ['mp4', 'avi', 'mov', 'mkv', 'wmv'];
                    
                    if (imageExts.includes(ext)) {
                        return { class: 'fas fa-image', type: 'image' };
                    } else if (videoExts.includes(ext)) {
                        return { class: 'fas fa-video', type: 'video' };
                    } else {
                        return { class: 'fas fa-file', type: 'file' };
                    }
                }
                
                // 格式化文件大小
                function formatFileSize(bytes) {
                    if (bytes === 0) return '0 B';
                    const k = 1024;
                    const sizes = ['B', 'KB', 'MB', 'GB'];
                    const i = Math.floor(Math.log(bytes) / Math.log(k));
                    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
                }
                
                // 选择文件
                function handleFileSelect() {
                    const fileInput = document.getElementById('fileInput');
                    uploadFiles(fileInput.files);
                }
                
                // 上传文件
                async function uploadFiles(fileList) {
                    if (fileList.length === 0) return;
                    
                    const formData = new FormData();
                    for (let i = 0; i < fileList.length; i++) {
                        formData.append('files', fileList[i]);
                    }
                    
                    const progressBar = document.getElementById('progressBar');
                    const uploadProgress = document.getElementById('uploadProgress');
                    const uploadStats = document.getElementById('uploadStats');
                    
                    uploadProgress.style.display = 'block';
                    uploadStats.style.display = 'flex';
                    
                    try {
                        const xhr = new XMLHttpRequest();
                        
                        xhr.upload.addEventListener('progress', (e) => {
                            if (e.lengthComputable) {
                                const percent = (e.loaded / e.total * 100).toFixed(2);
                                progressBar.style.width = percent + '%';
                                
                                const loaded = formatFileSize(e.loaded);
                                const total = formatFileSize(e.total);
                                uploadStats.innerHTML = `
                                    <span>${percent}%</span>
                                    <span>${loaded} / ${total}</span>
                                `;
                            }
                        });
                        
                        xhr.onload = function() {
                            if (xhr.status === 200) {
                                const response = JSON.parse(xhr.responseText);
                                if (response.status === 'success') {
                                    showMessage('上传成功！', 'success');
                                    loadFiles();
                                } else {
                                    showMessage('上传失败: ' + response.message, 'error');
                                }
                            } else {
                                showMessage('上传失败: HTTP ' + xhr.status, 'error');
                            }
                            
                            uploadProgress.style.display = 'none';
                            uploadStats.style.display = 'none';
                            progressBar.style.width = '0%';
                        };
                        
                        xhr.onerror = function() {
                            showMessage('上传失败: 网络错误', 'error');
                            uploadProgress.style.display = 'none';
                            uploadStats.style.display = 'none';
                            progressBar.style.width = '0%';
                        };
                        
                        xhr.open('POST', '/api/upload');
                        xhr.send(formData);
                        
                        // 重置文件输入
                        document.getElementById('fileInput').value = '';
                        
                    } catch (error) {
                        showMessage('上传失败: ' + error.message, 'error');
                        uploadProgress.style.display = 'none';
                        uploadStats.style.display = 'none';
                    }
                }
                
                // 下载文件
                function downloadFile(filename) {
                    window.open(`/api/download/${encodeURIComponent(filename)}`, '_blank');
                }
                
                // 删除文件
                function deleteFile(filename) {
                    currentFile = filename;
                    showConfirmDialog('删除文件', `确定要删除 "${filename}" 吗？`, 'delete');
                }
                
                // 清空文件
                function clearFiles() {
                    showConfirmDialog('清空文件夹', '确定要清空所有文件吗？此操作不可恢复！', 'clear');
                }
                
                // 创建文件夹
                function createFolder() {
                    const folderName = prompt('请输入文件夹名称:');
                    if (folderName && folderName.trim()) {
                        fetch('/api/mkdir', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ name: folderName.trim() })
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.status === 'success') {
                                showMessage('文件夹创建成功！', 'success');
                                loadFiles();
                            } else {
                                showMessage('创建失败: ' + data.message, 'error');
                            }
                        })
                        .catch(error => {
                            showMessage('创建失败: ' + error.message, 'error');
                        });
                    }
                }
                
                // 显示确认对话框
                function showConfirmDialog(title, message, action) {
                    document.getElementById('confirmTitle').textContent = title;
                    document.getElementById('confirmMessage').textContent = message;
                    document.getElementById('confirmDialog').style.display = 'flex';
                    document.getElementById('confirmDialog').dataset.action = action;
                }
                
                // 隐藏确认对话框
                function hideConfirmDialog() {
                    document.getElementById('confirmDialog').style.display = 'none';
                    currentFile = null;
                }
                
                // 确认操作
                function confirmAction() {
                    const action = document.getElementById('confirmDialog').dataset.action;
                    const url = action === 'clear' ? '/api/clear' : `/api/delete/${encodeURIComponent(currentFile)}`;
                    
                    fetch(url, { method: action === 'clear' ? 'GET' : 'DELETE' })
                        .then(response => response.json())
                        .then(data => {
                            if (data.status === 'success') {
                                showMessage(action === 'clear' ? '已清空所有文件' : '文件删除成功', 'success');
                                loadFiles();
                            } else {
                                showMessage('操作失败: ' + data.message, 'error');
                            }
                        })
                        .catch(error => {
                            showMessage('操作失败: ' + error.message, 'error');
                        });
                    
                    hideConfirmDialog();
                }
                
                // 显示消息
                function showMessage(message, type) {
                    const statusDiv = document.getElementById('uploadStatus');
                    statusDiv.innerHTML = `
                        <div class="status ${type}">
                            ${message}
                        </div>
                    `;
                    
                    setTimeout(() => {
                        statusDiv.innerHTML = '';
                    }, 3000);
                }
                
                // 定期刷新文件列表
                setInterval(loadFiles, 30000); // 每30秒刷新一次
            </script>
        </body>
        </html>
        """
        
        self._send_response(200, 'text/html; charset=utf-8', html_content)
    
    def _serve_static_file(self, path):
        """提供静态文件（主要用于CSS、JS等）"""
        static_dir = Path(__file__).parent / 'static'
        file_path = static_dir / path.lstrip('/')
        
        if file_path.exists() and file_path.is_file():
            mime_type, _ = mimetypes.guess_type(str(file_path))
            with open(file_path, 'rb') as f:
                self._send_response(200, mime_type or 'application/octet-stream', f.read())
        else:
            self._send_response(404, 'application/json', {
                'status': 'error',
                'message': '文件不存在'
            })
    
    def _get_file_list(self):
        """获取文件列表"""
        try:
            files = []
            shared_path = self.shared_dir
            
            for item in shared_path.iterdir():
                stat = item.stat()
                files.append({
                    'name': item.name,
                    'size': stat.st_size,
                    'type': 'dir' if item.is_dir() else 'file',
                    'modified': stat.st_mtime,
                    'created': stat.st_ctime
                })
            
            # 按修改时间排序，最新的在前面
            files.sort(key=lambda x: x['modified'], reverse=True)
            
            self._send_response(200, 'application/json', {
                'status': 'success',
                'files': files
            })
        except Exception as e:
            self._send_response(500, 'application/json', {
                'status': 'error',
                'message': str(e)
            })
    
    def _handle_file_upload(self):
        """处理文件上传"""
        try:
            content_type = self.headers.get('content-type', '')
            
            if not content_type.startswith('multipart/form-data'):
                self._send_response(400, 'application/json', {
                    'status': 'error',
                    'message': '无效的请求类型'
                })
                return
            
            # 解析multipart/form-data
            content_length = int(self.headers.get('content-length', 0))
            if content_length == 0:
                self._send_response(400, 'application/json', {
                    'status': 'error',
                    'message': '没有上传文件'
                })
                return
            
            # 简化处理：实际应该解析multipart数据
            # 这里使用简单的实现
            import cgi
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={'REQUEST_METHOD': 'POST'}
            )
            
            uploaded_files = []
            for field in form.list:
                if field.filename:
                    # 保存文件
                    file_path = self.shared_dir / field.filename
                    with open(file_path, 'wb') as f:
                        f.write(field.file.read())
                    uploaded_files.append(field.filename)
            
            self._send_response(200, 'application/json', {
                'status': 'success',
                'message': f'成功上传 {len(uploaded_files)} 个文件',
                'files': uploaded_files
            })
            
        except Exception as e:
            self._send_response(500, 'application/json', {
                'status': 'error',
                'message': str(e)
            })
    
    def _download_file(self, parsed_path):
        """处理文件下载"""
        try:
            # 获取文件名
            filename = urllib.parse.unquote(parsed_path.path.replace('/api/download/', ''))
            file_path = self.shared_dir / filename
            
            if not file_path.exists():
                self._send_response(404, 'application/json', {
                    'status': 'error',
                    'message': '文件不存在'
                })
                return
            
            # 设置响应头
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Content-Length', str(file_path.stat().st_size))
            self.end_headers()
            
            # 发送文件内容
            with open(file_path, 'rb') as f:
                shutil.copyfileobj(f, self.wfile)
                
        except Exception as e:
            self._send_response(500, 'application/json', {
                'status': 'error',
                'message': str(e)
            })
    
    def _delete_file(self, parsed_path):
        """删除文件"""
        try:
            filename = urllib.parse.unquote(parsed_path.path.replace('/api/delete/', ''))
            file_path = self.shared_dir / filename
            
            if not file_path.exists():
                self._send_response(404, 'application/json', {
                    'status': 'error',
                    'message': '文件不存在'
                })
                return
            
            if file_path.is_dir():
                shutil.rmtree(file_path)
            else:
                file_path.unlink()
            
            self._send_response(200, 'application/json', {
                'status': 'success',
                'message': '文件删除成功'
            })
            
        except Exception as e:
            self._send_response(500, 'application/json', {
                'status': 'error',
                'message': str(e)
            })
    
    def _clear_directory(self, parsed_path):
        """清空共享目录"""
        try:
            # 删除所有文件和文件夹
            for item in self.shared_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            
            self._send_response(200, 'application/json', {
                'status': 'success',
                'message': '目录已清空'
            })
            
        except Exception as e:
            self._send_response(500, 'application/json', {
                'status': 'error',
                'message': str(e)
            })
    
    def _handle_mkdir(self):
        """创建文件夹"""
        try:
            content_length = int(self.headers.get('content-length', 0))
            if content_length == 0:
                self._send_response(400, 'application/json', {
                    'status': 'error',
                    'message': '请求体为空'
                })
                return
            
            data = json.loads(self.rfile.read(content_length))
            folder_name = data.get('name', '').strip()
            
            if not folder_name:
                self._send_response(400, 'application/json', {
                    'status': 'error',
                    'message': '文件夹名称不能为空'
                })
                return
            
            folder_path = self.shared_dir / folder_name
            folder_path.mkdir(exist_ok=True)
            
            self._send_response(200, 'application/json', {
                'status': 'success',
                'message': '文件夹创建成功'
            })
            
        except Exception as e:
            self._send_response(500, 'application/json', {
                'status': 'error',
                'message': str(e)
            })
    
    def _get_server_info(self):
        """获取服务器信息"""
        try:
            # 获取本机IP地址
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            
            # 获取存储空间信息
            total, used, free = shutil.disk_usage(self.base_dir)
            
            self._send_response(200, 'application/json', {
                'status': 'success',
                'hostname': hostname,
                'ip_address': ip_address,
                'port': self.server.server_address[1],
                'server_url': f'http://{ip_address}:{self.server.server_address[1]}',
                'base_dir': str(self.base_dir),
                'total_space': self._format_bytes(total),
                'used_space': self._format_bytes(used),
                'free_space': self._format_bytes(free),
                'timestamp': time.time(),
                'uptime': time.time() - self.server.start_time if hasattr(self.server, 'start_time') else 0
            })
            
        except Exception as e:
            self._send_response(500, 'application/json', {
                'status': 'error',
                'message': str(e)
            })
    
    def _format_bytes(self, bytes):
        """格式化字节大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes < 1024.0:
                return f"{bytes:.2f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.2f} PB"


def get_available_port(start_port=8000, end_port=8100):
    """获取可用的端口号"""
    for port in range(start_port, end_port + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    return start_port  # 如果都不可用，返回起始端口


def get_local_ip():
    """获取本机局域网IP地址"""
    try:
        # 创建一个UDP套接字
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 连接到一个公共DNS服务器
        s.connect(("8.8.8.8", 80))
        ip_address = s.getsockname()[0]
        s.close()
        return ip_address
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
    """主函数"""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║                局域网文件互传系统 v1.0                   ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # 获取可用端口
    port = get_available_port(8000, 8100)
    ip_address = get_local_ip()
    url = f"http://{ip_address}:{port}"
    
    print(f"服务器启动中...")
    print(f"文件存储目录: {Path(desktop_path) / 'FilePasser'}")
    print(f"访问地址: {url}")
    print("在手机浏览器中打开以上地址或扫码即可访问")
    print("请确保手机和电脑在同一Wi-Fi网络")
    print(f"局域网内其他设备可访问: {url}")
    print("\n" + "="*50)

    time.sleep(2)
    print("文件将保存在桌面上的 \'FilePasser\' 文件夹中。\n")
    time.sleep(3)
    # 生成二维码
    show_qrcode_as_image(url)
    try:
        # 启动HTTP服务器
        server_address = ('0.0.0.0', port)
        httpd = HTTPServer(server_address, FileTransferServer)
        httpd.start_time = time.time()
        
        print(f"服务器已启动!")
        print("\n按 Ctrl+C 停止服务器")
        print("="*50)
        # 尝试在默认浏览器中打开
        try:
            webbrowser.open(f"http://localhost:{port}")
        except:
            pass
        
        # 启动服务器
        httpd.serve_forever()
        
    except KeyboardInterrupt:
        print("\n\n服务器正在停止...")
        print("感谢使用！")
    except Exception as e:
        print(f"\n启动服务器失败: {e}")
        print("可能的原因:")
        print("  1. 端口被占用，请检查是否有其他程序在使用端口 {port}")
        print("  2. 防火墙设置，请确保允许端口 {port} 的访问")
        print("  3. 没有管理员权限（如果需要使用1024以下端口）")


if __name__ == "__main__":
    main()
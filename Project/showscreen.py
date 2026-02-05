import cv2
import subprocess
import numpy as np
import tempfile
import os
import time
import threading
from queue import Queue, Empty

class ScreenCaptureThread(threading.Thread):
    def __init__(self, target_width=480, max_queue_size=2):
        threading.Thread.__init__(self)
        self.target_width = target_width
        self.frame_queue = Queue(maxsize=max_queue_size)
        self.running = True
        self.daemon = True
        
    def run(self):
        while self.running:
            try:
                frame = self.get_screenshot_with_size(self.target_width)
                if frame is not None:
                    # 如果队列已满，丢弃旧帧
                    if self.frame_queue.full():
                        try:
                            self.frame_queue.get_nowait()
                        except Empty:
                            pass
                    self.frame_queue.put(frame)
                # 短暂休眠避免过度占用CPU
                time.sleep(0.01)
            except Exception as e:
                time.sleep(0.1)
    
    def get_screenshot_with_size(self, width=480):
        """获取指定宽度的截图 - 优化分辨率以提高帧率"""
        try:
            # 获取设备分辨率
            result = subprocess.run(
                ["./platform-tools/adb.exe", "shell", "wm", "size"],
                capture_output=True, text=True, timeout=2
            )
            
            if "Physical size" in result.stdout:
                size_str = result.stdout.split(": ")[1].strip()
                w, h = map(int, size_str.split("x"))
                
                # 大幅降低分辨率以提高帧率 [1,7](@ref)
                scale = width / w
                height = int(h * scale)
                
                # 使用内存流避免文件IO
                screenshot_result = subprocess.run(
                    ["./platform-tools/adb.exe", "exec-out", "screencap", "-p"],
                    capture_output=True, timeout=2
                )
                
                if screenshot_result.returncode == 0:
                    # 直接从内存解码图像
                    img_array = np.frombuffer(screenshot_result.stdout, dtype=np.uint8)
                    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                    
                    if img is not None:
                        # 调整到目标分辨率 [1](@ref)
                        img = cv2.resize(img, (width, height))
                        return img
                        
            return None
        except Exception as e:
            return None
    
    def get_latest_frame(self):
        try:
            return self.frame_queue.get_nowait()
        except Empty:
            return None
    
    def stop(self):
        """停止线程"""
        self.running = False

def display_optimized_window(target_width=480, target_fps=15):
    """显示优化后的窗口"""
    cv2.namedWindow("Phone Screen", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Phone Screen", target_width, int(target_width * 0.6))
    capture_thread = ScreenCaptureThread(target_width=target_width)
    capture_thread.start()
    
    frame_count = 0
    start_time = time.time()
    last_fps_update = start_time
    
    try:
        while True:
            frame_start = time.time()
            
            # 从线程获取最新帧
            img = capture_thread.get_latest_frame()
            
            if img is not None:
                cv2.imshow("Phone Screen", img)
                
                # 计算帧率 [4](@ref)
                frame_count += 1
                current_time = time.time()
                elapsed = current_time - last_fps_update
                
                if elapsed >= 1.0:
                    fps = frame_count / elapsed
                    frame_count = 0
                    last_fps_update = current_time
                    
                    # 在窗口标题显示帧率
                    cv2.setWindowTitle("Phone Screen", 
                                     f"Phone Screen - FPS: {fps:.1f} - Res: {target_width}px")
            
            # 动态延迟控制以实现目标帧率 [7](@ref)
            elapsed_frame = time.time() - frame_start
            target_frame_time = 1.0 / target_fps
            sleep_time = max(0.001, target_frame_time - elapsed_frame)
            time.sleep(sleep_time)
            
            # 按q退出
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    finally:
        capture_thread.stop()
        capture_thread.join(timeout=1)
        cv2.destroyAllWindows()

def main():
    """主函数 - 优化分辨率和帧率设置"""
    # 测试不同分辨率找到最佳平衡点 [7](@ref)
    resolutions = [360, 480, 640]  # 从低到高测试
    print("请将手机连接到电脑并启用USB调试模式。")
    print("按q键退出显示窗口。\n")
    print("选择分辨率:")
    for i, res in enumerate(resolutions, 1):
        print(f"{i}. {res}p")
    
    try:
        choice = int(input("输入选择 (1-3): ")) - 1
        selected_width = resolutions[choice if 0 <= choice < len(resolutions) else 0]
    except:
        selected_width = 480  # 默认值
    
    # 设置目标帧率
    target_fps = 15  # 平衡流畅度和性能 [2](@ref)
    
    display_optimized_window(selected_width, target_fps)
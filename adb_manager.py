import os
import requests
import zipfile
import platform
import sys
from typing import Tuple
from math import floor

class ADBManager:
    """Windows 平台 ADB 工具管理器 - 使用国内镜像源"""
    
    def __init__(self):
        self.platform = "windows"
        self.adb_dir = "platform-tools"
        
    def get_download_url(self) -> str:
        """获取可用的 ADB 下载链接（国内镜像）"""
        # 多个备选镜像源，按顺序尝试
        mirrors = [
            # 清华大学镜像源
            "https://mirrors.tuna.tsinghua.edu.cn/github-release/google/adb-tools/v35.0.1/platform-tools-35.0.1-windows.zip",
            # 华为云镜像源
            "https://mirrors.huaweicloud.com/android/repository/platform-tools-latest-windows.zip",
            # 腾讯云镜像源（备用）
            "https://mirrors.cloud.tencent.com/android/repository/platform-tools-latest-windows.zip",
        ]
        return mirrors[0]  # 先尝试第一个
    
    def try_mirrors(self) -> str:
        """尝试多个镜像源，返回第一个可用的"""
        mirrors = [
            "https://mirrors.tuna.tsinghua.edu.cn/github-release/google/adb-tools/v35.0.1/platform-tools-35.0.1-windows.zip",
            "https://mirrors.huaweicloud.com/android/repository/platform-tools-latest-windows.zip",
        ]
        
        for mirror in mirrors:
            try:
                print(f"正在测试镜像源: {mirror[:50]}...")
                response = requests.head(mirror, timeout=5)
                if response.status_code == 200:
                    print(f"找到可用镜像源: {mirror}")
                    return mirror
            except:
                continue
        
        # 如果所有镜像都失败，返回Google官方源（可能访问不了）
        return "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
    
    def check_adb_exists(self) -> bool:
        """检查 ADB 是否已安装"""
        adb_path = os.path.join(self.adb_dir, "adb.exe")
        return os.path.exists(adb_path)
    
    def download_adb(self) -> bool:
        """从国内镜像下载并安装 ADB 工具（解决目录嵌套问题）"""
        if self.check_adb_exists():
            print("[Success] ADB 工具已存在")
            return True

        print("正在从国内镜像源下载 ADB 工具...")
        print("此工具遵循 Apache License 2.0")
        print("=" * 60)

        zip_path = None  # 确保变量在try块外定义
        
        try:
            # 获取可用的下载链接
            url = self.try_mirrors()
            print(f"下载链接: {url}")
            
            # 下载ZIP文件
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            # 定义临时ZIP文件路径
            zip_path = "platform-tools-temp.zip"
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            # 下载文件
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"\r下载进度: {floor(percent)}%", end='')
            
            print("\n[Success] 下载完成，正在解压并整理文件...")

            import shutil
            import zipfile

            # 1. 创建临时解压目录
            temp_extract_dir = "temp_extract_adb"
            if os.path.exists(temp_extract_dir):
                shutil.rmtree(temp_extract_dir)
            os.makedirs(temp_extract_dir, exist_ok=True)

            # 2. 解压到临时目录
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)

            # 3. 清理下载的临时ZIP文件
            os.remove(zip_path)
            zip_path = None  # 已清理，设为None避免重复清理

            # 4. 核心：寻找包含 adb.exe 的实际目录，并处理嵌套
            target_base_dir = self.adb_dir
            source_dir_to_move = None

            # 首先，检查临时目录下是否直接存在 adb.exe
            for item in os.listdir(temp_extract_dir):
                item_path = os.path.join(temp_extract_dir, item)
                if os.path.isfile(item_path) and item.lower() == 'adb.exe':
                    # 情况1: 文件直接解压在临时目录根下（少见）
                    source_dir_to_move = temp_extract_dir
                    break
                elif os.path.isdir(item_path):
                    # 检查此文件夹下是否有 adb.exe
                    for root, dirs, files in os.walk(item_path):
                        if 'adb.exe' in files:
                            source_dir_to_move = root
                            break
                    if source_dir_to_move:
                        break

            if not source_dir_to_move:
                print("[Error] 在下载的压缩包中未找到 adb.exe 文件")
                shutil.rmtree(temp_extract_dir, ignore_errors=True)
                return False

            # 5. 准备目标目录
            if os.path.exists(target_base_dir):
                shutil.rmtree(target_base_dir)
            os.makedirs(target_base_dir, exist_ok=True)

            # 6. 将找到的文件和目录移动到目标位置
            # 如果找到的源目录就是临时目录本身，则移动其所有内容
            if source_dir_to_move == temp_extract_dir:
                for item in os.listdir(temp_extract_dir):
                    s = os.path.join(temp_extract_dir, item)
                    d = os.path.join(target_base_dir, item)
                    if os.path.isdir(s):
                        shutil.move(s, d)
                    else:
                        shutil.copy2(s, d)
            else:
                # 否则，移动找到的目录下的所有内容
                for item in os.listdir(source_dir_to_move):
                    s = os.path.join(source_dir_to_move, item)
                    d = os.path.join(target_base_dir, item)
                    if os.path.isdir(s):
                        shutil.move(s, d)
                    else:
                        shutil.copy2(s, d)

            # 7. 清理临时目录
            shutil.rmtree(temp_extract_dir, ignore_errors=True)

            print(f"[Success] 文件已整理至: {target_base_dir}")

            # 8. 最终验证
            if self.check_adb_exists():
                print("[Success] ADB 工具安装与配置完成")
                return True
            else:
                print(f"[Error] 文件整理后，在路径 {os.path.abspath(os.path.join(target_base_dir, 'adb.exe'))} 仍未找到 adb.exe")
                return False

        except Exception as e:
            print(f"[Error]处理过程中发生错误: {str(e)[:200]}")
            # 清理可能残留的临时文件
            import traceback
            traceback.print_exc()  # 打印详细错误信息
            
            import shutil
            shutil.rmtree("temp_extract_adb", ignore_errors=True)
            if zip_path and os.path.exists(zip_path):
                os.remove(zip_path)
            return False
    
    def get_adb_path(self) -> str:
        """获取 ADB 可执行文件路径"""
        return os.path.join(self.adb_dir, "adb.exe")

def ensure_adb_available() -> Tuple[bool, str]:
    """
    确保 ADB 工具可用
    返回: (是否成功, ADB路径或错误信息)
    """
    adb_manager = ADBManager()
    
    if adb_manager.check_adb_exists():
        return True, adb_manager.get_adb_path()
    
    print("首次使用，需要下载 ADB 工具...")
    
    success = adb_manager.download_adb()
    
    if success:
        return True, adb_manager.get_adb_path()
    else:
        print("\n" + "=" * 60)
        print("自动下载失败，请按以下步骤手动操作：")
        print("1. 访问以下链接下载：")
        print("   https://mirrors.tuna.tsinghua.edu.cn/github-release/google/adb-tools/")
        print("2. 找到最新的 platform-tools-*-windows.zip 文件下载")
        print("3. 解压到本项目文件夹下的 'platform-tools' 目录")
        print("4. 重新运行程序")
        print("=" * 60)
        return False, "ADB 工具不可用"

# 添加手动下载指引
def manual_download_guide():
    """提供详细的手动下载指引"""
    print("=" * 70)
    print("手动下载 ADB 工具指引")
    print("=" * 70)
    print("\n如果自动下载失败，请按以下步骤操作：")
    print("\n方法一：通过国内镜像下载（推荐）")
    print("1. 访问清华大学镜像站：")
    print("   https://mirrors.tuna.tsinghua.edu.cn/github-release/google/adb-tools/")
    print("2. 找到最新的版本，如 platform-tools-35.0.1-windows.zip")
    print("3. 下载该文件")
    print("\n方法二：通过百度网盘下载（如无法访问上述链接）")
    print("1. 在百度网盘搜索：platform-tools-latest-windows.zip")
    print("2. 或使用分享链接（需自行搜索可用链接）")
    print("\n解压步骤：")
    print("1. 将下载的 ZIP 文件复制到项目文件夹")
    print("2. 右键解压到当前文件夹")
    print("3. 将解压出的文件夹重命名为 'platform-tools'")
    print("4. 确保 adb.exe 文件路径为: ./platform-tools/adb.exe")
    print("=" * 70)

def main():
    # 添加命令行参数支持
    if len(sys.argv) > 1 and sys.argv[1] == "--manual":
        manual_download_guide()
    else:
        success, result = ensure_adb_available()
        
        if success:
            print(f"\n[Success] 就绪！ADB 路径: {result}")
            print(f"   完整路径: {os.path.abspath(result)}")
        else:
            print(f"\n[Error] {result}")
            print("\n提示：运行 'python adb_manager.py --manual' 查看详细手动下载指引")
    
    # 暂停，方便查看输出
    input("\n按 Enter 键继续...")
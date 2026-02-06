import showscreen
import filepasser
import showPC

print("=== FlowLink流联 ===")
print("选择要运行的程序:")
print("1. 手机屏幕显示器 (ShowScreen)")
print("2. 文件传输器 (FilePasser)")
print("3. 手机查看电脑屏幕 (ShowPC)")
print("退出请按Enter键")
choice = input("请输入数字 (1 或 2 或 3): ")
print("若想要切换程序，请重新运行此脚本。")

if choice == '1':
    import adb_manager
    adb_manager.main()
    from time import sleep
    print("\n\n第一个窗口可能存在比例缩放问题,请叉掉电脑会自动重新打开一个新窗口.")
    sleep(2)  # 等待ADB准备就绪
    showscreen.main()
elif choice == '2':
    filepasser.main()
elif choice == '3':
    showPC.main()
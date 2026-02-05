import showscreen
import filepasser
import showPC

print("选择要运行的程序:")
print("1. 手机屏幕显示器 (ShowScreen)")
print("2. 文件传输器 (FilePasser)")
print("3. 手机查看电脑屏幕 (ShowPC)")
choice = input("请输入数字 (1 或 2 或 3): ")

if choice == '1':
    showscreen.main()
elif choice == '2':
    filepasser.main()
elif choice == '3':
    showPC.main()
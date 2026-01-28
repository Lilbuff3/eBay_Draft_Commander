
import os
import sys
import winshell
from pathlib import Path
from win32com.client import Dispatch

def create_desktop_shortcut():
    desktop = winshell.desktop()
    path = os.path.join(desktop, "eBay Commander Pro.lnk")
    
    target = sys.executable.replace("python.exe", "pythonw.exe")
    cwd = str(Path(__file__).parent.absolute())
    script = os.path.join(cwd, "draft_commander.py")
    
    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortcut(path)
    shortcut.TargetPath = target
    shortcut.Arguments = f'"{script}"'
    shortcut.WorkingDirectory = cwd
    shortcut.IconLocation = target
    shortcut.Description = "Launch eBay Draft Commander Pro (AI Powered)"
    shortcut.Save()
    
    print(f"✅ Shortcut created on Desktop: {path}")

if __name__ == "__main__":
    try:
        create_desktop_shortcut()
    except Exception as e:
        print(f"❌ Failed to create shortcut: {e}")
        input("Press Enter to close...")

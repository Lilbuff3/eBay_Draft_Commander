import os
import winshell
from win32com.client import Dispatch

def create_inbox_shortcut():
    desktop = winshell.desktop()
    path = os.path.join(desktop, "B.L.A.S.T. Inbox.lnk")
    target = r"c:\Users\adam\OneDrive\Documents\Desktop\Development\projects\ebay-draft-commander\inbox"
    
    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(path)
    shortcut.Targetpath = target
    shortcut.Description = "Drop item folders here"
    shortcut.save()
    
    print(f"Shortcut created at: {path}")

if __name__ == '__main__':
    try:
        create_inbox_shortcut()
    except Exception as e:
        print(f"Failed to create shortcut: {e}")

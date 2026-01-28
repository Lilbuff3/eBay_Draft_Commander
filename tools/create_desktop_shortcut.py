import os
import sys
import winshell
from win32com.client import Dispatch

def create_shortcut():
    desktop = winshell.desktop()
    path = os.path.join(desktop, "B.L.A.S.T. Commander.lnk")
    target = r"c:\Users\adam\OneDrive\Documents\Desktop\Development\projects\ebay-draft-commander\Run_Commander.bat"
    wDir = r"c:\Users\adam\OneDrive\Documents\Desktop\Development\projects\ebay-draft-commander"
    icon = r"c:\Users\adam\OneDrive\Documents\Desktop\Development\projects\ebay-draft-commander\frontend\public\favicon.ico" # Try to use an icon if available
    
    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(path)
    shortcut.Targetpath = target
    shortcut.WorkingDirectory = wDir
    # shortcut.IconLocation = icon
    shortcut.save()
    
    print(f"Shortcut created at: {path}")

if __name__ == '__main__':
    try:
        create_shortcut()
    except Exception as e:
        print(f"Failed to create shortcut: {e}")
        # Fallback without winshell if needed
        print("Try copying the file manually.")

# 📱 Mobile Access Guide

You can control Draft Commander from your phone!

## 1. Quick Start (Desktop)
Double-click **`Start_App.bat`** in the project folder.
This will:
1. Start the server.
2. Open the Dashboard in your browser.
3. Show the **QR Code** for mobile.

## 2. Mobile Connection
3. Scan it with your phone's camera.
4. Open the link to see the Mobile Dashboard.

## 2. Troubleshooting
If the page doesn't load on your phone:

**A. Firewall Blocking?**
Windows Firewall might block the connection. Run this **one-time command** in PowerShell as Administrator:
```powershell
New-NetFirewallRule -DisplayName "Draft Commander Mobile" -Direction Inbound -Program (Get-Command python).Source -Action Allow
```

**B. Wrong Network?**
Make sure your phone is on the **same Wi-Fi** as this computer.

## 3. "Install" the App
For the best experience:
1. Open the page in **Chrome** (Android) or **Sappari** (iOS).
2. Tap **Share** (iOS) or **Menu** (Android).
3. Tap **Add to Home Screen**.
4. Launch it from your home screen for a full-screen app experience.

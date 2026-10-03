# Android Wrapper for eBay Draft Commander

A native Android WebView wrapper application that packages eBay Draft Commander for Android phones and tablets, providing a full-screen, native-feeling mobile experience for sourcing and listing.

---

## Features

- **Full-Screen Immersive Experience:** No browser address bars or navigation controls eating vertical screen space.
- **Intelligent Connection Management:**
  - **Tailscale HTTPS (Default):** Connects to `https://tuf-2.taile466a6.ts.net/app/`.
  - **Local LAN Fallback:** Connects to `http://192.168.1.142:5000/app/`.
  - **Custom Address:** Support for any custom host/IP.
  - **Connection Health Check:** Built-in test ping (`/api/system/health`) to diagnose connection issues before reloading.
  - **Native Error Overlay:** If the connection drops or Tailscale is disconnected, a native recovery screen appears with "Retry" and "Server Settings" buttons instead of raw browser error pages.
- **Camera & Barcode Scanner Integration:**
  - Automatically grants HTML5 `getUserMedia` camera permissions for the **Sourcing** and **Books** barcode scanners without repeated browser permission prompts.
  - Seamless `<input type="file" accept="image/*" capture>` handling: opens native camera capture or gallery multi-picker.
- **Native Share Target (Share Photos from Gallery):**
  - Select 1 to 12 product photos in Google Photos, Samsung Gallery, or any camera app, tap **Share**, and choose **Draft Commander**.
  - Opens directly into the upload workflow (`#create`) with the photos ready for processing.
- **Native Bridge (`window.AndroidBridge`):**
  - **Haptic Feedback:** Direct access to Android system vibration engine (`vibrate(ms)`).
  - **Screen Wake Lock:** Prevents screen timeout during active scanning sessions (`setKeepScreenOn(true)`).
  - **API Token Auto-Injection:** Automatically populates `localStorage['dc-api-key']` if an API access token is configured in server settings.
- **Back Navigation:**
  - Properly integrates with Android system back gesture/button to navigate WebView history and prevent accidental app exits.

---

## Directory Structure

```
android/
  app/
    src/main/
      AndroidManifest.xml                 # Permissions, Share Target filters, FileProvider
      java/com/ebaydraftcommander/app/
        MainActivity.kt                  # Core WebView controller & lifecycle
        CommanderWebViewClient.kt        # Network routing, error capture, external links
        CommanderWebChromeClient.kt      # Camera permission grant, file chooser bridge
        NativeBridge.kt                  # @JavascriptInterface for haptics, wake lock, server mode
        ServerConfigManager.kt           # SharedPreferences for Tailscale / LAN / Custom URLs
      res/
        drawable/ & mipmap/              # App icons, splash background
        layout/
          activity_main.xml              # WebView + Progress bar + Error/Server setup view
          dialog_server_config.xml       # Server configuration dialog layout
        xml/
          file_paths.xml                 # Secure FileProvider paths for camera captures
          network_security_config.xml    # Cleartext allowed for LAN IPs, strict for external
    build.gradle.kts                     # App-level dependencies (AndroidX, Material)
  gradle/wrapper/                        # Gradle 9.1.0 wrapper
  build.gradle.kts                       # Root project build script
  settings.gradle.kts                    # Settings & repo definitions
  gradle.properties                      # JVM args & AndroidX flags
  local.properties                       # Android SDK location
```

---

## Building and Installing

### Prerequisites
- Java JDK 17 or higher (configured in PATH)
- Android SDK installed (`local.properties` points to SDK directory)
- Optional: USB debugging enabled on your Android phone, or an Android emulator

### Build Script (`scripts/build-android.ps1`)

The included PowerShell script automates building and deploying:

```powershell
# 1. Build Debug APK
.\scripts\build-android.ps1

# 2. Build, install to connected phone or running emulator, and launch
.\scripts\build-android.ps1 -Install -Run

# 3. Build Release APK
.\scripts\build-android.ps1 -Release
```

The compiled APK will be located at:
- **Debug:** `android/app/build/outputs/apk/debug/app-debug.apk`
- **Release:** `android/app/build/outputs/apk/release/app-release-unsigned.apk`

---

## Configuration & Server Modes

When launching the app for the first time:
1. It connects to **Tailscale HTTPS** (`https://tuf-2.taile466a6.ts.net/app/`) by default.
2. If connection fails, tap **Change Server** on the error screen.
3. Choose:
   - **Tailscale HTTPS:** For remote usage outside your home network (ensure Tailscale VPN toggle is ON on your phone).
   - **Local Network LAN:** `http://192.168.1.142:5000/app/` (when connected to home Wi-Fi).
   - **Custom Address:** Enter a custom IP or hostname.
4. If your server requires an API Access Token (`API_ACCESS_TOKEN`), enter it in the **API Access Token** field.
5. Tap **Test Connection** to verify server reachability.
6. Tap **Save** to reload the application.

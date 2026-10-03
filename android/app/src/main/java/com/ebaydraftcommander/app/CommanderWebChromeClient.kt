package com.ebaydraftcommander.app

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import android.webkit.PermissionRequest
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebView
import androidx.core.content.ContextCompat

class CommanderWebChromeClient(
    private val activity: MainActivity
) : WebChromeClient() {

    private var pendingPermissionRequest: PermissionRequest? = null

    override fun onProgressChanged(view: WebView?, newProgress: Int) {
        super.onProgressChanged(view, newProgress)
        activity.onProgressChanged(newProgress)
    }

    override fun onPermissionRequest(request: PermissionRequest?) {
        if (request == null) return

        val resources = request.resources
        val hasVideo = resources.contains(PermissionRequest.RESOURCE_VIDEO_CAPTURE)

        if (hasVideo) {
            val cameraPermission = ContextCompat.checkSelfPermission(
                activity,
                Manifest.permission.CAMERA
            )

            if (cameraPermission == PackageManager.PERMISSION_GRANTED) {
                request.grant(resources)
            } else {
                pendingPermissionRequest = request
                activity.requestCameraPermission { granted ->
                    if (granted) {
                        pendingPermissionRequest?.grant(pendingPermissionRequest?.resources)
                    } else {
                        pendingPermissionRequest?.deny()
                    }
                    pendingPermissionRequest = null
                }
            }
        } else {
            // For audio or other permissions
            request.grant(resources)
        }
    }

    override fun onPermissionRequestCanceled(request: PermissionRequest?) {
        super.onPermissionRequestCanceled(request)
        if (pendingPermissionRequest == request) {
            pendingPermissionRequest = null
        }
    }

    override fun onShowFileChooser(
        webView: WebView?,
        filePathCallback: ValueCallback<Array<Uri>>?,
        fileChooserParams: FileChooserParams?
    ): Boolean {
        if (filePathCallback == null || fileChooserParams == null) return false
        return activity.handleFileChooser(filePathCallback, fileChooserParams)
    }
}

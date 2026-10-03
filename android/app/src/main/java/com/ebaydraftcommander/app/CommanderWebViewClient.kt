package com.ebaydraftcommander.app

import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient

class CommanderWebViewClient(
    private val activity: MainActivity,
    private val serverConfigManager: ServerConfigManager
) : WebViewClient() {

    var shouldClearHistoryOnLoad: Boolean = false
    private var hasError = false

    override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
        val url = request?.url ?: return false
        val urlStr = url.toString()

        val baseUrl = Uri.parse(serverConfigManager.currentBaseUrl)

        // Internal navigation within the app host
        if (url.host.equals(baseUrl.host, ignoreCase = true)) {
            return false
        }

        // External URLs: open in system browser
        return try {
            val intent = Intent(Intent.ACTION_VIEW, url)
            activity.startActivity(intent)
            true
        } catch (_: Exception) {
            false
        }
    }

    override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
        super.onPageStarted(view, url, favicon)
        hasError = false
        activity.hideError()

        // Inject helper flags into page context
        val apiKey = serverConfigManager.apiKey
        val jsInject = buildString {
            append("window.isAndroidWrapper = true;")
            if (apiKey.isNotBlank()) {
                // Ensure API key is persisted in localStorage so apiFetch picks it up immediately
                append("try { localStorage.setItem('dc-api-key', '${apiKey.replace("'", "\\'")}'); } catch(e){}")
            }
        }
        view?.evaluateJavascript(jsInject, null)
    }

    override fun onPageFinished(view: WebView?, url: String?) {
        super.onPageFinished(view, url)
        if (shouldClearHistoryOnLoad) {
            shouldClearHistoryOnLoad = false
            view?.clearHistory()
        }
        if (!hasError) {
            activity.hideError()
        }
    }

    override fun onReceivedError(
        view: WebView?,
        request: WebResourceRequest?,
        error: WebResourceError?
    ) {
        super.onReceivedError(view, request, error)
        if (request?.isForMainFrame == true) {
            hasError = true
            val desc = error?.description?.toString() ?: "Network error"
            activity.showError(desc)
        }
    }
}

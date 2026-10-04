package com.ebaydraftcommander.app

import android.content.Context
import android.content.SharedPreferences
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

enum class ServerMode {
    LAN,
    TAILSCALE,
    CUSTOM
}

class ServerConfigManager(context: Context) {
    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    companion object {
        private const val PREFS_NAME = "dc_server_config"
        private const val KEY_MODE = "server_mode"
        private const val KEY_CUSTOM_URL = "custom_url"
        private const val KEY_API_KEY = "api_key"

        const val DEFAULT_TAILSCALE_URL = "https://tuf-2.taile466a6.ts.net/app/"
        const val DEFAULT_LAN_URL = "http://10.0.0.51:5000/app/"
        const val DEFAULT_EMULATOR_URL = "http://10.0.2.2:5000/app/"
        const val DEFAULT_API_KEY = "ontqp4YTQaejSUvViTdxaXkDRbmAmNyt"

        fun normalizeAppUrl(input: String): String {
            var raw = input.trim()
            if (raw.isBlank()) return DEFAULT_LAN_URL
            if (!raw.startsWith("http://", ignoreCase = true) && !raw.startsWith("https://", ignoreCase = true)) {
                raw = "http://$raw"
            }
            while (raw.endsWith("/") || raw.endsWith(".")) {
                raw = raw.dropLast(1)
            }
            if (raw.endsWith("/download/apk", ignoreCase = true)) {
                raw = raw.substring(0, raw.length - 13)
            } else if (raw.endsWith("/download.apk", ignoreCase = true)) {
                raw = raw.substring(0, raw.length - 13)
            } else if (raw.endsWith("/download", ignoreCase = true)) {
                raw = raw.substring(0, raw.length - 9)
            } else if (raw.endsWith("/api/system/health", ignoreCase = true)) {
                raw = raw.substring(0, raw.length - 18)
            } else if (raw.endsWith("/api", ignoreCase = true)) {
                raw = raw.substring(0, raw.length - 4)
            } else if (raw.endsWith("/app", ignoreCase = true)) {
                raw = raw.substring(0, raw.length - 4)
            }
            while (raw.endsWith("/") || raw.endsWith(".")) {
                raw = raw.dropLast(1)
            }
            return "$raw/app/"
        }
    }

    var serverMode: ServerMode
        get() {
            val modeStr = prefs.getString(KEY_MODE, ServerMode.LAN.name) ?: ServerMode.LAN.name
            return try {
                ServerMode.valueOf(modeStr)
            } catch (_: Exception) {
                ServerMode.LAN
            }
        }
        set(value) {
            prefs.edit().putString(KEY_MODE, value.name).apply()
        }

    var customUrl: String
        get() = prefs.getString(KEY_CUSTOM_URL, "") ?: ""
        set(value) {
            prefs.edit().putString(KEY_CUSTOM_URL, value.trim()).apply()
        }

    var apiKey: String
        get() {
            val key = prefs.getString(KEY_API_KEY, "") ?: ""
            return if (key.isNotBlank()) key else DEFAULT_API_KEY
        }
        set(value) {
            prefs.edit().putString(KEY_API_KEY, value.trim()).apply()
        }

    val currentBaseUrl: String
        get() {
            val raw = when (serverMode) {
                ServerMode.LAN -> DEFAULT_LAN_URL
                ServerMode.TAILSCALE -> DEFAULT_TAILSCALE_URL
                ServerMode.CUSTOM -> if (customUrl.isNotBlank()) customUrl else DEFAULT_LAN_URL
            }
            return normalizeAppUrl(raw)
        }

    fun resolveHealthCheckUrl(overrideUrl: String? = null): String {
        val appUrl = normalizeAppUrl(overrideUrl?.takeIf { it.isNotBlank() } ?: currentBaseUrl)
        val hostBase = if (appUrl.endsWith("/app/")) {
            appUrl.substring(0, appUrl.length - 5)
        } else {
            appUrl.trimEnd('/')
        }
        return "$hostBase/api/system/health"
    }

    val healthCheckUrl: String
        get() = resolveHealthCheckUrl()

    suspend fun testConnection(
        overrideUrl: String? = null,
        overrideApiKey: String? = null
    ): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        if (overrideUrl != null && overrideUrl.trim().isBlank()) {
            return@withContext Pair(false, "Server URL cannot be empty")
        }
        var conn: HttpURLConnection? = null
        try {
            val target = URL(resolveHealthCheckUrl(overrideUrl))
            val key = overrideApiKey?.takeIf { it.isNotBlank() } ?: apiKey
            conn = (target.openConnection() as HttpURLConnection).apply {
                connectTimeout = 5000
                readTimeout = 5000
                requestMethod = "GET"
                if (key.isNotBlank()) {
                    setRequestProperty("X-API-Key", key)
                }
            }
            val code = conn.responseCode
            if (code in 200..299) {
                Pair(true, "OK (HTTP $code)")
            } else if (code == 401 || code == 403) {
                Pair(false, "HTTP $code (Unauthorized: check API Key)")
            } else {
                Pair(false, "Server returned HTTP $code")
            }
        } catch (e: Exception) {
            Pair(false, e.localizedMessage ?: "Connection failed")
        } finally {
            try {
                conn?.disconnect()
            } catch (_: Exception) {}
        }
    }
}

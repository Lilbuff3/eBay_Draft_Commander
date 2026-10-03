package com.ebaydraftcommander.app

import android.content.Context
import android.content.SharedPreferences
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

enum class ServerMode {
    TAILSCALE,
    LAN,
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
        const val DEFAULT_LAN_URL = "http://192.168.1.142:5000/app/"
        const val DEFAULT_EMULATOR_URL = "http://10.0.2.2:5000/app/"
    }

    var serverMode: ServerMode
        get() {
            val modeStr = prefs.getString(KEY_MODE, ServerMode.TAILSCALE.name) ?: ServerMode.TAILSCALE.name
            return try {
                ServerMode.valueOf(modeStr)
            } catch (_: Exception) {
                ServerMode.TAILSCALE
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
        get() = prefs.getString(KEY_API_KEY, "") ?: ""
        set(value) {
            prefs.edit().putString(KEY_API_KEY, value.trim()).apply()
        }

    val currentBaseUrl: String
        get() {
            val raw = when (serverMode) {
                ServerMode.TAILSCALE -> DEFAULT_TAILSCALE_URL
                ServerMode.LAN -> DEFAULT_LAN_URL
                ServerMode.CUSTOM -> if (customUrl.isNotBlank()) customUrl else DEFAULT_TAILSCALE_URL
            }
            return if (raw.endsWith("/")) raw else "$raw/"
        }

    val healthCheckUrl: String
        get() {
            val base = currentBaseUrl.removeSuffix("app/").removeSuffix("/")
            return "$base/api/system/health"
        }

    suspend fun testConnection(): Pair<Boolean, String> = withContext(Dispatchers.IO) {
        try {
            val target = URL(healthCheckUrl)
            val conn = (target.openConnection() as HttpURLConnection).apply {
                connectTimeout = 5000
                readTimeout = 5000
                requestMethod = "GET"
                if (apiKey.isNotBlank()) {
                    setRequestProperty("X-API-Key", apiKey)
                }
            }
            val code = conn.responseCode
            if (code in 200..299) {
                Pair(true, "OK (HTTP $code)")
            } else {
                Pair(false, "Server returned HTTP $code")
            }
        } catch (e: Exception) {
            Pair(false, e.localizedMessage ?: "Connection failed")
        }
    }
}

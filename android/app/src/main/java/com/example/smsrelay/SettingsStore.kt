package com.example.smsrelay

import android.content.Context

data class RelaySettings(
    val serverUrl: String,
    val bearerToken: String,
    val clientId: String,
    val serverPublicKeyPem: String,
)

class SettingsStore(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences(
        "sms-relay-settings",
        Context.MODE_PRIVATE
    )

    fun getSettings(): RelaySettings {
        return RelaySettings(
            serverUrl = prefs.getString(KEY_SERVER_URL, "") ?: "",
            bearerToken = prefs.getString(KEY_BEARER_TOKEN, "") ?: "",
            clientId = prefs.getString(KEY_CLIENT_ID, "phone-1") ?: "phone-1",
            serverPublicKeyPem = prefs.getString(KEY_PUBLIC_KEY, "") ?: "",
        )
    }

    fun save(settings: RelaySettings) {
        prefs.edit()
            .putString(KEY_SERVER_URL, settings.serverUrl.trim())
            .putString(KEY_BEARER_TOKEN, settings.bearerToken.trim())
            .putString(KEY_CLIENT_ID, settings.clientId.trim())
            .putString(KEY_PUBLIC_KEY, settings.serverPublicKeyPem.trim())
            .apply()
    }

    fun setLastUploadStatus(status: String) {
        prefs.edit().putString(KEY_LAST_UPLOAD_STATUS, status).apply()
    }

    fun getLastUploadStatus(): String {
        return prefs.getString(KEY_LAST_UPLOAD_STATUS, "No uploads yet") ?: "No uploads yet"
    }

    companion object {
        private const val KEY_SERVER_URL = "server_url"
        private const val KEY_BEARER_TOKEN = "bearer_token"
        private const val KEY_CLIENT_ID = "client_id"
        private const val KEY_PUBLIC_KEY = "server_public_key_pem"
        private const val KEY_LAST_UPLOAD_STATUS = "last_upload_status"
    }
}

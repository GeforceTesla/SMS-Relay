package com.example.smsrelay

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.concurrent.TimeUnit

sealed class ApiResult {
    data object Success : ApiResult()
    data class RetryableFailure(val reason: String) : ApiResult()
    data class PermanentFailure(val reason: String) : ApiResult()
}

class ApiClient(private val settings: RelaySettings) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .writeTimeout(20, TimeUnit.SECONDS)
        .build()

    suspend fun postSms(envelope: EncryptedEnvelope): ApiResult = withContext(Dispatchers.IO) {
        if (settings.serverUrl.isBlank() || settings.bearerToken.isBlank()) {
            return@withContext ApiResult.PermanentFailure("server URL and bearer token are required")
        }

        val endpoint = settings.serverUrl.trimEnd('/') + "/api/v1/sms"
        val body = envelope.toJsonString().toRequestBody(JSON)
        val request = Request.Builder()
            .url(endpoint)
            .header("Authorization", "Bearer ${settings.bearerToken}")
            .post(body)
            .build()

        try {
            client.newCall(request).execute().use { response ->
                when {
                    response.code == 200 -> ApiResult.Success
                    response.code == 401 || response.code == 403 -> {
                        ApiResult.PermanentFailure("auth rejected with HTTP ${response.code}")
                    }
                    response.code == 400 -> ApiResult.PermanentFailure("payload rejected with HTTP 400")
                    response.code == 408 || response.code == 429 || response.code >= 500 -> {
                        ApiResult.RetryableFailure("temporary server error HTTP ${response.code}")
                    }
                    else -> ApiResult.RetryableFailure("unexpected HTTP ${response.code}")
                }
            }
        } catch (exc: IOException) {
            ApiResult.RetryableFailure(exc.message ?: "network error")
        } catch (exc: IllegalArgumentException) {
            ApiResult.PermanentFailure(exc.message ?: "invalid server URL")
        }
    }

    companion object {
        private val JSON = "application/json; charset=utf-8".toMediaType()
    }
}

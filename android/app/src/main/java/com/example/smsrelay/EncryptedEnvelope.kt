package com.example.smsrelay

import org.json.JSONObject

data class EncryptedEnvelope(
    val version: Int,
    val clientId: String,
    val messageId: String,
    val encryptedKey: String,
    val nonce: String,
    val ciphertext: String,
    val createdAt: Long,
) {
    fun toJsonString(): String {
        return JSONObject()
            .put("version", version)
            .put("client_id", clientId)
            .put("message_id", messageId)
            .put("encrypted_key", encryptedKey)
            .put("nonce", nonce)
            .put("ciphertext", ciphertext)
            .put("created_at", createdAt)
            .toString()
    }
}

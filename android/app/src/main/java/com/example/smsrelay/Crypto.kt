package com.example.smsrelay

import android.util.Base64
import org.json.JSONObject
import java.security.KeyFactory
import java.security.SecureRandom
import java.security.interfaces.RSAPublicKey
import java.security.spec.MGF1ParameterSpec
import java.security.spec.X509EncodedKeySpec
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.OAEPParameterSpec
import javax.crypto.spec.PSource

object Crypto {
    private val secureRandom = SecureRandom()

    fun encryptSms(message: OutboundSmsEntity, settings: RelaySettings): EncryptedEnvelope {
        require(settings.clientId.isNotBlank()) { "client_id is required" }
        require(settings.serverPublicKeyPem.isNotBlank()) { "server public key is required" }

        val plaintext = JSONObject()
            .put("sender", message.sender)
            .put("body", message.body)
            .put("received_at_phone", message.receivedAtPhone)
            .put("sim_slot", message.simSlot)
            .toString()
            .toByteArray(Charsets.UTF_8)

        val aesKey = KeyGenerator.getInstance("AES").apply { init(256) }.generateKey()
        val nonce = ByteArray(12).also { secureRandom.nextBytes(it) }
        val aesCipher = Cipher.getInstance("AES/GCM/NoPadding")
        aesCipher.init(Cipher.ENCRYPT_MODE, aesKey, GCMParameterSpec(128, nonce))
        val ciphertext = aesCipher.doFinal(plaintext)

        val rsaCipher = Cipher.getInstance("RSA/ECB/OAEPWithSHA-256AndMGF1Padding")
        rsaCipher.init(
            Cipher.ENCRYPT_MODE,
            parsePublicKey(settings.serverPublicKeyPem),
            OAEPParameterSpec(
                "SHA-256",
                "MGF1",
                MGF1ParameterSpec.SHA256,
                PSource.PSpecified.DEFAULT
            )
        )
        val encryptedKey = rsaCipher.doFinal(aesKey.encoded)

        return EncryptedEnvelope(
            version = 1,
            clientId = settings.clientId,
            messageId = message.clientMessageId,
            encryptedKey = b64(encryptedKey),
            nonce = b64(nonce),
            ciphertext = b64(ciphertext),
            createdAt = message.createdAt,
        )
    }

    private fun parsePublicKey(pem: String): RSAPublicKey {
        val body = pem
            .replace("-----BEGIN PUBLIC KEY-----", "")
            .replace("-----END PUBLIC KEY-----", "")
            .replace("\\s".toRegex(), "")
        val keyBytes = Base64.decode(body, Base64.DEFAULT)
        val key = KeyFactory.getInstance("RSA").generatePublic(X509EncodedKeySpec(keyBytes))
        return key as RSAPublicKey
    }

    private fun b64(bytes: ByteArray): String {
        return Base64.encodeToString(bytes, Base64.NO_WRAP)
    }
}

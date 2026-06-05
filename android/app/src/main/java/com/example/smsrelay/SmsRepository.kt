package com.example.smsrelay

import android.content.Context
import java.util.UUID

class SmsRepository(private val dao: OutboundSmsDao) {
    suspend fun enqueueIncomingSms(sender: String, body: String, receivedAtPhone: Long, simSlot: Int?): Long {
        return dao.insert(
            OutboundSmsEntity(
                clientMessageId = UUID.randomUUID().toString(),
                sender = sender,
                body = body,
                receivedAtPhone = receivedAtPhone,
                simSlot = simSlot,
                status = STATUS_PENDING,
                createdAt = System.currentTimeMillis(),
            )
        )
    }

    suspend fun enqueueTestSms(body: String): Long {
        return enqueueIncomingSms(
            sender = "+15550000000",
            body = body.ifBlank { "SMS Relay encrypted test ${System.currentTimeMillis()}" },
            receivedAtPhone = System.currentTimeMillis(),
            simSlot = null,
        )
    }

    suspend fun pendingForUpload(limit: Int = 25): List<OutboundSmsEntity> {
        return dao.messagesWithStatus(listOf(STATUS_PENDING, STATUS_FAILED), limit)
    }

    suspend fun markUploading(message: OutboundSmsEntity) {
        dao.updateStatus(message.id, STATUS_UPLOADING)
    }

    suspend fun markUploaded(message: OutboundSmsEntity) {
        dao.updateStatus(message.id, STATUS_UPLOADED, uploadedAt = System.currentTimeMillis())
    }

    suspend fun markRetry(message: OutboundSmsEntity, reason: String) {
        dao.updateStatus(
            id = message.id,
            status = STATUS_PENDING,
            retryIncrement = 1,
            lastError = reason.take(200),
        )
    }

    suspend fun markFailed(message: OutboundSmsEntity, reason: String) {
        dao.updateStatus(
            id = message.id,
            status = STATUS_FAILED,
            retryIncrement = 1,
            lastError = reason.take(200),
        )
    }

    suspend fun queueLength(): Int {
        return dao.countWithStatus(listOf(STATUS_PENDING, STATUS_UPLOADING, STATUS_FAILED))
    }

    suspend fun latestStatusText(): String {
        return dao.latestStatusText() ?: "No queued messages"
    }

    companion object {
        const val STATUS_PENDING = "pending"
        const val STATUS_UPLOADING = "uploading"
        const val STATUS_UPLOADED = "uploaded"
        const val STATUS_FAILED = "failed"

        fun get(context: Context): SmsRepository {
            return SmsRepository(SmsDatabase.get(context).outboundSmsDao())
        }
    }
}

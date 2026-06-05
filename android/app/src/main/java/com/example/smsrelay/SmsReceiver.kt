package com.example.smsrelay

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class SmsReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return

        val pendingResult = goAsync()
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            try {
                val parts = Telephony.Sms.Intents.getMessagesFromIntent(intent).toList()
                if (parts.isEmpty()) return@launch

                val sender = parts.firstOrNull()?.displayOriginatingAddress ?: "unknown"
                val body = parts.joinToString(separator = "") { it.messageBody ?: "" }
                val receivedAtPhone = parts.minOfOrNull { it.timestampMillis }
                    ?: System.currentTimeMillis()
                val simSlot = readSimSlot(intent)

                val repository = SmsRepository.get(context)
                repository.enqueueIncomingSms(sender, body, receivedAtPhone, simSlot)
                SmsUploadWorker.enqueue(context)
            } finally {
                pendingResult.finish()
            }
        }
    }

    private fun readSimSlot(intent: Intent): Int? {
        val extras = intent.extras ?: return null
        val knownKeys = listOf("slot", "slotId", "simSlot", "subscription", "subscription_id")
        for (key in knownKeys) {
            if (extras.containsKey(key)) {
                return when (val value = extras.get(key)) {
                    is Int -> value
                    is Long -> value.toInt()
                    is String -> value.toIntOrNull()
                    else -> null
                }
            }
        }
        return null
    }
}

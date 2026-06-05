package com.example.smsrelay

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit

class SmsUploadWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        val repository = SmsRepository.get(applicationContext)
        val settingsStore = SettingsStore(applicationContext)
        val settings = settingsStore.getSettings()
        val messages = repository.pendingForUpload()

        if (messages.isEmpty()) {
            settingsStore.setLastUploadStatus("Queue empty")
            return Result.success()
        }

        var shouldRetry = false
        settingsStore.setLastUploadStatus("Uploading ${messages.size} queued messages")
        val apiClient = ApiClient(settings)

        for (message in messages) {
            repository.markUploading(message)
            try {
                val envelope = Crypto.encryptSms(message, settings)
                when (val result = apiClient.postSms(envelope)) {
                    ApiResult.Success -> {
                        repository.markUploaded(message)
                        settingsStore.setLastUploadStatus("Uploaded ${message.clientMessageId}")
                    }
                    is ApiResult.PermanentFailure -> {
                        repository.markFailed(message, result.reason)
                        settingsStore.setLastUploadStatus(result.reason)
                    }
                    is ApiResult.RetryableFailure -> {
                        shouldRetry = true
                        repository.markRetry(message, result.reason)
                        settingsStore.setLastUploadStatus(result.reason)
                    }
                }
            } catch (exc: Exception) {
                val reason = exc.message ?: exc.javaClass.simpleName
                repository.markFailed(message, reason)
                settingsStore.setLastUploadStatus(reason)
            }
        }

        return if (shouldRetry) Result.retry() else Result.success()
    }

    companion object {
        private const val UNIQUE_WORK_NAME = "sms-upload"

        fun enqueue(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()
            val request = OneTimeWorkRequestBuilder<SmsUploadWorker>()
                .setConstraints(constraints)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build()

            WorkManager.getInstance(context.applicationContext).enqueueUniqueWork(
                UNIQUE_WORK_NAME,
                ExistingWorkPolicy.REPLACE,
                request
            )
        }
    }
}

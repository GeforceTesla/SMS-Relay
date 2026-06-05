package com.example.smsrelay

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface OutboundSmsDao {
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insert(message: OutboundSmsEntity): Long

    @Query(
        """
        SELECT * FROM outbound_sms
        WHERE status IN (:statuses)
        ORDER BY created_at ASC
        LIMIT :limit
        """
    )
    suspend fun messagesWithStatus(statuses: List<String>, limit: Int): List<OutboundSmsEntity>

    @Query(
        """
        UPDATE outbound_sms
        SET status = :status,
            retry_count = retry_count + :retryIncrement,
            last_error = :lastError,
            uploaded_at = :uploadedAt
        WHERE id = :id
        """
    )
    suspend fun updateStatus(
        id: Long,
        status: String,
        retryIncrement: Int = 0,
        lastError: String? = null,
        uploadedAt: Long? = null,
    )

    @Query("SELECT COUNT(*) FROM outbound_sms WHERE status IN (:statuses)")
    suspend fun countWithStatus(statuses: List<String>): Int

    @Query(
        """
        SELECT COALESCE(last_error, status)
        FROM outbound_sms
        ORDER BY COALESCE(uploaded_at, created_at) DESC
        LIMIT 1
        """
    )
    suspend fun latestStatusText(): String?
}

package com.example.smsrelay

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "outbound_sms",
    indices = [Index(value = ["client_message_id"], unique = true)]
)
data class OutboundSmsEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "client_message_id")
    val clientMessageId: String,
    val sender: String,
    val body: String,
    @ColumnInfo(name = "received_at_phone")
    val receivedAtPhone: Long,
    @ColumnInfo(name = "sim_slot")
    val simSlot: Int?,
    val status: String,
    @ColumnInfo(name = "retry_count")
    val retryCount: Int = 0,
    @ColumnInfo(name = "last_error")
    val lastError: String? = null,
    @ColumnInfo(name = "created_at")
    val createdAt: Long,
    @ColumnInfo(name = "uploaded_at")
    val uploadedAt: Long? = null,
)

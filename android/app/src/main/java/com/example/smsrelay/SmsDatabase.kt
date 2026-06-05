package com.example.smsrelay

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(entities = [OutboundSmsEntity::class], version = 1, exportSchema = false)
abstract class SmsDatabase : RoomDatabase() {
    abstract fun outboundSmsDao(): OutboundSmsDao

    companion object {
        @Volatile
        private var instance: SmsDatabase? = null

        fun get(context: Context): SmsDatabase {
            return instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    SmsDatabase::class.java,
                    "sms-relay.db"
                ).build().also { instance = it }
            }
        }
    }
}

package com.rwradar.app.push

import android.content.Context
import androidx.core.app.NotificationChannelCompat
import androidx.core.app.NotificationManagerCompat
import com.rwradar.app.R

/** Notification channels. The ids must match `notification.channel_id` sent by the poller (CLAUDE.md §4.3). */
object Channels {
    const val NEW_OPENINGS = "new_openings"
    const val HIRING_SIGNALS = "hiring_signals"

    fun create(context: Context) {
        val openings = NotificationChannelCompat.Builder(NEW_OPENINGS, NotificationManagerCompat.IMPORTANCE_HIGH)
            .setName(context.getString(R.string.channel_new_openings))
            .setDescription(context.getString(R.string.channel_new_openings_desc))
            .build()
        val signals = NotificationChannelCompat.Builder(HIRING_SIGNALS, NotificationManagerCompat.IMPORTANCE_DEFAULT)
            .setName(context.getString(R.string.channel_hiring_signals))
            .setDescription(context.getString(R.string.channel_hiring_signals_desc))
            .build()
        NotificationManagerCompat.from(context).createNotificationChannelsCompat(listOf(openings, signals))
    }

    fun forType(type: String?): String = if (type == PushTarget.TYPE_SIGNAL) HIRING_SIGNALS else NEW_OPENINGS
}

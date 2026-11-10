package com.rwradar.app.push

import android.Manifest
import android.annotation.SuppressLint
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.rwradar.app.MainActivity
import com.rwradar.app.R
import com.rwradar.app.RwRadarApp

/**
 * Pushes are notification + data messages. In the background the system shows them and a tap
 * launches MainActivity with the data as extras. In the foreground we build the same notification here.
 */
class RwMessagingService : FirebaseMessagingService() {

    @SuppressLint("MissingPermission") // checked in canNotify()
    override fun onMessageReceived(message: RemoteMessage) {
        val target = PushTarget.fromData(message.data)
        val title = message.notification?.title ?: getString(R.string.app_name)
        val body = message.notification?.body ?: return
        val channel = message.notification?.channelId ?: Channels.forType(target?.type)

        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            target?.toExtras()?.forEach { (key, value) -> putExtra(key, value) }
        }
        val requestCode = (message.messageId ?: "${target?.companyId}_${System.currentTimeMillis()}").hashCode()
        val pendingIntent = PendingIntent.getActivity(
            this, requestCode, intent, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )

        val notification = NotificationCompat.Builder(this, channel)
            .setSmallIcon(R.drawable.ic_stat_radar)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .build()

        val manager = NotificationManagerCompat.from(this)
        if (canNotify(manager)) {
            manager.notify(requestCode, notification)
        }
    }

    // Deprecated in firebase-messaging 26 (onRegistered is the newer callback) but still dispatched
    // for NEW_TOKEN, so both are handled.
    @Suppress("OVERRIDE_DEPRECATION")
    override fun onNewToken(token: String) = onTokenChanged("onNewToken")

    override fun onRegistered(token: String) = onTokenChanged("onRegistered")

    private fun onTokenChanged(callback: String) {
        // Topic subscriptions belong to the app instance and no token is sent anywhere. Re-run the
        // topic sync in case this instance lost its subscriptions.
        Log.i(TAG, "FCM $callback; re-running topic sync")
        (application as? RwRadarApp)?.container?.resyncTopics()
    }

    private fun canNotify(manager: NotificationManagerCompat): Boolean {
        if (!manager.areNotificationsEnabled()) return false
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED
    }

    private companion object {
        const val TAG = "RwMessagingService"
    }
}

package com.rwradar.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.rwradar.app.analytics.Events
import com.rwradar.app.analytics.Params
import com.rwradar.app.push.PushTarget
import com.rwradar.app.ui.nav.RwNavHost
import com.rwradar.app.ui.theme.RwRadarTheme
import kotlinx.coroutines.flow.MutableStateFlow

/** Single activity (singleTop). Notification taps arrive as extras in onCreate or onNewIntent. */
class MainActivity : ComponentActivity() {
    private val pendingPush = MutableStateFlow<PushTarget?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        // On recreation the launch intent was already handled.
        if (savedInstanceState == null) handleNotificationTap(intent)

        setContent {
            RwRadarTheme {
                val push by pendingPush.collectAsStateWithLifecycle()
                RwNavHost(pendingPush = push, onPushHandled = { pendingPush.value = null })
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleNotificationTap(intent)
    }

    private fun handleNotificationTap(intent: Intent?) {
        val extras = intent?.extras ?: return
        val target = PushTarget.parse { key -> extras.getString(key) } ?: return
        (application as RwRadarApp).container.analytics.log(
            Events.NOTIF_OPEN,
            Params.TYPE to target.type,
            Params.ID to target.companyId,
        )
        pendingPush.value = target
        listOf(
            PushTarget.KEY_TYPE, PushTarget.KEY_COMPANY_ID, PushTarget.KEY_FAMILY,
            PushTarget.KEY_SINCE, PushTarget.KEY_NEWS_HASH,
        ).forEach(intent::removeExtra)
    }
}

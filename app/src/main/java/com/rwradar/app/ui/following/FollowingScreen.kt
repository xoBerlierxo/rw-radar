package com.rwradar.app.ui.following

import android.content.Context
import android.content.Intent
import android.provider.Settings
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.NotificationsOff
import androidx.compose.material3.Badge
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.app.NotificationManagerCompat
import androidx.lifecycle.compose.LifecycleResumeEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.rwradar.app.R
import com.rwradar.app.ui.LoadState
import com.rwradar.app.ui.appContainer
import com.rwradar.app.ui.components.CompanyRow
import com.rwradar.app.ui.components.EmptyState
import com.rwradar.app.ui.components.ErrorState
import com.rwradar.app.ui.components.FollowButton
import com.rwradar.app.ui.components.LoadingState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FollowingScreen(onOpenCompany: (String) -> Unit) {
    val container = appContainer()
    val vm: FollowingViewModel = viewModel { FollowingViewModel(container) }
    val state by vm.state.collectAsStateWithLifecycle()
    val notificationsEnabled = rememberNotificationsEnabled()

    Scaffold(topBar = { TopAppBar(title = { Text(stringResource(R.string.tab_following)) }) }) { padding ->
        LazyColumn(Modifier.fillMaxSize(), contentPadding = padding) {
            if (!notificationsEnabled) {
                item { NotificationsOffBanner() }
            }
            when (val entries = state.entries) {
                LoadState.Loading -> item { LoadingState() }
                is LoadState.Failed -> item { ErrorState(onRetry = vm::retry) }
                is LoadState.Ready -> if (entries.data.isEmpty()) {
                    item { EmptyState(stringResource(R.string.empty_following)) }
                } else {
                    items(entries.data, key = { it.id }) { entry ->
                        val unread = state.unread[entry.id] ?: 0
                        CompanyRow(
                            entry = entry,
                            onClick = { onOpenCompany(entry.id) },
                            extraLine = if (unread > 0) {
                                { UnreadLabel(unread) }
                            } else {
                                null
                            },
                        ) {
                            FollowButton(following = true, onToggle = { vm.unfollow(entry.id) })
                        }
                        HorizontalDivider()
                    }
                }
            }
        }
    }
}

@Composable
private fun UnreadLabel(count: Int) {
    Badge(containerColor = MaterialTheme.colorScheme.primary, contentColor = MaterialTheme.colorScheme.onPrimary) {
        Text(pluralStringResource(R.plurals.unread_updates, count, count), modifier = Modifier.padding(horizontal = 4.dp))
    }
}

/** Re-checked on every resume, so the banner disappears after the user enables notifications. */
@Composable
private fun rememberNotificationsEnabled(): Boolean {
    val context = LocalContext.current
    var enabled by remember { mutableStateOf(true) }
    LifecycleResumeEffect(Unit) {
        enabled = NotificationManagerCompat.from(context).areNotificationsEnabled()
        onPauseOrDispose { }
    }
    return enabled
}

@Composable
private fun NotificationsOffBanner() {
    val context = LocalContext.current
    Card(
        modifier = Modifier.fillMaxWidth().padding(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.errorContainer,
            contentColor = MaterialTheme.colorScheme.onErrorContainer,
        ),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Icon(Icons.Outlined.NotificationsOff, contentDescription = null)
            Text(stringResource(R.string.banner_notifications_off_title), style = MaterialTheme.typography.titleMedium)
            Text(stringResource(R.string.banner_notifications_off_body), style = MaterialTheme.typography.bodyMedium)
            TextButton(onClick = { openNotificationSettings(context) }, modifier = Modifier.align(Alignment.End)) {
                Text(stringResource(R.string.action_open_settings))
            }
        }
    }
}

fun openNotificationSettings(context: Context) {
    val intent = Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
        .putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    runCatching { context.startActivity(intent) }
}

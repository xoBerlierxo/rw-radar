package com.rwradar.app.ui.onboarding

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.NotificationsActive
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.rwradar.app.R
import com.rwradar.app.ui.LoadState
import com.rwradar.app.ui.appContainer
import com.rwradar.app.ui.components.CompanyRow
import com.rwradar.app.ui.components.EmptyState
import com.rwradar.app.ui.components.ErrorState
import com.rwradar.app.ui.components.FamilyChips
import com.rwradar.app.ui.components.FollowButton
import com.rwradar.app.ui.components.LoadingState
import com.rwradar.app.ui.discover.SearchField

/** 3 steps (M9): role families → follow ≥ 3 companies → notification permission (Android 13+). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OnboardingScreen(onFinished: () -> Unit) {
    val container = appContainer()
    val vm: OnboardingViewModel = viewModel { OnboardingViewModel(container) }
    val step by vm.step.collectAsStateWithLifecycle()
    val families by vm.families.collectAsStateWithLifecycle()
    val followState by vm.followState.collectAsStateWithLifecycle()

    val context = LocalContext.current
    val needsPermissionStep = remember {
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
    }
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        vm.finish(onFinished) // continue whether granted or denied; Following shows a banner if off
    }

    BackHandler(enabled = step != OnboardingStep.FAMILIES) { vm.back() }

    Scaffold(
        topBar = {
            Column {
                TopAppBar(title = { Text(stringResource(R.string.onboarding_step, step.ordinal + 1, 3)) })
                LinearProgressIndicator(
                    progress = { (step.ordinal + 1) / 3f },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        bottomBar = {
            Surface(tonalElevation = 3.dp) {
                Row(
                    Modifier.fillMaxWidth().navigationBarsPadding().padding(16.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp, Alignment.End),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    when (step) {
                        OnboardingStep.FAMILIES -> Button(onClick = vm::submitFamilies, enabled = families.isNotEmpty()) {
                            Text(stringResource(R.string.action_next))
                        }
                        OnboardingStep.FOLLOW -> {
                            Text(
                                stringResource(R.string.onboarding_follow_count, followState.follows.size, followState.required),
                                style = MaterialTheme.typography.bodyMedium,
                                modifier = Modifier.weight(1f),
                            )
                            Button(
                                onClick = { vm.submitFollows(needsPermissionStep, onFinished) },
                                enabled = followState.canContinue,
                            ) { Text(stringResource(R.string.action_continue)) }
                        }
                        OnboardingStep.NOTIFICATIONS -> {
                            TextButton(onClick = { vm.finish(onFinished) }) { Text(stringResource(R.string.action_not_now)) }
                            Button(onClick = { permissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS) }) {
                                Text(stringResource(R.string.action_allow_notifications))
                            }
                        }
                    }
                }
            }
        },
    ) { padding ->
        when (step) {
            OnboardingStep.FAMILIES -> FamiliesStep(Modifier.padding(padding)) {
                FamilyChips(selected = families, onToggle = vm::toggleFamily)
            }
            OnboardingStep.FOLLOW -> FollowStep(
                state = followState,
                onQuery = vm::setQuery,
                onToggle = vm::toggleFollow,
                onRetry = vm::retryDirectory,
                modifier = Modifier.padding(padding),
            )
            OnboardingStep.NOTIFICATIONS -> NotificationsStep(Modifier.padding(padding))
        }
    }
}

@Composable
private fun FamiliesStep(modifier: Modifier, chips: @Composable () -> Unit) {
    Column(
        modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(stringResource(R.string.onboarding_families_title), style = MaterialTheme.typography.headlineSmall)
        Text(stringResource(R.string.onboarding_families_body), style = MaterialTheme.typography.bodyLarge)
        chips()
    }
}

@Composable
private fun FollowStep(
    state: FollowStepState,
    onQuery: (String) -> Unit,
    onToggle: (String, Boolean) -> Unit,
    onRetry: () -> Unit,
    modifier: Modifier,
) {
    LazyColumn(modifier.fillMaxSize()) {
        item {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(stringResource(R.string.onboarding_follow_title), style = MaterialTheme.typography.headlineSmall)
                Text(stringResource(R.string.onboarding_follow_body), style = MaterialTheme.typography.bodyLarge)
                SearchField(query = state.query, onQueryChange = onQuery, modifier = Modifier.fillMaxWidth())
            }
        }
        when (val dir = state.directory) {
            LoadState.Loading -> item { LoadingState() }
            is LoadState.Failed -> item { ErrorState(onRetry = onRetry) }
            is LoadState.Ready -> if (state.results.isEmpty()) {
                item {
                    EmptyState(stringResource(if (dir.data.isEmpty()) R.string.empty_directory else R.string.empty_search))
                }
            } else {
                items(state.results, key = { it.id }) { entry ->
                    val following = entry.id in state.follows
                    CompanyRow(entry = entry, onClick = { onToggle(entry.id, !following) }) {
                        FollowButton(following = following, onToggle = { onToggle(entry.id, !following) })
                    }
                    HorizontalDivider()
                }
            }
        }
    }
}

@Composable
private fun NotificationsStep(modifier: Modifier) {
    Column(
        modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Icon(
            Icons.Outlined.NotificationsActive,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier.size(48.dp),
        )
        Text(stringResource(R.string.onboarding_notif_title), style = MaterialTheme.typography.headlineSmall)
        Text(stringResource(R.string.onboarding_notif_body), style = MaterialTheme.typography.bodyLarge)
    }
}

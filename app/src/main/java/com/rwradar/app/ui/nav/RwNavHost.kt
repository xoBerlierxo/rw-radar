package com.rwradar.app.ui.nav

import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bookmarks
import androidx.compose.material.icons.filled.Explore
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.outlined.Bookmarks
import androidx.compose.material.icons.outlined.Explore
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.rwradar.app.R
import com.rwradar.app.analytics.ParamValues
import com.rwradar.app.push.PushTarget
import com.rwradar.app.ui.appContainer
import com.rwradar.app.ui.company.CompanyScreen
import com.rwradar.app.ui.company.CompanyTab
import com.rwradar.app.ui.company.CompanyViewModel
import com.rwradar.app.ui.discover.DiscoverScreen
import com.rwradar.app.ui.following.FollowingScreen
import com.rwradar.app.ui.onboarding.OnboardingScreen
import com.rwradar.app.ui.settings.PrivacyScreen
import com.rwradar.app.ui.settings.SettingsScreen
import kotlinx.coroutines.flow.map

object Routes {
    const val ONBOARDING = "onboarding"
    const val DISCOVER = "discover"
    const val FOLLOWING = "following"
    const val SETTINGS = "settings"
    const val PRIVACY = "privacy"

    const val ARG_ID = "companyId"
    const val ARG_TAB = "tab"
    const val ARG_SINCE = "since"
    const val ARG_SOURCE = "source"
    const val COMPANY = "company/{$ARG_ID}?$ARG_TAB={$ARG_TAB}&$ARG_SINCE={$ARG_SINCE}&$ARG_SOURCE={$ARG_SOURCE}"

    fun company(id: String, source: String, tab: CompanyTab = CompanyTab.OPENINGS, since: Long? = null): String =
        "company/${Uri.encode(id)}?$ARG_TAB=${tab.ordinal}&$ARG_SINCE=${since ?: -1}&$ARG_SOURCE=$source"
}

private enum class TopLevel(val route: String, val label: Int, val icon: ImageVector, val selectedIcon: ImageVector) {
    DISCOVER(Routes.DISCOVER, R.string.tab_discover, Icons.Outlined.Explore, Icons.Filled.Explore),
    FOLLOWING(Routes.FOLLOWING, R.string.tab_following, Icons.Outlined.Bookmarks, Icons.Filled.Bookmarks),
    SETTINGS(Routes.SETTINGS, R.string.tab_settings, Icons.Outlined.Settings, Icons.Filled.Settings),
}

/**
 * Single NavHost. Onboarding shows until finished, then never again. [pendingPush] is a notification
 * tap to route to Company detail (Openings + highlights for jobs, News for signals).
 */
@Composable
fun RwNavHost(pendingPush: PushTarget?, onPushHandled: () -> Unit) {
    val container = appContainer()
    val onboardingDone by remember { container.localPrefs.onboardingDone.map<Boolean, Boolean?> { it } }
        .collectAsStateWithLifecycle(initialValue = null)

    if (onboardingDone == null) {
        Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background))
        return
    }
    // Fixed at first composition: finishing onboarding navigates instead of swapping the graph.
    val startRoute = remember { if (onboardingDone == true) Routes.DISCOVER else Routes.ONBOARDING }
    val navController = rememberNavController()

    LaunchedEffect(pendingPush) {
        val push = pendingPush ?: return@LaunchedEffect
        navController.navigate(
            Routes.company(
                id = push.companyId,
                source = ParamValues.SOURCE_NOTIFICATION,
                tab = if (push.isSignal) CompanyTab.NEWS else CompanyTab.OPENINGS,
                since = push.since,
            ),
        )
        onPushHandled()
    }

    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route
    val showBottomBar = TopLevel.entries.any { it.route == currentRoute }

    Scaffold(
        contentWindowInsets = WindowInsets(0),
        bottomBar = { if (showBottomBar) BottomBar(navController, currentRoute) },
    ) { inner ->
        NavHost(
            navController = navController,
            startDestination = startRoute,
            modifier = Modifier.padding(inner).consumeWindowInsets(inner),
        ) {
            composable(Routes.ONBOARDING) {
                OnboardingScreen(onFinished = {
                    navController.navigate(Routes.DISCOVER) { popUpTo(Routes.ONBOARDING) { inclusive = true } }
                })
            }
            composable(Routes.DISCOVER) {
                DiscoverScreen(onOpenCompany = { navController.navigate(Routes.company(it, ParamValues.SOURCE_DISCOVER)) })
            }
            composable(Routes.FOLLOWING) {
                FollowingScreen(onOpenCompany = { navController.navigate(Routes.company(it, ParamValues.SOURCE_FOLLOWING)) })
            }
            composable(Routes.SETTINGS) {
                SettingsScreen(onOpenPrivacy = { navController.navigate(Routes.PRIVACY) })
            }
            composable(Routes.PRIVACY) {
                PrivacyScreen(onBack = { navController.popBackStack() })
            }
            composable(
                Routes.COMPANY,
                arguments = listOf(
                    navArgument(Routes.ARG_ID) { type = NavType.StringType },
                    navArgument(Routes.ARG_TAB) { type = NavType.IntType; defaultValue = 0 },
                    navArgument(Routes.ARG_SINCE) { type = NavType.LongType; defaultValue = -1L },
                    navArgument(Routes.ARG_SOURCE) { type = NavType.StringType; defaultValue = ParamValues.SOURCE_DISCOVER },
                ),
            ) { entry ->
                val args = requireNotNull(entry.arguments)
                val vm: CompanyViewModel = viewModel {
                    CompanyViewModel(
                        container = container,
                        companyId = requireNotNull(args.getString(Routes.ARG_ID)),
                        initialTab = CompanyTab.entries.getOrElse(args.getInt(Routes.ARG_TAB)) { CompanyTab.OPENINGS },
                        highlightSince = args.getLong(Routes.ARG_SINCE).takeIf { it >= 0 },
                        source = args.getString(Routes.ARG_SOURCE) ?: ParamValues.SOURCE_DISCOVER,
                    )
                }
                CompanyScreen(vm, onBack = { navController.popBackStack() })
            }
        }
    }
}

@Composable
private fun BottomBar(navController: NavHostController, currentRoute: String?) {
    NavigationBar {
        TopLevel.entries.forEach { item ->
            val selected = item.route == currentRoute
            NavigationBarItem(
                selected = selected,
                onClick = {
                    if (!selected) {
                        navController.navigate(item.route) {
                            // Discover is the root once onboarding is done.
                            popUpTo(Routes.DISCOVER) { saveState = true }
                            launchSingleTop = true
                            restoreState = true
                        }
                    }
                },
                icon = { Icon(if (selected) item.selectedIcon else item.icon, contentDescription = null) },
                label = { Text(stringResource(item.label)) },
            )
        }
    }
}

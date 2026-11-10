package com.rwradar.app.ui

import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext
import com.rwradar.app.AppContainer
import com.rwradar.app.RwRadarApp
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.onStart

/** Loading / ready / failed, for screens backed by a listener (directory, company doc). */
sealed interface LoadState<out T> {
    data object Loading : LoadState<Nothing>
    data class Ready<T>(val data: T) : LoadState<T>
    data class Failed(val error: Throwable) : LoadState<Nothing>
}

fun <T> Flow<T>.asLoadState(): Flow<LoadState<T>> =
    map<T, LoadState<T>> { LoadState.Ready(it) }
        .onStart { emit(LoadState.Loading) }
        .catch { emit(LoadState.Failed(it)) }

/** The app-wide [AppContainer] (manual DI). */
@Composable
fun appContainer(): AppContainer = (LocalContext.current.applicationContext as RwRadarApp).container

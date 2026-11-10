package com.rwradar.app.ui.discover

import android.os.SystemClock
import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.rwradar.app.AppContainer
import com.rwradar.app.analytics.ParamValues
import com.rwradar.app.data.model.DirectoryEntry
import com.rwradar.app.ui.LoadState
import com.rwradar.app.ui.asLoadState
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn

data class DiscoverState(
    val query: String = "",
    val sort: SortOrder = SortOrder.NEW_THIS_WEEK,
    val directory: LoadState<List<DirectoryEntry>> = LoadState.Loading,
    val results: List<DirectoryEntry> = emptyList(),
    val follows: Set<String> = emptySet(),
)

@OptIn(ExperimentalCoroutinesApi::class)
class DiscoverViewModel(private val container: AppContainer) : ViewModel() {
    private val query = MutableStateFlow("")
    private val sort = MutableStateFlow(SortOrder.NEW_THIS_WEEK)
    private val retry = MutableStateFlow(0)

    private val directory = retry.flatMapLatest { container.directoryRepository.observe().asLoadState() }
    private val follows = container.userRepository.prefs.map { it?.follows.orEmpty().toSet() }

    val state: StateFlow<DiscoverState> = combine(query, sort, directory, follows) { q, s, dir, f ->
        val entries = (dir as? LoadState.Ready)?.data.orEmpty()
        val start = SystemClock.elapsedRealtime()
        val results = DirectorySearch.apply(entries, q, s)
        if (q.isNotEmpty()) Log.d(TAG, "Search '${q}' over ${entries.size} took ${SystemClock.elapsedRealtime() - start}ms (target < 300ms)")
        DiscoverState(query = q, sort = s, directory = dir, results = results, follows = f)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), DiscoverState())

    fun setQuery(value: String) {
        query.value = value
    }

    fun setSort(value: SortOrder) {
        sort.value = value
    }

    fun retry() {
        retry.value++
    }

    fun toggleFollow(companyId: String, follow: Boolean) =
        container.setFollowing(companyId, follow, ParamValues.SOURCE_DISCOVER)

    private companion object {
        const val TAG = "Discover"
    }
}

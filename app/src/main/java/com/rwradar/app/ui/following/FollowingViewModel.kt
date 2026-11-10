package com.rwradar.app.ui.following

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.rwradar.app.AppContainer
import com.rwradar.app.analytics.ParamValues
import com.rwradar.app.data.model.DirectoryEntry
import com.rwradar.app.ui.LoadState
import com.rwradar.app.ui.asLoadState
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.mapLatest
import kotlinx.coroutines.flow.onStart
import kotlinx.coroutines.flow.stateIn

data class FollowingState(
    /** Loading until both the user doc and the directory are available. */
    val entries: LoadState<List<DirectoryEntry>> = LoadState.Loading,
    /** companyId → unread count; missing while counting. */
    val unread: Map<String, Int> = emptyMap(),
)

@OptIn(ExperimentalCoroutinesApi::class)
class FollowingViewModel(private val container: AppContainer) : ViewModel() {
    private val retry = MutableStateFlow(0)
    private val follows = container.userRepository.prefs.filterNotNull().map { it.follows }.distinctUntilChanged()
    private val directory = retry.flatMapLatest { container.directoryRepository.observe().asLoadState() }

    private val entries = combine(follows, directory) { ids, dir ->
        when (dir) {
            is LoadState.Ready -> {
                val byId = dir.data.associateBy { it.id }
                // A followed id missing from the directory still shows, by id.
                LoadState.Ready(ids.map { byId[it] ?: DirectoryEntry(id = it, name = it) }.sortedBy { it.name.lowercase() })
            }
            else -> dir
        }
    }

    private val unread = combine(follows, container.localPrefs.lastViewedAt) { ids, viewed -> ids to viewed }
        .distinctUntilChanged()
        .mapLatest { (ids, viewed) -> countUnread(ids, viewed) }
        .onStart { emit(emptyMap()) }

    val state: StateFlow<FollowingState> = combine(entries, unread) { e, u -> FollowingState(e, u) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), FollowingState())

    fun retry() {
        retry.value++
    }

    fun unfollow(companyId: String) = container.setFollowing(companyId, false, ParamValues.SOURCE_FOLLOWING)

    private suspend fun countUnread(ids: List<String>, viewed: Map<String, Long>): Map<String, Int> = coroutineScope {
        ids.map { id ->
            async {
                runCatching {
                    val repo = container.companyRepository
                    val jobs = async { repo.jobsPage(id).items.map { it.firstSeenAt } }
                    val news = async { repo.newsPage(id).items.map { it.publishedAt } }
                    id to Unread.count(jobs.await(), news.await(), viewed[id])
                }.onFailure { Log.w("Following", "Unread count failed for $id", it) }.getOrNull()
            }
        }.awaitAll().filterNotNull().toMap()
    }
}

package com.rwradar.app.ui

import android.util.Log
import com.google.firebase.firestore.DocumentSnapshot
import com.rwradar.app.data.Page
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class PagedState<T>(
    val items: List<T> = emptyList(),
    val loading: Boolean = false,
    val loadingMore: Boolean = false,
    val error: Boolean = false,
    val loaded: Boolean = false,
    val endReached: Boolean = false,
)

/** "Load more" paging over a Firestore query (20 per page, `startAfter` the last doc). */
class PagedList<T>(
    private val scope: CoroutineScope,
    private val load: suspend (after: DocumentSnapshot?) -> Page<T>,
) {
    private val _state = MutableStateFlow(PagedState<T>())
    val state: StateFlow<PagedState<T>> = _state.asStateFlow()
    private var cursor: DocumentSnapshot? = null
    private var job: Job? = null

    fun loadFirstIfNeeded() {
        if (!_state.value.loaded && job?.isActive != true) refresh()
    }

    fun refresh() {
        job?.cancel()
        cursor = null
        _state.value = PagedState(loading = true)
        job = scope.launch {
            runCatching { load(null) }
                .onSuccess { page ->
                    cursor = page.cursor
                    _state.value = PagedState(items = page.items, loaded = true, endReached = page.endReached)
                }
                .onFailure {
                    Log.w(TAG, "First page failed", it)
                    _state.value = PagedState(error = true)
                }
        }
    }

    fun loadMore() {
        val current = _state.value
        if (!current.loaded || current.endReached || job?.isActive == true) return
        _state.update { it.copy(loadingMore = true, error = false) }
        job = scope.launch {
            runCatching { load(cursor) }
                .onSuccess { page ->
                    cursor = page.cursor
                    _state.update { it.copy(items = it.items + page.items, loadingMore = false, endReached = page.endReached) }
                }
                .onFailure {
                    Log.w(TAG, "Next page failed", it)
                    _state.update { it.copy(loadingMore = false, error = true) }
                }
        }
    }

    private companion object {
        const val TAG = "PagedList"
    }
}

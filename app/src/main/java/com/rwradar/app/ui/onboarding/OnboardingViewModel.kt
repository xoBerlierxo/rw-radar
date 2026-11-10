package com.rwradar.app.ui.onboarding

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.rwradar.app.AppContainer
import com.rwradar.app.analytics.Events
import com.rwradar.app.analytics.ParamValues
import com.rwradar.app.analytics.Params
import com.rwradar.app.data.model.DirectoryEntry
import com.rwradar.app.data.model.RoleFamily
import com.rwradar.app.ui.LoadState
import com.rwradar.app.ui.asLoadState
import com.rwradar.app.ui.discover.DirectorySearch
import com.rwradar.app.ui.discover.SortOrder
import com.rwradar.app.ui.settings.SettingsViewModel
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class OnboardingStep { FAMILIES, FOLLOW, NOTIFICATIONS }

data class FollowStepState(
    val query: String = "",
    val directory: LoadState<List<DirectoryEntry>> = LoadState.Loading,
    val results: List<DirectoryEntry> = emptyList(),
    val follows: Set<String> = emptySet(),
) {
    /** At least 3 follows (M9), unless the directory itself has fewer companies. */
    val required: Int get() = minOf(MIN_FOLLOWS, (directory as? LoadState.Ready)?.data?.size ?: MIN_FOLLOWS)
    val canContinue: Boolean get() = directory is LoadState.Ready && follows.size >= required

    companion object {
        const val MIN_FOLLOWS = 3
    }
}

@OptIn(ExperimentalCoroutinesApi::class)
class OnboardingViewModel(private val container: AppContainer) : ViewModel() {
    private val _step = MutableStateFlow(OnboardingStep.FAMILIES)
    val step: StateFlow<OnboardingStep> = _step.asStateFlow()

    private val _families = MutableStateFlow<Set<RoleFamily>>(emptySet())
    val families: StateFlow<Set<RoleFamily>> = _families.asStateFlow()

    private val query = MutableStateFlow("")
    private val retry = MutableStateFlow(0)
    private val directory = retry.flatMapLatest { container.directoryRepository.observe().asLoadState() }
    private val follows = container.userRepository.prefs.map { it?.follows.orEmpty().toSet() }

    val followState: StateFlow<FollowStepState> = combine(query, directory, follows) { q, dir, f ->
        val entries = (dir as? LoadState.Ready)?.data.orEmpty()
        FollowStepState(q, dir, DirectorySearch.apply(entries, q, SortOrder.NEW_THIS_WEEK), f)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), FollowStepState())

    init {
        // Pre-fill families if the user doc already has some (e.g. onboarding restarted).
        viewModelScope.launch {
            val existing = container.userRepository.prefs.first { it != null }?.families.orEmpty()
            if (_families.value.isEmpty() && existing.isNotEmpty()) _families.value = existing
        }
    }

    fun toggleFamily(family: RoleFamily) =
        _families.update { if (family in it) it - family else it + family }

    fun setQuery(value: String) {
        query.value = value
    }

    fun retryDirectory() {
        retry.value++
    }

    fun toggleFollow(companyId: String, follow: Boolean) =
        container.setFollowing(companyId, follow, ParamValues.SOURCE_ONBOARDING)

    fun back() = _step.update { OnboardingStep.entries[(it.ordinal - 1).coerceAtLeast(0)] }

    fun submitFamilies() {
        if (_families.value.isEmpty()) return
        container.userRepository.setFamilies(_families.value)
        _step.value = OnboardingStep.FOLLOW
    }

    /** From the follow step: go to the permission step, or finish when it doesn't apply. */
    fun submitFollows(needsPermissionStep: Boolean, onDone: () -> Unit) {
        if (!followState.value.canContinue) return
        if (needsPermissionStep) _step.value = OnboardingStep.NOTIFICATIONS else finish(onDone)
    }

    /** Called after the permission prompt whatever the answer (continue even if denied). */
    fun finish(onDone: () -> Unit) {
        viewModelScope.launch {
            container.localPrefs.setOnboardingDone()
            container.analytics.log(
                Events.ONBOARDING_COMPLETE,
                Params.FAMILIES to SettingsViewModel.familiesParam(_families.value),
                Params.FOLLOWS to followState.value.follows.size,
            )
            onDone()
        }
    }
}

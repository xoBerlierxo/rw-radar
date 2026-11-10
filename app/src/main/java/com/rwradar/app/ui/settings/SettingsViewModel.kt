package com.rwradar.app.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.rwradar.app.AppContainer
import com.rwradar.app.analytics.Events
import com.rwradar.app.analytics.ParamValues
import com.rwradar.app.analytics.Params
import com.rwradar.app.data.model.RoleFamily
import com.rwradar.app.data.model.UserPrefs
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn

/** Settings writes go to `users/{uid}`; the AppContainer collector then re-syncs topics (< 5 s, M5). */
class SettingsViewModel(private val container: AppContainer) : ViewModel() {
    val prefs: StateFlow<UserPrefs?> = container.userRepository.prefs
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), container.userRepository.prefs.value)

    fun setNotifyJobs(on: Boolean) {
        container.userRepository.setNotifyJobs(on)
        container.analytics.log(Events.NOTIF_TOGGLE, Params.KIND to ParamValues.KIND_JOBS, Params.ON to on)
    }

    fun setNotifySignals(on: Boolean) {
        container.userRepository.setNotifySignals(on)
        container.analytics.log(Events.NOTIF_TOGGLE, Params.KIND to ParamValues.KIND_SIGNALS, Params.ON to on)
    }

    /** At least one family must stay selected. */
    fun toggleFamily(family: RoleFamily) {
        val current = prefs.value?.families ?: return
        val updated = if (family in current) current - family else current + family
        if (updated.isEmpty()) return
        container.userRepository.setFamilies(updated)
        container.analytics.log(Events.PREFS_CHANGED, Params.FAMILIES to familiesParam(updated))
    }

    companion object {
        fun familiesParam(families: Set<RoleFamily>): String =
            RoleFamily.entries.filter { it in families }.joinToString(",") { it.key }
    }
}

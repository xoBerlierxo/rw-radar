package com.rwradar.app.ui.company

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.rwradar.app.AppContainer
import com.rwradar.app.BuildConfig
import com.rwradar.app.analytics.Events
import com.rwradar.app.analytics.ParamValues
import com.rwradar.app.analytics.Params
import com.rwradar.app.data.model.Company
import com.rwradar.app.data.model.Job
import com.rwradar.app.data.model.NewsItem
import com.rwradar.app.data.model.RoleFamily
import com.rwradar.app.ui.LoadState
import com.rwradar.app.ui.PagedList
import com.rwradar.app.ui.asLoadState
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class CompanyTab { OPENINGS, NEWS }

@OptIn(ExperimentalCoroutinesApi::class)
class CompanyViewModel(
    private val container: AppContainer,
    val companyId: String,
    initialTab: CompanyTab,
    /** From a jobs push: highlight jobs with firstSeenAt >= since. */
    val highlightSince: Long?,
    source: String,
) : ViewModel() {
    private val retry = MutableStateFlow(0)
    val company: StateFlow<LoadState<Company?>> =
        retry.flatMapLatest { container.companyRepository.observeCompany(companyId).asLoadState() }
            .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), LoadState.Loading)

    val following: StateFlow<Boolean> = container.userRepository.prefs
        .map { companyId in it?.follows.orEmpty() }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), false)

    private val _tab = MutableStateFlow(initialTab)
    val tab: StateFlow<CompanyTab> = _tab.asStateFlow()

    private val _filters = MutableStateFlow(JobFilters())
    val filters: StateFlow<JobFilters> = _filters.asStateFlow()

    val jobs = PagedList(viewModelScope) { after -> container.companyRepository.jobsPage(companyId, after) }
    val news = PagedList(viewModelScope) { after -> container.companyRepository.newsPage(companyId, after) }

    init {
        container.analytics.log(Events.VIEW_COMPANY, Params.ID to companyId, Params.SOURCE to source)
        viewModelScope.launch { container.localPrefs.setLastViewedAt(companyId) }
        loadTab(initialTab)
    }

    fun selectTab(tab: CompanyTab) {
        _tab.value = tab
        loadTab(tab)
    }

    fun retryCompany() {
        retry.value++
    }

    fun toggleFamilyFilter(family: RoleFamily) =
        _filters.update { it.copy(families = if (family in it.families) it.families - family else it.families + family) }

    fun setLocationFilter(text: String) = _filters.update { it.copy(location = text) }

    fun setRemoteOnly(on: Boolean) = _filters.update { it.copy(remoteOnly = on) }

    fun toggleFollow() = container.setFollowing(companyId, !following.value, ParamValues.SOURCE_DETAIL)

    fun onApply(job: Job) =
        container.analytics.log(Events.APPLY_CLICK, Params.ID to companyId, Params.FAMILY to job.family.key)

    fun onNews(item: NewsItem) =
        container.analytics.log(Events.NEWS_CLICK, Params.ID to companyId, Params.TAG to item.tag.key)

    /** Plain homepage link, no params or deep links (M8). */
    fun onReferralWorld(): String {
        container.analytics.log(Events.REFERRALWORLD_CLICK, Params.ID to companyId)
        return BuildConfig.REFERRALWORLD_URL
    }

    private fun loadTab(tab: CompanyTab) = when (tab) {
        CompanyTab.OPENINGS -> jobs.loadFirstIfNeeded()
        CompanyTab.NEWS -> news.loadFirstIfNeeded()
    }
}

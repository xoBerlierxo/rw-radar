package com.rwradar.app.ui.company

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.PrimaryTabRow
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.rwradar.app.R
import com.rwradar.app.data.model.Company
import com.rwradar.app.data.model.RoleFamily
import com.rwradar.app.data.model.NewsItem
import com.rwradar.app.ui.LoadState
import com.rwradar.app.ui.PagedState
import com.rwradar.app.ui.components.CompanyAvatar
import com.rwradar.app.ui.components.EmptyState
import com.rwradar.app.ui.components.ErrorState
import com.rwradar.app.ui.components.FamilyChips
import com.rwradar.app.ui.components.FollowButton
import com.rwradar.app.ui.components.JobRow
import com.rwradar.app.ui.components.LoadingState
import com.rwradar.app.ui.components.NewsRow
import com.rwradar.app.util.openExternalUrl

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun CompanyScreen(vm: CompanyViewModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val companyState by vm.company.collectAsStateWithLifecycle()
    val following by vm.following.collectAsStateWithLifecycle()
    val tab by vm.tab.collectAsStateWithLifecycle()
    val filters by vm.filters.collectAsStateWithLifecycle()
    val jobs by vm.jobs.state.collectAsStateWithLifecycle()
    val news by vm.news.state.collectAsStateWithLifecycle()
    val company = (companyState as? LoadState.Ready)?.data

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(company?.name ?: "", maxLines = 1, overflow = TextOverflow.Ellipsis) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(R.string.action_back))
                    }
                },
            )
        },
    ) { padding ->
        // Top padding as a modifier so the sticky tab row pins right under the app bar.
        LazyColumn(
            Modifier.fillMaxSize().padding(top = padding.calculateTopPadding()),
            contentPadding = PaddingValues(bottom = padding.calculateBottomPadding()),
        ) {
            when (val state = companyState) {
                LoadState.Loading -> item { LoadingState() }
                is LoadState.Failed -> item { ErrorState(onRetry = vm::retryCompany) }
                is LoadState.Ready -> if (state.data == null) {
                    item { EmptyState(stringResource(R.string.empty_company)) }
                } else {
                    item {
                        CompanyHeader(
                            company = state.data,
                            following = following,
                            onToggleFollow = vm::toggleFollow,
                            onWebsite = { context.openExternalUrl(state.data.website) },
                            onReferralWorld = { context.openExternalUrl(vm.onReferralWorld()) },
                        )
                    }
                }
            }

            stickyHeader(key = "tabs") {
                Surface(color = MaterialTheme.colorScheme.surface) {
                    PrimaryTabRow(selectedTabIndex = tab.ordinal) {
                        Tab(
                            selected = tab == CompanyTab.OPENINGS,
                            onClick = { vm.selectTab(CompanyTab.OPENINGS) },
                            text = { Text(stringResource(R.string.tab_openings)) },
                        )
                        Tab(
                            selected = tab == CompanyTab.NEWS,
                            onClick = { vm.selectTab(CompanyTab.NEWS) },
                            text = { Text(stringResource(R.string.tab_news)) },
                        )
                    }
                }
            }

            when (tab) {
                CompanyTab.OPENINGS -> {
                    item(key = "filters") {
                        OpeningsFilters(
                            filters = filters,
                            onToggleFamily = vm::toggleFamilyFilter,
                            onLocation = vm::setLocationFilter,
                            onRemoteOnly = vm::setRemoteOnly,
                        )
                    }
                    pagedItems(
                        state = jobs,
                        visible = filters.apply(jobs.items),
                        emptyText = if (filters.isActive && jobs.items.isNotEmpty()) R.string.empty_openings_filtered else R.string.empty_openings,
                        onRetry = vm.jobs::refresh,
                        onLoadMore = vm.jobs::loadMore,
                        key = { "job_${it.id}" },
                    ) { job ->
                        JobRow(
                            job = job,
                            highlighted = JobFilters.isHighlighted(job, vm.highlightSince),
                            onClick = {
                                vm.onApply(job)
                                context.openExternalUrl(job.url)
                            },
                        )
                    }
                }
                CompanyTab.NEWS -> pagedItems(
                    state = news,
                    visible = news.items,
                    emptyText = R.string.empty_news,
                    onRetry = vm.news::refresh,
                    onLoadMore = vm.news::loadMore,
                    key = { "news_${it.id}" },
                ) { item: NewsItem ->
                    NewsRow(item = item, onClick = {
                        vm.onNews(item)
                        context.openExternalUrl(item.url)
                    })
                }
            }
        }
    }
}

/** Loading / error+retry / empty / rows + "Load more" for one paged list. */
private fun <T> LazyListScope.pagedItems(
    state: PagedState<T>,
    visible: List<T>,
    emptyText: Int,
    onRetry: () -> Unit,
    onLoadMore: () -> Unit,
    key: (T) -> String,
    row: @Composable (T) -> Unit,
) {
    when {
        state.loading || (!state.loaded && !state.error) -> item { LoadingState() }
        !state.loaded && state.error -> item { ErrorState(onRetry = onRetry) }
        else -> {
            if (visible.isEmpty()) {
                item { EmptyState(stringResource(emptyText)) }
            }
            items(visible, key = key) { value ->
                row(value)
                HorizontalDivider()
            }
            if (!state.endReached || state.error) {
                item(key = "load_more") {
                    Row(Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.Center) {
                        when {
                            state.loadingMore -> CircularProgressIndicator()
                            state.error -> TextButton(onClick = onLoadMore) { Text(stringResource(R.string.error_load_more)) }
                            else -> OutlinedButton(onClick = onLoadMore) { Text(stringResource(R.string.action_load_more)) }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun CompanyHeader(
    company: Company,
    following: Boolean,
    onToggleFollow: () -> Unit,
    onWebsite: () -> Unit,
    onReferralWorld: () -> Unit,
) {
    Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            CompanyAvatar(company.name, company.logoUrl, size = 64.dp)
            Column(Modifier.weight(1f)) {
                Text(company.name, style = MaterialTheme.typography.headlineSmall)
                val details = listOfNotNull(
                    company.sector.takeIf { it.isNotBlank() },
                    pluralStringResource(R.plurals.open_roles, company.openCount, company.openCount),
                ).joinToString(" · ")
                Text(details, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (company.website.isNotBlank()) {
                    TextButton(onClick = onWebsite, contentPadding = ButtonDefaults.TextButtonWithIconContentPadding) {
                        Text(
                            company.website.removePrefix("https://").removePrefix("http://").removeSuffix("/"),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }
        }
        FollowButton(following = following, onToggle = onToggleFollow, modifier = Modifier.fillMaxWidth())
        Button(onClick = onReferralWorld, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.action_referralworld))
            Icon(
                Icons.AutoMirrored.Filled.OpenInNew,
                contentDescription = null,
                modifier = Modifier.padding(start = ButtonDefaults.IconSpacing).size(ButtonDefaults.IconSize),
            )
        }
    }
}

@Composable
private fun OpeningsFilters(
    filters: JobFilters,
    onToggleFamily: (RoleFamily) -> Unit,
    onLocation: (String) -> Unit,
    onRemoteOnly: (Boolean) -> Unit,
) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        FamilyChips(selected = filters.families, onToggle = onToggleFamily)
        OutlinedTextField(
            value = filters.location,
            onValueChange = onLocation,
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text(stringResource(R.string.filter_location)) },
        )
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.filter_remote_only), modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
            Switch(checked = filters.remoteOnly, onCheckedChange = onRemoteOnly)
        }
    }
}

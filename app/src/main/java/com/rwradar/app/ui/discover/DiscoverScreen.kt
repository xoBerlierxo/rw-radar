package com.rwradar.app.ui.discover

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Sort
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.rwradar.app.R
import com.rwradar.app.ui.LoadState
import com.rwradar.app.ui.appContainer
import com.rwradar.app.ui.components.CompanyRow
import com.rwradar.app.ui.components.EmptyState
import com.rwradar.app.ui.components.ErrorState
import com.rwradar.app.ui.components.FollowButton
import com.rwradar.app.ui.components.LoadingState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DiscoverScreen(onOpenCompany: (String) -> Unit) {
    val container = appContainer()
    val vm: DiscoverViewModel = viewModel { DiscoverViewModel(container) }
    val state by vm.state.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.tab_discover)) },
                actions = { SortMenu(state.sort, vm::setSort) },
            )
        },
    ) { padding ->
        LazyColumn(Modifier.fillMaxSize(), contentPadding = padding) {
            item {
                SearchField(
                    query = state.query,
                    onQueryChange = vm::setQuery,
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
                )
            }
            when (val dir = state.directory) {
                LoadState.Loading -> item { LoadingState() }
                is LoadState.Failed -> item { ErrorState(onRetry = vm::retry) }
                is LoadState.Ready -> if (state.results.isEmpty()) {
                    item {
                        EmptyState(
                            stringResource(if (dir.data.isEmpty()) R.string.empty_directory else R.string.empty_search),
                        )
                    }
                } else {
                    items(state.results, key = { it.id }) { entry ->
                        val following = entry.id in state.follows
                        CompanyRow(entry = entry, onClick = { onOpenCompany(entry.id) }) {
                            FollowButton(following = following, onToggle = { vm.toggleFollow(entry.id, !following) })
                        }
                        HorizontalDivider()
                    }
                }
            }
        }
    }
}

@Composable
fun SearchField(query: String, onQueryChange: (String) -> Unit, modifier: Modifier = Modifier) {
    OutlinedTextField(
        value = query,
        onValueChange = onQueryChange,
        modifier = modifier,
        singleLine = true,
        placeholder = { Text(stringResource(R.string.search_companies)) },
        leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
        trailingIcon = {
            if (query.isNotEmpty()) {
                IconButton(onClick = { onQueryChange("") }) {
                    Icon(Icons.Filled.Clear, contentDescription = stringResource(R.string.action_clear_search))
                }
            }
        },
        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
    )
}

@Composable
private fun SortMenu(current: SortOrder, onSelect: (SortOrder) -> Unit) {
    var expanded by rememberSaveable { mutableStateOf(false) }
    Box {
        IconButton(onClick = { expanded = true }) {
            Icon(Icons.AutoMirrored.Filled.Sort, contentDescription = stringResource(R.string.action_sort))
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            SortOrder.entries.forEach { order ->
                DropdownMenuItem(
                    text = { Text(stringResource(order.labelRes())) },
                    onClick = {
                        onSelect(order)
                        expanded = false
                    },
                    trailingIcon = if (order == current) {
                        { Icon(Icons.Filled.Check, contentDescription = null) }
                    } else {
                        null
                    },
                )
            }
        }
    }
}

private fun SortOrder.labelRes(): Int = when (this) {
    SortOrder.NEW_THIS_WEEK -> R.string.sort_new_this_week
    SortOrder.RECENTLY_FUNDED -> R.string.sort_recently_funded
    SortOrder.A_Z -> R.string.sort_a_z
}

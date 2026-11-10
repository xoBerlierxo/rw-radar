package com.rwradar.app.ui.discover

import com.rwradar.app.data.model.DirectoryEntry

enum class SortOrder { NEW_THIS_WEEK, RECENTLY_FUNDED, A_Z }

/** In-memory search and sort over `directory/v1` (M1, D3). Pure, so it is unit tested. */
object DirectorySearch {

    private val byName = compareBy<DirectoryEntry, String>(String.CASE_INSENSITIVE_ORDER) { it.name }

    fun apply(entries: List<DirectoryEntry>, query: String, sort: SortOrder): List<DirectoryEntry> {
        val q = query.trim()
        val matches = if (q.isEmpty()) entries else entries.filter { it.matches(q) }
        return matches.sortedWith(comparator(sort))
    }

    fun comparator(sort: SortOrder): Comparator<DirectoryEntry> = when (sort) {
        SortOrder.NEW_THIS_WEEK -> compareByDescending<DirectoryEntry> { it.newThisWeek }.then(byName)
        // Most recent funding first; never-funded companies last.
        SortOrder.RECENTLY_FUNDED -> compareBy<DirectoryEntry> { it.lastFundingAt == null }
            .thenByDescending { it.lastFundingAt ?: 0L }
            .then(byName)
        SortOrder.A_Z -> byName
    }

    private fun DirectoryEntry.matches(q: String): Boolean =
        name.contains(q, ignoreCase = true) || aliases.any { it.contains(q, ignoreCase = true) }
}

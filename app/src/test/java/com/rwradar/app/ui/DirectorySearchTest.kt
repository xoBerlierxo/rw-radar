package com.rwradar.app.ui

import com.rwradar.app.data.model.DirectoryEntry
import com.rwradar.app.ui.discover.DirectorySearch
import com.rwradar.app.ui.discover.SortOrder
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DirectorySearchTest {

    private val entries = listOf(
        DirectoryEntry("zepto", "Zepto", newThisWeek = 2, lastFundingAt = 300L),
        DirectoryEntry("razorpay", "Razorpay", aliases = listOf("Razorpay Software"), newThisWeek = 5, lastFundingAt = 100L),
        DirectoryEntry("acko", "acko", newThisWeek = 2),
        DirectoryEntry("cred", "CRED", newThisWeek = 0, lastFundingAt = 200L),
    )

    private fun ids(query: String, sort: SortOrder) = DirectorySearch.apply(entries, query, sort).map { it.id }

    @Test
    fun `most new roles this week, ties by name`() {
        assertEquals(listOf("razorpay", "acko", "zepto", "cred"), ids("", SortOrder.NEW_THIS_WEEK))
    }

    @Test
    fun `recently funded puts never-funded last`() {
        assertEquals(listOf("zepto", "cred", "razorpay", "acko"), ids("", SortOrder.RECENTLY_FUNDED))
    }

    @Test
    fun `a to z ignores case`() {
        assertEquals(listOf("acko", "cred", "razorpay", "zepto"), ids("", SortOrder.A_Z))
    }

    @Test
    fun `search matches name and aliases, case-insensitive, trimmed`() {
        assertEquals(listOf("razorpay"), ids("  razor ", SortOrder.A_Z))
        assertEquals(listOf("razorpay"), ids("software", SortOrder.A_Z))
        assertEquals(listOf("cred"), ids("Cre", SortOrder.A_Z))
        assertEquals(emptyList<String>(), ids("nothing", SortOrder.A_Z))
    }

    @Test
    fun `search of 100 entries stays well under 300 ms`() {
        val many = (1..100).map { DirectoryEntry("c$it", "Company $it", aliases = listOf("Alias $it")) }
        val start = System.nanoTime()
        repeat(100) { DirectorySearch.apply(many, "pany 5", SortOrder.RECENTLY_FUNDED) }
        val perSearchMs = (System.nanoTime() - start) / 100 / 1_000_000.0
        assertTrue("search took $perSearchMs ms", perSearchMs < 300)
    }
}

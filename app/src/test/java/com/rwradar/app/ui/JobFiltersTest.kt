package com.rwradar.app.ui

import com.rwradar.app.data.model.Job
import com.rwradar.app.data.model.RoleFamily
import com.rwradar.app.ui.company.JobFilters
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class JobFiltersTest {

    private val jobs = listOf(
        Job("1", "Backend Engineer", RoleFamily.ENG, location = "Bengaluru", remote = false, firstSeenAt = 100L),
        Job("2", "Data Analyst", RoleFamily.DATA, location = "Remote - India", remote = true, firstSeenAt = 200L),
        Job("3", "Product Designer", RoleFamily.DESIGN, location = "Mumbai", remote = false),
    )

    private fun ids(filters: JobFilters) = filters.apply(jobs).map { it.id }

    @Test
    fun `no filters shows everything`() {
        assertEquals(listOf("1", "2", "3"), ids(JobFilters()))
        assertFalse(JobFilters().isActive)
    }

    @Test
    fun `filters combine`() {
        assertEquals(listOf("1", "2"), ids(JobFilters(families = setOf(RoleFamily.ENG, RoleFamily.DATA))))
        assertEquals(listOf("1"), ids(JobFilters(location = " bengal")))
        assertEquals(listOf("2"), ids(JobFilters(remoteOnly = true)))
        assertEquals(emptyList<String>(), ids(JobFilters(families = setOf(RoleFamily.ENG), remoteOnly = true)))
    }

    @Test
    fun `highlight jobs first seen at or after since`() {
        assertTrue(JobFilters.isHighlighted(jobs[1], since = 200L))
        assertFalse(JobFilters.isHighlighted(jobs[0], since = 200L))
        assertFalse(JobFilters.isHighlighted(jobs[2], since = 0L)) // unknown firstSeenAt
        assertFalse(JobFilters.isHighlighted(jobs[1], since = null))
    }
}

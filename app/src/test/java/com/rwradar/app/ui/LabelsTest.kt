package com.rwradar.app.ui

import com.rwradar.app.ui.components.Labels
import com.rwradar.app.util.TimeFormat
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.TimeUnit

class LabelsTest {
    private val day = TimeUnit.DAYS.toMillis(1)
    private val now = 1_000 * day

    @Test
    fun initials() {
        assertEquals("AL", Labels.initials("Acme Labs"))
        assertEquals("Z", Labels.initials("zepto"))
        assertEquals("PW", Labels.initials("Physics-Wallah"))
        assertEquals("?", Labels.initials("  "))
    }

    @Test
    fun `funded tag covers the last 90 days`() {
        assertTrue(Labels.isRecentlyFunded(now - 10 * day, now))
        assertTrue(Labels.isRecentlyFunded(now - 90 * day, now))
        assertFalse(Labels.isRecentlyFunded(now - 91 * day, now))
        assertFalse(Labels.isRecentlyFunded(null, now))
    }

    @Test
    fun `posted dates read naturally`() {
        assertEquals("today", TimeFormat.daysAgo(now - 1000, now))
        assertEquals("yesterday", TimeFormat.daysAgo(now - day, now))
        assertEquals("3 days ago", TimeFormat.daysAgo(now - 3 * day - 5, now))
        assertEquals("5 h ago", TimeFormat.relative(now - TimeUnit.HOURS.toMillis(5), now))
        assertEquals("just now", TimeFormat.relative(now, now))
    }
}

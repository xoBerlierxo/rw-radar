package com.rwradar.app.ui.components

import java.util.concurrent.TimeUnit

/** Small pure helpers for list rows (unit tested). */
object Labels {
    private val FUNDED_WINDOW_MS = TimeUnit.DAYS.toMillis(90)

    /** "Acme Labs" → "AL", "zepto" → "Z". */
    fun initials(name: String): String =
        name.split(' ', '-', '.', '_')
            .filter { it.isNotBlank() }
            .take(2)
            .joinToString("") { it.first().uppercase() }
            .ifEmpty { "?" }

    /** True when the last funding is within the last 90 days (the "Funded" tag). */
    fun isRecentlyFunded(lastFundingAt: Long?, now: Long): Boolean =
        lastFundingAt != null && now - lastFundingAt in 0..FUNDED_WINDOW_MS
}

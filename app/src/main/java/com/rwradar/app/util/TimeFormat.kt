package com.rwradar.app.util

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.TimeUnit

/** Plain-English relative times. Pure functions so they can be unit tested. */
object TimeFormat {
    private val DAY = TimeUnit.DAYS.toMillis(1)
    private val HOUR = TimeUnit.HOURS.toMillis(1)
    private val MINUTE = TimeUnit.MINUTES.toMillis(1)

    /** "today", "yesterday", "3 days ago", then a date ("12 Oct 2026") after 30 days. */
    fun daysAgo(then: Long, now: Long): String {
        val days = ((now - then).coerceAtLeast(0) / DAY).toInt()
        return when {
            days == 0 -> "today"
            days == 1 -> "yesterday"
            days < 30 -> "$days days ago"
            else -> "on ${date(then)}"
        }
    }

    /** "just now", "5 min ago", "3 h ago", "2 d ago", then a date. */
    fun relative(then: Long, now: Long): String {
        val diff = (now - then).coerceAtLeast(0)
        return when {
            diff < MINUTE -> "just now"
            diff < HOUR -> "${diff / MINUTE} min ago"
            diff < DAY -> "${diff / HOUR} h ago"
            diff < 7 * DAY -> "${diff / DAY} d ago"
            else -> date(then)
        }
    }

    fun date(millis: Long): String = SimpleDateFormat("d MMM yyyy", Locale.ENGLISH).format(Date(millis))

    fun monthYear(millis: Long): String = SimpleDateFormat("MMM yyyy", Locale.ENGLISH).format(Date(millis))
}

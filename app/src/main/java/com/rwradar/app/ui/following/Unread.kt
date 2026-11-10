package com.rwradar.app.ui.following

/** Unread = new jobs (firstSeenAt) + news (publishedAt) after lastViewedAt (PLAN §6.3). Pure, unit tested. */
object Unread {
    /**
     * [jobFirstSeen] and [newsPublished] are the times from the first page (≤ 20) of each list.
     * A null [lastViewedAt] (never opened) counts every dated item. Undated items never count.
     */
    fun count(jobFirstSeen: List<Long?>, newsPublished: List<Long?>, lastViewedAt: Long?): Int {
        fun isNew(t: Long?) = t != null && (lastViewedAt == null || t > lastViewedAt)
        return jobFirstSeen.count(::isNew) + newsPublished.count(::isNew)
    }
}

package com.rwradar.app.data

import com.google.firebase.Timestamp
import com.rwradar.app.data.model.Company
import com.rwradar.app.data.model.DirectoryEntry
import com.rwradar.app.data.model.Job
import com.rwradar.app.data.model.NewsItem
import com.rwradar.app.data.model.NewsTag
import com.rwradar.app.data.model.RoleFamily
import com.rwradar.app.data.model.UserPrefs
import java.util.Date

/**
 * Hand-written parsers for Firestore documents (no reflection, so R8 needs no keep rules).
 * They take the raw field map (`DocumentSnapshot.data`) and tolerate missing or mistyped fields.
 */
object FirestoreParsing {

    fun directory(data: Map<String, Any?>?): List<DirectoryEntry> =
        data.list("companies").mapNotNull { row -> (row as? Map<*, *>)?.let(::directoryEntry) }

    fun directoryEntry(row: Map<*, *>): DirectoryEntry? {
        val id = row.string("id").ifEmpty { return null }
        return DirectoryEntry(
            id = id,
            name = row.string("name").ifEmpty { id },
            aliases = row.strings("aliases"),
            sector = row.string("sector"),
            openCount = row.int("openCount"),
            newThisWeek = row.int("newThisWeek"),
            lastFundingAt = row.millis("lastFundingAt"),
            logoUrl = row.string("logoUrl"),
        )
    }

    fun company(id: String, data: Map<String, Any?>?): Company? {
        if (data == null) return null
        return Company(
            id = id,
            name = data.string("name").ifEmpty { id },
            aliases = data.strings("aliases"),
            sector = data.string("sector"),
            website = data.string("website"),
            logoUrl = data.string("logoUrl"),
            openCount = data.int("openCount"),
            newThisWeek = data.int("newThisWeek"),
            lastFundingAt = data.millis("lastFundingAt"),
        )
    }

    fun job(id: String, data: Map<String, Any?>?): Job? {
        if (data == null) return null
        return Job(
            id = id,
            title = data.string("title").ifEmpty { "Untitled role" },
            family = RoleFamily.fromKey(data.string("family")) ?: RoleFamily.OTHER,
            location = data.string("location"),
            remote = data["remote"] as? Boolean ?: false,
            dept = data.string("dept"),
            url = data.string("url"),
            postedAt = data.millis("postedAt"),
            firstSeenAt = data.millis("firstSeenAt"),
            open = data.string("status") != "closed",
        )
    }

    fun news(id: String, data: Map<String, Any?>?): NewsItem? {
        if (data == null) return null
        val title = data.string("title").ifEmpty { return null }
        return NewsItem(
            id = id,
            title = title,
            source = data.string("source"),
            url = data.string("url"),
            publishedAt = data.millis("publishedAt"),
            tag = NewsTag.fromKey(data.string("tag")),
            companyIds = data.strings("companyIds"),
        )
    }

    fun userPrefs(data: Map<String, Any?>?): UserPrefs {
        val notif = data?.get("notifPrefs") as? Map<*, *>
        return UserPrefs(
            follows = data.strings("follows").distinct(),
            families = data.strings("families").mapNotNull(RoleFamily::fromKey).toSet(),
            notifyJobs = notif?.get("jobs") as? Boolean ?: true,
            notifySignals = notif?.get("signals") as? Boolean ?: true,
        )
    }

    /** Converts a Firestore time value to epoch millis. Timestamps are the contract; the rest is tolerance. */
    fun toMillis(value: Any?): Long? = when (value) {
        is Timestamp -> value.seconds * 1000 + value.nanoseconds / 1_000_000
        is Date -> value.time
        is Long -> value
        else -> null
    }

    private fun Map<*, *>?.string(key: String): String = (this?.get(key) as? String)?.trim().orEmpty()

    private fun Map<*, *>?.int(key: String): Int = (this?.get(key) as? Number)?.toInt() ?: 0

    private fun Map<*, *>?.millis(key: String): Long? = toMillis(this?.get(key))

    private fun Map<*, *>?.list(key: String): List<Any?> = this?.get(key) as? List<*> ?: emptyList()

    private fun Map<*, *>?.strings(key: String): List<String> =
        list(key).filterIsInstance<String>().map { it.trim() }.filter { it.isNotEmpty() }
}

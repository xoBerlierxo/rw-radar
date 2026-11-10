package com.rwradar.app.data.model

// All times are epoch millis converted from Firestore Timestamps at parse time; null when unknown.

/** One summary row of `directory/v1` (D3). */
data class DirectoryEntry(
    val id: String,
    val name: String,
    val aliases: List<String> = emptyList(),
    val sector: String = "",
    val openCount: Int = 0,
    val newThisWeek: Int = 0,
    val lastFundingAt: Long? = null,
    val logoUrl: String = "",
)

/** `companies/{id}`. The app ignores `jobIndex` and the poller's bookkeeping fields. */
data class Company(
    val id: String,
    val name: String,
    val aliases: List<String> = emptyList(),
    val sector: String = "",
    val website: String = "",
    val logoUrl: String = "",
    val openCount: Int = 0,
    val newThisWeek: Int = 0,
    val lastFundingAt: Long? = null,
)

/** `companies/{id}/jobs/{jobId}`. */
data class Job(
    val id: String,
    val title: String,
    val family: RoleFamily = RoleFamily.OTHER,
    val location: String = "",
    val remote: Boolean = false,
    val dept: String = "",
    val url: String = "",
    val postedAt: Long? = null,
    val firstSeenAt: Long? = null,
    val open: Boolean = true,
)

/** `news/{hash}`. Headline, source and link only (no body, ever). */
data class NewsItem(
    val id: String,
    val title: String,
    val source: String = "",
    val url: String = "",
    val publishedAt: Long? = null,
    val tag: NewsTag = NewsTag.OTHER,
    val companyIds: List<String> = emptyList(),
)

/** `users/{uid}`. */
data class UserPrefs(
    val follows: List<String> = emptyList(),
    val families: Set<RoleFamily> = emptySet(),
    val notifyJobs: Boolean = true,
    val notifySignals: Boolean = true,
)

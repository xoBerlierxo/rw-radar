package com.rwradar.app.push

/**
 * Where a notification tap should land (CLAUDE.md §4.3). Built from the FCM data fields, which arrive
 * as intent extras (system-shown notifications) or from our own PendingIntent (foreground).
 */
data class PushTarget(
    val type: String,
    val companyId: String,
    val family: String? = null,
    /** Run start in epoch millis: jobs with `firstSeenAt >= since` are highlighted. */
    val since: Long? = null,
    val newsHash: String? = null,
) {
    val isSignal: Boolean get() = type == TYPE_SIGNAL

    fun toExtras(): Map<String, String> = buildMap {
        put(KEY_TYPE, type)
        put(KEY_COMPANY_ID, companyId)
        family?.let { put(KEY_FAMILY, it) }
        since?.let { put(KEY_SINCE, it.toString()) }
        newsHash?.let { put(KEY_NEWS_HASH, it) }
    }

    companion object {
        const val TYPE_JOBS = "jobs"
        const val TYPE_SIGNAL = "signal"

        const val KEY_TYPE = "type"
        const val KEY_COMPANY_ID = "companyId"
        const val KEY_FAMILY = "family"
        const val KEY_SINCE = "since"
        const val KEY_NEWS_HASH = "newsHash"

        /** Returns null unless both `type` (jobs|signal) and `companyId` are present. */
        fun parse(get: (String) -> String?): PushTarget? {
            val type = get(KEY_TYPE)?.takeIf { it == TYPE_JOBS || it == TYPE_SIGNAL } ?: return null
            val companyId = get(KEY_COMPANY_ID)?.takeIf { it.isNotBlank() } ?: return null
            return PushTarget(
                type = type,
                companyId = companyId,
                family = get(KEY_FAMILY)?.takeIf { it.isNotBlank() },
                since = get(KEY_SINCE)?.trim()?.toLongOrNull(),
                newsHash = get(KEY_NEWS_HASH)?.takeIf { it.isNotBlank() },
            )
        }

        fun fromData(data: Map<String, String>): PushTarget? = parse { data[it] }
    }
}

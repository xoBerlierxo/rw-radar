package com.rwradar.app.ui.company

import com.rwradar.app.data.model.Job
import com.rwradar.app.data.model.RoleFamily

/** Client-side filters over the loaded openings (M3). No family selected means all families. */
data class JobFilters(
    val families: Set<RoleFamily> = emptySet(),
    val location: String = "",
    val remoteOnly: Boolean = false,
) {
    val isActive: Boolean get() = families.isNotEmpty() || location.isNotBlank() || remoteOnly

    fun apply(jobs: List<Job>): List<Job> {
        val loc = location.trim()
        return jobs.filter { job ->
            (families.isEmpty() || job.family in families) &&
                (loc.isEmpty() || job.location.contains(loc, ignoreCase = true)) &&
                (!remoteOnly || job.remote)
        }
    }

    companion object {
        /** A job is highlighted when it was first seen in the run that sent the push (`since`). */
        fun isHighlighted(job: Job, since: Long?): Boolean =
            since != null && job.firstSeenAt != null && job.firstSeenAt >= since
    }
}

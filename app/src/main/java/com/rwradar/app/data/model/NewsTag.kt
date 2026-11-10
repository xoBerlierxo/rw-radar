package com.rwradar.app.data.model

/** News tag keys (CLAUDE.md §4.1). Unknown keys map to [OTHER]. */
enum class NewsTag(val key: String, val label: String) {
    FUNDING("funding", "Funding"),
    LAYOFFS("layoffs", "Layoffs"),
    ACQUISITION("acquisition", "Acquisition"),
    FINANCIALS("financials", "Financials"),
    OTHER("other", "Other");

    companion object {
        fun fromKey(key: String?): NewsTag = entries.firstOrNull { it.key == key } ?: OTHER
    }
}

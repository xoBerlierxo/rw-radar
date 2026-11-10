package com.rwradar.app.analytics

import android.os.Bundle
import com.google.firebase.analytics.FirebaseAnalytics

/** Thin wrapper over Firebase Analytics. Names come from [Events] and [Params]. */
class Analytics(private val firebase: FirebaseAnalytics) {

    fun log(event: String, vararg params: Pair<String, Any?>) {
        val bundle = Bundle()
        for ((key, value) in params) {
            when (value) {
                null -> Unit
                is String -> bundle.putString(key, value.take(MAX_VALUE_LENGTH))
                is Int -> bundle.putLong(key, value.toLong())
                is Long -> bundle.putLong(key, value)
                is Boolean -> bundle.putLong(key, if (value) 1L else 0L)
                is Double -> bundle.putDouble(key, value)
                else -> bundle.putString(key, value.toString().take(MAX_VALUE_LENGTH))
            }
        }
        firebase.logEvent(event, bundle)
    }

    private companion object {
        const val MAX_VALUE_LENGTH = 100 // Analytics truncates longer string values
    }
}

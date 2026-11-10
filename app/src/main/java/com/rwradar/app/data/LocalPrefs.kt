package com.rwradar.app.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringSetPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.rwradar.app.push.TopicStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "rwradar_prefs")

/** Device-local state (DataStore): onboardingDone, subscribedTopics, lastViewedAt{companyId}. */
class LocalPrefs(context: Context) : TopicStore {
    private val store = context.applicationContext.dataStore

    val onboardingDone: Flow<Boolean> = store.data.map { it[ONBOARDING_DONE] ?: false }

    suspend fun setOnboardingDone() {
        store.edit { it[ONBOARDING_DONE] = true }
    }

    /** companyId → epoch millis of the last time its detail screen was opened. */
    val lastViewedAt: Flow<Map<String, Long>> = store.data.map { prefs ->
        prefs.asMap().mapNotNull { (key, value) ->
            if (key.name.startsWith(LAST_VIEWED_PREFIX) && value is Long) {
                key.name.removePrefix(LAST_VIEWED_PREFIX) to value
            } else {
                null
            }
        }.toMap()
    }

    suspend fun setLastViewedAt(companyId: String, millis: Long = System.currentTimeMillis()) {
        store.edit { it[lastViewedKey(companyId)] = millis }
    }

    /** Starts the unread clock at follow time, so a new follow doesn't show 20 old items as unread. */
    suspend fun setLastViewedAtIfAbsent(companyId: String, millis: Long = System.currentTimeMillis()) {
        store.edit { prefs ->
            if (prefs[lastViewedKey(companyId)] == null) prefs[lastViewedKey(companyId)] = millis
        }
    }

    override suspend fun subscribedTopics(): Set<String> = store.data.first()[SUBSCRIBED_TOPICS] ?: emptySet()

    override suspend fun setSubscribedTopics(topics: Set<String>) {
        store.edit { it[SUBSCRIBED_TOPICS] = topics }
    }

    private fun lastViewedKey(companyId: String) = longPreferencesKey(LAST_VIEWED_PREFIX + companyId)

    private companion object {
        val ONBOARDING_DONE = booleanPreferencesKey("onboardingDone")
        val SUBSCRIBED_TOPICS = stringSetPreferencesKey("subscribedTopics")
        const val LAST_VIEWED_PREFIX = "lastViewedAt_"
    }
}

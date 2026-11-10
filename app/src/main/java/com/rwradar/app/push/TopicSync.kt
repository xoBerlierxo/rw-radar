package com.rwradar.app.push

import android.util.Log
import com.rwradar.app.data.model.RoleFamily
import com.rwradar.app.data.model.UserPrefs
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** FCM topic names (CLAUDE.md §4.3). */
object Topics {
    fun jobs(companyId: String, family: RoleFamily) = "c_${companyId}_${family.key}"
    fun signal(companyId: String) = "c_${companyId}_signal"

    /**
     * Desired topics (PLAN §6.4): for each followed company, `c_{id}_{family}` for each chosen family
     * if job notifications are on, plus `c_{id}_signal` if funding signals are on.
     */
    fun desired(prefs: UserPrefs): Set<String> = buildSet {
        for (companyId in prefs.follows) {
            if (prefs.notifyJobs) prefs.families.forEach { add(jobs(companyId, it)) }
            if (prefs.notifySignals) add(signal(companyId))
        }
    }

    fun diff(desired: Set<String>, subscribed: Set<String>) = TopicDiff(
        subscribe = desired - subscribed,
        unsubscribe = subscribed - desired,
    )
}

data class TopicDiff(val subscribe: Set<String>, val unsubscribe: Set<String>) {
    val isEmpty: Boolean get() = subscribe.isEmpty() && unsubscribe.isEmpty()
}

/** FCM topic calls; [FirebaseTopicClient] in the app, a fake in tests. Each call throws on failure. */
interface TopicClient {
    suspend fun subscribe(topic: String)
    suspend fun unsubscribe(topic: String)
}

/** Where the set of topics this instance is subscribed to is remembered ([com.rwradar.app.data.LocalPrefs]). */
interface TopicStore {
    suspend fun subscribedTopics(): Set<String>
    suspend fun setSubscribedTopics(topics: Set<String>)
}

data class SyncResult(val subscribed: Set<String>, val failed: Set<String>, val durationMs: Long)

/**
 * Diffs the desired topics against the stored subscribed set and applies the difference.
 * Only successful calls are stored, so failures are retried on the next sync (app start or any change).
 */
class TopicSync(
    private val client: TopicClient,
    private val store: TopicStore,
    private val clock: () -> Long = System::currentTimeMillis,
) {
    private val mutex = Mutex()

    /**
     * Applies the diff between [desired] and the stored set. With [forceResubscribe] every desired topic
     * is subscribed again (used after a new FCM token, when the instance may have lost its topics).
     */
    suspend fun sync(desired: Set<String>, forceResubscribe: Boolean = false): SyncResult = mutex.withLock {
        val start = clock()
        val stored = store.subscribedTopics()
        val diff = Topics.diff(desired, stored)
        val toSubscribe = if (forceResubscribe) desired else diff.subscribe

        val (subResults, unsubResults) = coroutineScope {
            val subs = toSubscribe.map { topic -> async { topic to runCatching { client.subscribe(topic) }.isSuccess } }
            val unsubs = diff.unsubscribe.map { topic -> async { topic to runCatching { client.unsubscribe(topic) }.isSuccess } }
            subs.awaitAll() to unsubs.awaitAll()
        }
        val subscribedOk = subResults.okTopics()
        val unsubscribedOk = unsubResults.okTopics()
        val failed = (toSubscribe - subscribedOk) + (diff.unsubscribe - unsubscribedOk)

        // Store only what succeeded: a failed subscribe is retried next time, a failed unsubscribe stays stored.
        val result = (stored - unsubscribedOk - (toSubscribe - subscribedOk)) + subscribedOk
        if (result != stored) store.setSubscribedTopics(result)

        val duration = clock() - start
        log("Topic sync: +${subscribedOk.size} -${unsubscribedOk.size} failed=${failed.size} in ${duration}ms (target < 5000ms)")
        SyncResult(subscribed = result, failed = failed, durationMs = duration)
    }

    private fun List<Pair<String, Boolean>>.okTopics(): Set<String> = filter { it.second }.map { it.first }.toSet()

    private fun log(message: String) {
        runCatching { Log.i("TopicSync", message) }
    }
}

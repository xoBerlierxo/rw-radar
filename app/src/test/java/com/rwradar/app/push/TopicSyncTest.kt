package com.rwradar.app.push

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TopicSyncTest {

    private class FakeClient(private val failing: Set<String> = emptySet()) : TopicClient {
        val subscribed = mutableListOf<String>()
        val unsubscribed = mutableListOf<String>()

        override suspend fun subscribe(topic: String) {
            if (topic in failing) error("subscribe failed: $topic")
            subscribed += topic
        }

        override suspend fun unsubscribe(topic: String) {
            if (topic in failing) error("unsubscribe failed: $topic")
            unsubscribed += topic
        }
    }

    private class FakeStore(var topics: Set<String> = emptySet()) : TopicStore {
        var writes = 0
        override suspend fun subscribedTopics() = topics
        override suspend fun setSubscribedTopics(topics: Set<String>) {
            this.topics = topics
            writes++
        }
    }

    @Test
    fun `applies only the difference and stores the result`() = runTest {
        val client = FakeClient()
        val store = FakeStore(setOf("c_a_eng", "c_old_signal"))

        val result = TopicSync(client, store).sync(setOf("c_a_eng", "c_b_eng"))

        assertEquals(listOf("c_b_eng"), client.subscribed)
        assertEquals(listOf("c_old_signal"), client.unsubscribed)
        assertEquals(setOf("c_a_eng", "c_b_eng"), store.topics)
        assertTrue(result.failed.isEmpty())
    }

    @Test
    fun `failed calls are not stored so the next sync retries them`() = runTest {
        val store = FakeStore(setOf("c_old_signal"))
        val failing = FakeClient(failing = setOf("c_b_eng", "c_old_signal"))

        val result = TopicSync(failing, store).sync(setOf("c_a_eng", "c_b_eng"))

        assertEquals(setOf("c_a_eng", "c_old_signal"), store.topics) // failed unsubscribe stays stored
        assertEquals(setOf("c_b_eng", "c_old_signal"), result.failed)

        val healthy = FakeClient()
        TopicSync(healthy, store).sync(setOf("c_a_eng", "c_b_eng"))
        assertEquals(listOf("c_b_eng"), healthy.subscribed)
        assertEquals(listOf("c_old_signal"), healthy.unsubscribed)
        assertEquals(setOf("c_a_eng", "c_b_eng"), store.topics)
    }

    @Test
    fun `no change makes no calls and no write`() = runTest {
        val client = FakeClient()
        val store = FakeStore(setOf("c_a_eng"))

        TopicSync(client, store).sync(setOf("c_a_eng"))

        assertTrue(client.subscribed.isEmpty() && client.unsubscribed.isEmpty())
        assertEquals(0, store.writes)
    }

    @Test
    fun `force resubscribe subscribes every desired topic again`() = runTest {
        val client = FakeClient()
        val store = FakeStore(setOf("c_a_eng", "c_gone_eng"))

        TopicSync(client, store).sync(setOf("c_a_eng", "c_b_eng"), forceResubscribe = true)

        assertEquals(setOf("c_a_eng", "c_b_eng"), client.subscribed.toSet())
        assertEquals(listOf("c_gone_eng"), client.unsubscribed)
        assertEquals(setOf("c_a_eng", "c_b_eng"), store.topics)
    }

    @Test
    fun `reports duration from the clock`() = runTest {
        var now = 1_000L
        val sync = TopicSync(FakeClient(), FakeStore(), clock = { now.also { now += 250 } })
        assertEquals(250L, sync.sync(setOf("c_a_eng")).durationMs)
    }
}

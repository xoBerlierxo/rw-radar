package com.rwradar.app.data

import com.google.firebase.Timestamp
import com.rwradar.app.data.model.NewsTag
import com.rwradar.app.data.model.RoleFamily
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class FirestoreParsingTest {

    private val ts = Timestamp(1_762_780_000L, 500_000_000)
    private val tsMillis = 1_762_780_000_500L

    @Test
    fun `timestamps become epoch millis`() {
        assertEquals(tsMillis, FirestoreParsing.toMillis(ts))
        assertNull(FirestoreParsing.toMillis(null))
        assertNull(FirestoreParsing.toMillis("2026-11-10"))
    }

    @Test
    fun `directory rows parse and rows without id are skipped`() {
        val data = mapOf(
            "updatedAt" to ts,
            "companies" to listOf(
                mapOf(
                    "id" to "razorpay", "name" to "Razorpay", "aliases" to listOf("Razorpay Software"),
                    "sector" to "Fintech", "openCount" to 12L, "newThisWeek" to 3L,
                    "lastFundingAt" to ts, "logoUrl" to "",
                ),
                mapOf("name" to "No id"),
                mapOf("id" to "bare"),
                "not a map",
            ),
        )
        val entries = FirestoreParsing.directory(data)
        assertEquals(listOf("razorpay", "bare"), entries.map { it.id })
        with(entries[0]) {
            assertEquals("Razorpay", name)
            assertEquals(listOf("Razorpay Software"), aliases)
            assertEquals(12, openCount)
            assertEquals(3, newThisWeek)
            assertEquals(tsMillis, lastFundingAt)
        }
        with(entries[1]) {
            assertEquals("bare", name) // falls back to the id
            assertEquals(0, openCount)
            assertNull(lastFundingAt)
        }
    }

    @Test
    fun `missing directory doc is an empty list`() {
        assertTrue(FirestoreParsing.directory(null).isEmpty())
    }

    @Test
    fun `job parses known fields and tolerates nulls`() {
        val job = FirestoreParsing.job(
            "greenhouse_1",
            mapOf(
                "title" to "Backend Engineer", "family" to "eng", "location" to "Bengaluru", "remote" to true,
                "dept" to "Engineering", "url" to "https://x", "postedAt" to null, "firstSeenAt" to ts,
                "status" to "open",
            ),
        )!!
        assertEquals(RoleFamily.ENG, job.family)
        assertTrue(job.remote)
        assertNull(job.postedAt)
        assertEquals(tsMillis, job.firstSeenAt)
        assertTrue(job.open)

        val sparse = FirestoreParsing.job("lever_2", mapOf("family" to "unknown", "status" to "closed"))!!
        assertEquals(RoleFamily.OTHER, sparse.family)
        assertFalse(sparse.remote)
        assertFalse(sparse.open)
    }

    @Test
    fun `news parses tag and drops items without a title`() {
        val news = FirestoreParsing.news(
            "hash1",
            mapOf("title" to "Acme raises 10M", "source" to "Inc42", "tag" to "funding", "companyIds" to listOf("acme")),
        )!!
        assertEquals(NewsTag.FUNDING, news.tag)
        assertEquals(listOf("acme"), news.companyIds)
        assertEquals(NewsTag.OTHER, FirestoreParsing.news("h", mapOf("title" to "x", "tag" to "weird"))!!.tag)
        assertNull(FirestoreParsing.news("h", mapOf("source" to "Inc42")))
    }

    @Test
    fun `user prefs default to notifications on and ignore unknown families`() {
        val prefs = FirestoreParsing.userPrefs(
            mapOf(
                "follows" to listOf("a", "b", "a"),
                "families" to listOf("eng", "nope", "gtm"),
                "notifPrefs" to mapOf("jobs" to false),
            ),
        )
        assertEquals(listOf("a", "b"), prefs.follows)
        assertEquals(setOf(RoleFamily.ENG, RoleFamily.GTM), prefs.families)
        assertFalse(prefs.notifyJobs)
        assertTrue(prefs.notifySignals)

        val empty = FirestoreParsing.userPrefs(null)
        assertTrue(empty.follows.isEmpty() && empty.notifyJobs && empty.notifySignals)
    }
}

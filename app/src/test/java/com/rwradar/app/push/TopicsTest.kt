package com.rwradar.app.push

import com.rwradar.app.data.model.RoleFamily
import com.rwradar.app.data.model.UserPrefs
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TopicsTest {

    private val prefs = UserPrefs(
        follows = listOf("razorpay", "zepto"),
        families = setOf(RoleFamily.ENG, RoleFamily.DATA),
        notifyJobs = true,
        notifySignals = true,
    )

    @Test
    fun `desired topics cover each followed company, family and signal`() {
        assertEquals(
            setOf(
                "c_razorpay_eng", "c_razorpay_data", "c_razorpay_signal",
                "c_zepto_eng", "c_zepto_data", "c_zepto_signal",
            ),
            Topics.desired(prefs),
        )
    }

    @Test
    fun `jobs toggle off keeps only signal topics`() {
        assertEquals(setOf("c_razorpay_signal", "c_zepto_signal"), Topics.desired(prefs.copy(notifyJobs = false)))
    }

    @Test
    fun `signals toggle off keeps only job topics`() {
        assertEquals(
            setOf("c_razorpay_eng", "c_razorpay_data", "c_zepto_eng", "c_zepto_data"),
            Topics.desired(prefs.copy(notifySignals = false)),
        )
    }

    @Test
    fun `no follows or everything off means no topics`() {
        assertTrue(Topics.desired(prefs.copy(follows = emptyList())).isEmpty())
        assertTrue(Topics.desired(prefs.copy(notifyJobs = false, notifySignals = false)).isEmpty())
    }

    @Test
    fun `topic names use family keys not labels`() {
        val all = Topics.desired(UserPrefs(follows = listOf("acme"), families = RoleFamily.entries.toSet()))
        assertEquals(
            setOf("c_acme_design", "c_acme_data", "c_acme_product", "c_acme_gtm", "c_acme_eng", "c_acme_other", "c_acme_signal"),
            all,
        )
        assertTrue(all.all { Regex("[a-zA-Z0-9-_.~%]+").matches(it) })
    }

    @Test
    fun `diff subscribes the missing and unsubscribes the extra`() {
        val diff = Topics.diff(desired = setOf("a", "b", "c"), subscribed = setOf("b", "c", "d"))
        assertEquals(setOf("a"), diff.subscribe)
        assertEquals(setOf("d"), diff.unsubscribe)
    }

    @Test
    fun `diff of equal sets is empty`() {
        assertTrue(Topics.diff(setOf("a"), setOf("a")).isEmpty)
    }
}

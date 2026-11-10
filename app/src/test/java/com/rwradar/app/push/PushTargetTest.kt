package com.rwradar.app.push

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PushTargetTest {

    @Test
    fun `parses a jobs push`() {
        val target = PushTarget.fromData(
            mapOf("type" to "jobs", "companyId" to "razorpay", "family" to "eng", "since" to "1762780000000"),
        )
        assertEquals(PushTarget("jobs", "razorpay", family = "eng", since = 1_762_780_000_000L), target)
    }

    @Test
    fun `parses a signal push`() {
        val target = PushTarget.fromData(mapOf("type" to "signal", "companyId" to "zepto", "newsHash" to "abc123"))
        assertEquals(PushTarget("signal", "zepto", newsHash = "abc123"), target)
        assertEquals(true, target?.isSignal)
    }

    @Test
    fun `ignores unrelated or incomplete extras`() {
        assertNull(PushTarget.fromData(emptyMap()))
        assertNull(PushTarget.fromData(mapOf("type" to "jobs")))
        assertNull(PushTarget.fromData(mapOf("type" to "promo", "companyId" to "x")))
    }

    @Test
    fun `bad since is dropped, not fatal`() {
        assertNull(PushTarget.fromData(mapOf("type" to "jobs", "companyId" to "x", "since" to "soon"))?.since)
    }

    @Test
    fun `extras round trip`() {
        val target = PushTarget("jobs", "razorpay", "eng", 42L, null)
        assertEquals(target, PushTarget.fromData(target.toExtras()))
    }
}

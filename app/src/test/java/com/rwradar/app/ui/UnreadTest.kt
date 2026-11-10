package com.rwradar.app.ui

import com.rwradar.app.ui.following.Unread
import org.junit.Assert.assertEquals
import org.junit.Test

class UnreadTest {

    @Test
    fun `counts jobs and news strictly after last viewed`() {
        assertEquals(3, Unread.count(listOf(50L, 100L, 150L, 200L), listOf(101L, 90L), lastViewedAt = 100L))
    }

    @Test
    fun `undated items never count`() {
        assertEquals(1, Unread.count(listOf(null, 200L), listOf(null), lastViewedAt = 100L))
    }

    @Test
    fun `never viewed counts every dated item`() {
        assertEquals(3, Unread.count(listOf(1L, 2L), listOf(3L, null), lastViewedAt = null))
    }

    @Test
    fun `nothing new is zero`() {
        assertEquals(0, Unread.count(emptyList(), emptyList(), lastViewedAt = 5L))
        assertEquals(0, Unread.count(listOf(1L), listOf(2L), lastViewedAt = 5L))
    }
}

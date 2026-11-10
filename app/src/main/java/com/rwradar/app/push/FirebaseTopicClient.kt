package com.rwradar.app.push

import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.tasks.await

class FirebaseTopicClient(private val messaging: FirebaseMessaging) : TopicClient {
    override suspend fun subscribe(topic: String) {
        messaging.subscribeToTopic(topic).await()
    }

    override suspend fun unsubscribe(topic: String) {
        messaging.unsubscribeFromTopic(topic).await()
    }
}

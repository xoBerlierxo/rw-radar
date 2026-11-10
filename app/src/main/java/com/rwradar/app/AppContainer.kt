package com.rwradar.app

import android.content.Context
import com.google.firebase.analytics.FirebaseAnalytics
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.messaging.FirebaseMessaging
import com.rwradar.app.analytics.Analytics
import com.rwradar.app.analytics.Events
import com.rwradar.app.analytics.Params
import com.rwradar.app.data.AuthRepository
import com.rwradar.app.data.CompanyRepository
import com.rwradar.app.data.DirectoryRepository
import com.rwradar.app.data.LocalPrefs
import com.rwradar.app.data.UserRepository
import com.rwradar.app.push.FirebaseTopicClient
import com.rwradar.app.push.TopicSync
import com.rwradar.app.push.Topics
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch

/** Manual DI (no Hilt): one instance, created in [RwRadarApp]. */
class AppContainer(context: Context) {
    val appScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    private val firestore = FirebaseFirestore.getInstance()

    val analytics = Analytics(FirebaseAnalytics.getInstance(context))
    val localPrefs = LocalPrefs(context)
    val authRepository = AuthRepository(FirebaseAuth.getInstance())
    val userRepository = UserRepository(firestore, authRepository, appScope)
    val directoryRepository = DirectoryRepository(firestore)
    val companyRepository = CompanyRepository(firestore)
    val topicSync = TopicSync(FirebaseTopicClient(FirebaseMessaging.getInstance()), localPrefs)

    /** Re-syncs topics on start and whenever follows, families or notifPrefs change (PLAN §6.4). */
    fun start() {
        // userRepository.prefs starts eagerly: it signs in anonymously, then listens to users/{uid}.
        appScope.launch {
            userRepository.prefs
                .filterNotNull()
                .map { Topics.desired(it) }
                .distinctUntilChanged()
                .collect { topicSync.sync(it) }
        }
    }

    /** After a new FCM token: subscribe every desired topic again. */
    fun resyncTopics() {
        val prefs = userRepository.prefs.value ?: return
        appScope.launch { topicSync.sync(Topics.desired(prefs), forceResubscribe = true) }
    }

    /** One-tap follow/unfollow from any screen (M2): Firestore, unread clock and analytics. */
    fun setFollowing(companyId: String, follow: Boolean, source: String) {
        if (follow) {
            userRepository.follow(companyId)
            appScope.launch { localPrefs.setLastViewedAtIfAbsent(companyId) }
            analytics.log(Events.FOLLOW_COMPANY, Params.ID to companyId, Params.SOURCE to source)
        } else {
            userRepository.unfollow(companyId)
            analytics.log(Events.UNFOLLOW_COMPANY, Params.ID to companyId)
        }
    }
}

package com.rwradar.app.data

import com.google.firebase.auth.FirebaseAuth
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.tasks.await

/** Anonymous Firebase Auth. Follows are stored against this uid (M2, D12). */
class AuthRepository(private val auth: FirebaseAuth) {
    private val mutex = Mutex()

    val currentUid: String? get() = auth.currentUser?.uid

    /** Returns the uid, signing in anonymously first if needed. Throws if sign-in fails (e.g. offline on first launch). */
    suspend fun awaitUid(): String = mutex.withLock {
        auth.currentUser?.uid ?: checkNotNull(auth.signInAnonymously().await().user?.uid) {
            "Anonymous sign-in returned no user"
        }
    }
}

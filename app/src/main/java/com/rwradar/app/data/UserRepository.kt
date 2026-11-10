package com.rwradar.app.data

import android.util.Log
import com.google.firebase.firestore.DocumentReference
import com.google.firebase.firestore.FieldValue
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.SetOptions
import com.rwradar.app.data.model.RoleFamily
import com.rwradar.app.data.model.UserPrefs
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.emitAll
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.mapNotNull
import kotlinx.coroutines.flow.retryWhen
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/**
 * `users/{uid}`: follows, families and notifPrefs.
 *
 * [prefs] is backed by a snapshot listener. Writes are fire-and-forget: the Firestore local cache
 * applies them immediately (the listener emits the pending write), and syncs when online.
 */
class UserRepository(
    private val db: FirebaseFirestore,
    private val auth: AuthRepository,
    private val scope: CoroutineScope,
) {
    /** null until the user doc has been read (or created) for the first time. */
    val prefs: StateFlow<UserPrefs?> = flow {
        val ref = userDoc()
        emitAll(
            ref.snapshots().mapNotNull { snapshot ->
                if (!snapshot.exists()) {
                    // Create the doc with defaults, but only when the server confirms it is missing.
                    if (!snapshot.metadata.isFromCache) createDefaults(ref)
                    null
                } else {
                    FirestoreParsing.userPrefs(snapshot.data)
                }
            }
        )
    }.retryWhen { cause, attempt ->
        Log.w(TAG, "User doc listener failed (attempt $attempt)", cause)
        delay((2_000L shl attempt.toInt().coerceAtMost(4)))
        true
    }.stateIn(scope, SharingStarted.Eagerly, null)

    fun follow(companyId: String) = write(mapOf("follows" to FieldValue.arrayUnion(companyId)))

    fun unfollow(companyId: String) = write(mapOf("follows" to FieldValue.arrayRemove(companyId)))

    fun setFamilies(families: Set<RoleFamily>) =
        write(mapOf("families" to RoleFamily.entries.filter { it in families }.map { it.key }))

    fun setNotifyJobs(on: Boolean) = write(mapOf("notifPrefs" to mapOf("jobs" to on)))

    fun setNotifySignals(on: Boolean) = write(mapOf("notifPrefs" to mapOf("signals" to on)))

    private suspend fun userDoc(): DocumentReference =
        db.collection("users").document(auth.awaitUid())

    private fun createDefaults(ref: DocumentReference) {
        val defaults = mapOf(
            "follows" to emptyList<String>(),
            "families" to emptyList<String>(),
            "notifPrefs" to mapOf("jobs" to true, "signals" to true),
            "createdAt" to FieldValue.serverTimestamp(),
        )
        ref.set(defaults).addOnFailureListener { Log.w(TAG, "Creating user doc failed", it) }
    }

    /** Merge write: works whether or not the doc exists yet, and leaves other fields alone. */
    private fun write(fields: Map<String, Any>) {
        // UNDISPATCHED keeps the call order of rapid writes (follow then unfollow) once the uid is known.
        scope.launch(start = CoroutineStart.UNDISPATCHED) {
            runCatching { userDoc() }
                .onSuccess { ref ->
                    ref.set(fields, SetOptions.merge())
                        .addOnFailureListener { Log.w(TAG, "User doc write failed: ${fields.keys}", it) }
                }
                .onFailure { Log.w(TAG, "No uid for write: ${fields.keys}", it) }
        }
    }

    private companion object {
        const val TAG = "UserRepository"
    }
}

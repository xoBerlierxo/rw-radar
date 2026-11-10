package com.rwradar.app.data

import com.google.firebase.firestore.DocumentReference
import com.google.firebase.firestore.DocumentSnapshot
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow

/** Snapshot listener as a cold Flow. Local (pending) writes are emitted too, so the UI updates optimistically. */
internal fun DocumentReference.snapshots(): Flow<DocumentSnapshot> = callbackFlow {
    val registration = addSnapshotListener { snapshot, error ->
        when {
            error != null -> close(error)
            snapshot != null -> trySend(snapshot)
        }
    }
    awaitClose { registration.remove() }
}

/** One page of a Firestore list query. [cursor] is the last document, used with `startAfter`. */
data class Page<T>(val items: List<T>, val cursor: DocumentSnapshot?, val endReached: Boolean)

const val PAGE_SIZE = 20L

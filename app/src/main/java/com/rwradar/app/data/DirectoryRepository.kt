package com.rwradar.app.data

import com.google.firebase.firestore.FirebaseFirestore
import com.rwradar.app.data.model.DirectoryEntry
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

/** Listens to the single `directory/v1` doc (D3). Search and sort happen in memory. */
class DirectoryRepository(private val db: FirebaseFirestore) {
    fun observe(): Flow<List<DirectoryEntry>> =
        db.collection("directory").document("v1").snapshots()
            .map { FirestoreParsing.directory(it.data) }
}

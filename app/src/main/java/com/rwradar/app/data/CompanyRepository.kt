package com.rwradar.app.data

import com.google.firebase.firestore.DocumentSnapshot
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.Query
import com.rwradar.app.data.model.Company
import com.rwradar.app.data.model.Job
import com.rwradar.app.data.model.NewsItem
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.tasks.await

/** Company doc, openings and news pages (CLAUDE.md §4.2 queries). Pages are capped at 20 docs. */
class CompanyRepository(private val db: FirebaseFirestore) {

    fun observeCompany(id: String): Flow<Company?> =
        db.collection("companies").document(id).snapshots()
            .map { FirestoreParsing.company(id, it.data) }

    suspend fun jobsPage(companyId: String, after: DocumentSnapshot? = null): Page<Job> {
        var query = db.collection("companies").document(companyId).collection("jobs")
            .whereEqualTo("status", "open")
            .orderBy("firstSeenAt", Query.Direction.DESCENDING)
            .limit(PAGE_SIZE)
        if (after != null) query = query.startAfter(after)
        val docs = query.get().await().documents
        return Page(
            items = docs.mapNotNull { FirestoreParsing.job(it.id, it.data) },
            cursor = docs.lastOrNull() ?: after,
            endReached = docs.size < PAGE_SIZE,
        )
    }

    suspend fun newsPage(companyId: String, after: DocumentSnapshot? = null): Page<NewsItem> {
        var query = db.collection("news")
            .whereArrayContains("companyIds", companyId)
            .orderBy("publishedAt", Query.Direction.DESCENDING)
            .limit(PAGE_SIZE)
        if (after != null) query = query.startAfter(after)
        val docs = query.get().await().documents
        return Page(
            items = docs.mapNotNull { FirestoreParsing.news(it.id, it.data) },
            cursor = docs.lastOrNull() ?: after,
            endReached = docs.size < PAGE_SIZE,
        )
    }
}

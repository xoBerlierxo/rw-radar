package com.rwradar.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.rwradar.app.R
import com.rwradar.app.data.model.Job
import com.rwradar.app.util.TimeFormat

/** Opening row: title, location, dept, posted date, Remote badge; highlighted when new since a push (M4). */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun JobRow(job: Job, highlighted: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier, now: Long = System.currentTimeMillis()) {
    val background = if (highlighted) MaterialTheme.colorScheme.primaryContainer else Color.Transparent
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(background)
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        if (highlighted) {
            Tag(
                stringResource(R.string.tag_new),
                container = MaterialTheme.colorScheme.primary,
                content = MaterialTheme.colorScheme.onPrimary,
            )
        }
        Text(job.title, style = MaterialTheme.typography.titleMedium)
        val meta = listOf(job.location, job.dept).filter { it.isNotBlank() }.joinToString(" · ")
        if (meta.isNotEmpty()) {
            Text(meta, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            itemVerticalAlignment = Alignment.CenterVertically,
        ) {
            Text(postedLabel(job, now), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (job.remote) {
                Tag(
                    stringResource(R.string.tag_remote),
                    container = MaterialTheme.colorScheme.secondaryContainer,
                    content = MaterialTheme.colorScheme.onSecondaryContainer,
                )
            }
        }
    }
}

@Composable
private fun postedLabel(job: Job, now: Long): String = when {
    job.postedAt != null -> stringResource(R.string.job_posted, TimeFormat.daysAgo(job.postedAt, now))
    job.firstSeenAt != null -> stringResource(R.string.job_first_seen, TimeFormat.date(job.firstSeenAt))
    else -> ""
}

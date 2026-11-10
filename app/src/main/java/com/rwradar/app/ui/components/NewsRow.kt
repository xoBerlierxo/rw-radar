package com.rwradar.app.ui.components

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
import androidx.compose.ui.unit.dp
import com.rwradar.app.data.model.NewsItem
import com.rwradar.app.data.model.NewsTag
import com.rwradar.app.util.TimeFormat

/** News row: headline, source, relative time, tag chip (M6). */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun NewsRow(item: NewsItem, onClick: () -> Unit, modifier: Modifier = Modifier, now: Long = System.currentTimeMillis()) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(item.title, style = MaterialTheme.typography.titleMedium)
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            itemVerticalAlignment = Alignment.CenterVertically,
        ) {
            NewsTagChip(item.tag)
            val meta = listOfNotNull(
                item.source.takeIf { it.isNotBlank() },
                item.publishedAt?.let { TimeFormat.relative(it, now) },
            ).joinToString(" · ")
            Text(meta, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun NewsTagChip(tag: NewsTag) {
    val colors = MaterialTheme.colorScheme
    when (tag) {
        NewsTag.FUNDING -> Tag(tag.label, container = colors.primaryContainer, content = colors.onPrimaryContainer)
        NewsTag.LAYOFFS -> Tag(tag.label, container = colors.errorContainer, content = colors.onErrorContainer)
        NewsTag.ACQUISITION, NewsTag.FINANCIALS -> Tag(tag.label)
        NewsTag.OTHER -> Tag(tag.label, container = colors.surfaceVariant, content = colors.onSurfaceVariant)
    }
}

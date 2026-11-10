package com.rwradar.app.ui.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.rwradar.app.R
import com.rwradar.app.data.model.DirectoryEntry
import com.rwradar.app.util.TimeFormat

/** Directory row: avatar, name, sector, open count, "Funded" tag, and a trailing slot (FollowButton). */
@Composable
fun CompanyRow(
    entry: DirectoryEntry,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    now: Long = System.currentTimeMillis(),
    extraLine: (@Composable () -> Unit)? = null,
    trailing: @Composable () -> Unit = {},
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        CompanyAvatar(entry.name, entry.logoUrl)
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(
                entry.name,
                style = MaterialTheme.typography.titleMedium,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            val details = listOfNotNull(
                entry.sector.takeIf { it.isNotBlank() },
                pluralStringResource(R.plurals.open_roles, entry.openCount, entry.openCount),
            ).joinToString(" · ")
            Text(details, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (Labels.isRecentlyFunded(entry.lastFundingAt, now)) {
                Tag(stringResource(R.string.tag_funded, TimeFormat.monthYear(entry.lastFundingAt!!)))
            }
            extraLine?.invoke()
        }
        trailing()
    }
}

package com.rwradar.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import coil3.compose.SubcomposeAsyncImage

/** Logo when [logoUrl] is set and loads, otherwise an initials avatar. */
@Composable
fun CompanyAvatar(name: String, logoUrl: String, modifier: Modifier = Modifier, size: Dp = 44.dp) {
    val shape = RoundedCornerShape(size / 4)
    val box = modifier.size(size).clip(shape)
    if (logoUrl.isBlank()) {
        InitialsAvatar(name, box)
    } else {
        SubcomposeAsyncImage(
            model = logoUrl,
            contentDescription = null,
            contentScale = ContentScale.Fit,
            modifier = box.background(MaterialTheme.colorScheme.surfaceVariant),
            loading = { InitialsAvatar(name, Modifier.size(size)) },
            error = { InitialsAvatar(name, Modifier.size(size)) },
        )
    }
}

@Composable
private fun InitialsAvatar(name: String, modifier: Modifier) {
    Box(
        modifier = modifier.background(MaterialTheme.colorScheme.primaryContainer),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            Labels.initials(name),
            style = MaterialTheme.typography.titleSmall,
            color = MaterialTheme.colorScheme.onPrimaryContainer,
            maxLines = 1,
        )
    }
}

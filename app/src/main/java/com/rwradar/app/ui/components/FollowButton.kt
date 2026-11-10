package com.rwradar.app.ui.components

import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import com.rwradar.app.R

/** One-tap follow/unfollow (M2). */
@Composable
fun FollowButton(following: Boolean, onToggle: () -> Unit, modifier: Modifier = Modifier) {
    val iconModifier = Modifier.padding(end = ButtonDefaults.IconSpacing).size(ButtonDefaults.IconSize)
    val padding = ButtonDefaults.ButtonWithIconContentPadding
    if (following) {
        FilledTonalButton(onClick = onToggle, modifier = modifier, contentPadding = padding) {
            Icon(Icons.Filled.Check, contentDescription = null, modifier = iconModifier)
            Text(stringResource(R.string.action_following), maxLines = 1)
        }
    } else {
        OutlinedButton(onClick = onToggle, modifier = modifier, contentPadding = padding) {
            Icon(Icons.Filled.Add, contentDescription = null, modifier = iconModifier)
            Text(stringResource(R.string.action_follow), maxLines = 1)
        }
    }
}

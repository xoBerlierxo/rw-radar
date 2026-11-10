package com.rwradar.app.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.rwradar.app.data.model.RoleFamily

/** Multi-select role-family chips (onboarding, settings, openings filter). */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun FamilyChips(
    selected: Set<RoleFamily>,
    onToggle: (RoleFamily) -> Unit,
    modifier: Modifier = Modifier,
) {
    FlowRow(
        modifier = modifier,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        RoleFamily.entries.forEach { family ->
            val isSelected = family in selected
            FilterChip(
                selected = isSelected,
                onClick = { onToggle(family) },
                label = { Text(family.label) },
                leadingIcon = if (isSelected) {
                    { Icon(Icons.Filled.Check, contentDescription = null, modifier = Modifier.size(FilterChipDefaults.IconSize)) }
                } else {
                    null
                },
            )
        }
    }
}

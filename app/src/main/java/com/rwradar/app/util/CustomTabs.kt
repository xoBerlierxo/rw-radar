package com.rwradar.app.util

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.util.Log
import android.widget.Toast
import androidx.browser.customtabs.CustomTabsClient
import androidx.browser.customtabs.CustomTabsIntent
import androidx.core.net.toUri
import com.rwradar.app.R

/**
 * Opens external links (apply, news, ReferralWorld) in a Custom Tab, falling back to ACTION_VIEW
 * when no browser supports Custom Tabs.
 */
fun Context.openExternalUrl(url: String) {
    val uri = url.trim().toUri()
    if (uri.scheme != "https" && uri.scheme != "http") {
        Toast.makeText(this, R.string.error_bad_link, Toast.LENGTH_SHORT).show()
        return
    }
    val hasCustomTabsBrowser = CustomTabsClient.getPackageName(this, null) != null
    try {
        if (hasCustomTabsBrowser) {
            CustomTabsIntent.Builder().setShowTitle(true).build().launchUrl(this, uri)
        } else {
            startActivity(Intent(Intent.ACTION_VIEW, uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
    } catch (e: ActivityNotFoundException) {
        Log.w("CustomTabs", "No app can open $url", e)
        Toast.makeText(this, R.string.error_no_browser, Toast.LENGTH_SHORT).show()
    }
}

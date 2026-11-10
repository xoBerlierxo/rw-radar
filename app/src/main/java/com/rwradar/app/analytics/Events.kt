package com.rwradar.app.analytics

/** Every analytics event name (PLAN §6.6). Don't log an event whose name isn't here. */
object Events {
    const val ONBOARDING_COMPLETE = "onboarding_complete" // families, follows
    const val FOLLOW_COMPANY = "follow_company" // id, source
    const val UNFOLLOW_COMPANY = "unfollow_company" // id
    const val VIEW_COMPANY = "view_company" // id, source
    const val APPLY_CLICK = "apply_click" // id, family
    const val NEWS_CLICK = "news_click" // id, tag
    const val REFERRALWORLD_CLICK = "referralworld_click" // id
    const val NOTIF_OPEN = "notif_open" // type, id
    const val PREFS_CHANGED = "prefs_changed" // families
    const val NOTIF_TOGGLE = "notif_toggle" // kind, on
}

/** Event parameter names (PLAN §6.6). */
object Params {
    const val FAMILIES = "families"
    const val FOLLOWS = "follows"
    const val ID = "id"
    const val SOURCE = "source"
    const val FAMILY = "family"
    const val TAG = "tag"
    const val TYPE = "type"
    const val KIND = "kind"
    const val ON = "on"
}

/** Values for [Params.SOURCE] and [Params.KIND]. */
object ParamValues {
    const val SOURCE_ONBOARDING = "onboarding"
    const val SOURCE_DISCOVER = "discover"
    const val SOURCE_FOLLOWING = "following"
    const val SOURCE_DETAIL = "detail"
    const val SOURCE_NOTIFICATION = "notification"

    const val KIND_JOBS = "jobs"
    const val KIND_SIGNALS = "signals"
}

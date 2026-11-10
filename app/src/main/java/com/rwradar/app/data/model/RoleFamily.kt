package com.rwradar.app.data.model

/** Role families (D9). Data and topics use [key]; only the UI shows [label]. Declared in classifier order. */
enum class RoleFamily(val key: String, val label: String) {
    DESIGN("design", "Design"),
    DATA("data", "Data"),
    PRODUCT("product", "Product"),
    GTM("gtm", "Marketing/Sales"),
    ENG("eng", "Engineering"),
    OTHER("other", "Other");

    companion object {
        fun fromKey(key: String?): RoleFamily? = entries.firstOrNull { it.key == key }
    }
}

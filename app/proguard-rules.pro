# RW Radar R8 rules.
#
# Firestore documents are parsed by hand from maps (data/FirestoreParsing.kt), so the model
# classes need no reflection keep rules. Library consumer rules (Firebase, Coil, OkHttp,
# DataStore, Compose) ship inside their AARs.

# Readable Crashlytics stack traces (mapping file is uploaded by the Crashlytics plugin).
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile
-keep public class * extends java.lang.Exception

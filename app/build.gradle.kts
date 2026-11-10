import com.android.build.gradle.internal.api.BaseVariantOutputImpl
import com.google.firebase.crashlytics.buildtools.gradle.CrashlyticsExtension
import java.util.Properties
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.google.services)
    alias(libs.plugins.firebase.crashlytics)
}

// Owner-provided values live in local.properties or the environment, never in the repo (CLAUDE.md §7).
val localProps = Properties().apply {
    val file = rootProject.file("local.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}

fun localOrEnv(key: String): String? =
    (localProps.getProperty(key) ?: System.getenv(key))?.trim()?.takeIf { it.isNotEmpty() }

// ReferralWorld Careers homepage: plain link, no params or deep links (M8/D11).
val referralWorldUrl = localOrEnv("rwradar.referralworldUrl") ?: "https://www.referralworldcareers.com/"

val keystoreFile = localOrEnv("RWRADAR_KEYSTORE_FILE")
val keystorePassword = localOrEnv("RWRADAR_KEYSTORE_PASSWORD")
val keyAlias = localOrEnv("RWRADAR_KEY_ALIAS")
val keyPassword = localOrEnv("RWRADAR_KEY_PASSWORD")
val hasReleaseSigning = listOf(keystoreFile, keystorePassword, keyAlias, keyPassword).all { it != null } &&
    rootProject.file(keystoreFile!!).exists()
if (!hasReleaseSigning) {
    logger.info("RW Radar: release signing props missing (CLAUDE.md §7); the release APK will be unsigned.")
}

// Crashlytics mapping upload (release): on with a real google-services.json. A placeholder file has a
// fake app id, so the upload is skipped there; `rwradar.crashlyticsMappingUpload=false` also turns it off.
val uploadCrashlyticsMapping = file("google-services.json").let { f ->
    f.exists() && !f.readText().contains("rw-radar-placeholder")
} && localOrEnv("rwradar.crashlyticsMappingUpload") != "false"

android {
    namespace = "com.rwradar.app"
    compileSdk {
        version = release(36)
    }

    defaultConfig {
        applicationId = "com.rwradar.app"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"

        buildConfigField("String", "REFERRALWORLD_URL", "\"$referralWorldUrl\"")
    }

    signingConfigs {
        if (hasReleaseSigning) {
            create("release") {
                storeFile = rootProject.file(keystoreFile!!)
                storePassword = keystorePassword
                this.keyAlias = keyAlias
                this.keyPassword = keyPassword
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            // Left unsigned (and the build still succeeds) when the signing props are missing.
            signingConfig = signingConfigs.findByName("release")
            configure<CrashlyticsExtension> {
                mappingFileUploadEnabled = uploadCrashlyticsMapping
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    testOptions {
        unitTests.isReturnDefaultValues = true
    }

    // APK name: rw-radar-<versionName>.apk (CLAUDE.md §5). The legacy variant API still works on AGP 8.x.
    @Suppress("DEPRECATION")
    applicationVariants.all {
        val variant = this
        outputs.all {
            val suffix = when {
                variant.buildType.name == "release" && variant.signingConfig == null -> "-unsigned"
                variant.buildType.name == "release" -> ""
                else -> "-${variant.buildType.name}"
            }
            (this as BaseVariantOutputImpl).outputFileName = "rw-radar-${variant.versionName}$suffix.apk"
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.browser)
    implementation(libs.androidx.datastore.preferences)

    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons.extended)
    debugImplementation(libs.androidx.compose.ui.tooling)

    implementation(platform(libs.firebase.bom))
    implementation(libs.firebase.auth)
    implementation(libs.firebase.firestore)
    implementation(libs.firebase.messaging)
    implementation(libs.firebase.analytics)
    implementation(libs.firebase.crashlytics)

    implementation(libs.coil.compose)
    implementation(libs.coil.network.okhttp)
    implementation(libs.kotlinx.coroutines.play.services)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
}

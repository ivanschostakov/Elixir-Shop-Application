const { AndroidConfig, createRunOncePlugin, withAndroidManifest } = require("expo/config-plugins")

const PLUGIN_NAME = "with-android-play-policy-permissions"

const BLOCKED_MEDIA_PERMISSIONS = [
    "android.permission.READ_EXTERNAL_STORAGE",
    "android.permission.WRITE_EXTERNAL_STORAGE",
    "android.permission.READ_MEDIA_IMAGES",
    "android.permission.READ_MEDIA_VIDEO",
    "android.permission.READ_MEDIA_VISUAL_USER_SELECTED",
]

function withAndroidPlayPolicyPermissions(config) {
    config = AndroidConfig.Permissions.withBlockedPermissions(config, BLOCKED_MEDIA_PERMISSIONS)

    return withAndroidManifest(config, (config) => {
        const mainApplication = AndroidConfig.Manifest.getMainApplicationOrThrow(config.modResults)
        delete mainApplication.$["android:requestLegacyExternalStorage"]
        return config
    })
}

module.exports = createRunOncePlugin(withAndroidPlayPolicyPermissions, PLUGIN_NAME, "1.0.0")

const {
  createRunOncePlugin,
  withEntitlementsPlist,
  withXcodeProject,
} = require("expo/config-plugins")

const PLUGIN_NAME = "with-app-attest-environment"
const APP_ATTEST_ENTITLEMENT = "com.apple.developer.devicecheck.appattest-environment"
const APP_ATTEST_BUILD_SETTING = "$(APP_ATTEST_ENVIRONMENT)"

function getEnvironmentForConfiguration(name) {
  const normalizedName = String(name ?? "").toLowerCase()

  if (normalizedName.includes("debug")) {
    return "development"
  }

  if (normalizedName.includes("release")) {
    return "production"
  }

  return null
}

function withAppAttestEnvironment(config) {
  config = withEntitlementsPlist(config, (config) => {
    config.modResults[APP_ATTEST_ENTITLEMENT] = APP_ATTEST_BUILD_SETTING
    return config
  })

  return withXcodeProject(config, (config) => {
    const buildConfigurations = config.modResults.pbxXCBuildConfigurationSection()

    for (const entry of Object.values(buildConfigurations)) {
      if (!entry || typeof entry !== "object" || !entry.buildSettings) {
        continue
      }

      const environment = getEnvironmentForConfiguration(entry.name)

      if (environment) {
        entry.buildSettings.APP_ATTEST_ENVIRONMENT = environment
      }
    }

    return config
  })
}

module.exports = createRunOncePlugin(withAppAttestEnvironment, PLUGIN_NAME, "1.0.0")

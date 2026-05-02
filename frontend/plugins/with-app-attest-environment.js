const {
  createRunOncePlugin,
  withEntitlementsPlist,
  withXcodeProject,
} = require("expo/config-plugins")

const PLUGIN_NAME = "with-app-attest-environment"
const APP_ATTEST_ENTITLEMENT = "com.apple.developer.devicecheck.appattest-environment"

function resolveAppAttestEntitlementEnvironment() {
  const explicit = String(process.env.APP_ATTEST_ENVIRONMENT ?? "").trim().toLowerCase()
  if (explicit === "development" || explicit === "production") {
    return explicit
  }

  const profile = String(process.env.EAS_BUILD_PROFILE ?? "").trim().toLowerCase()
  if (profile === "development" || profile === "preview") {
    return "development"
  }

  return "production"
}

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
  const entitlementEnvironment = resolveAppAttestEntitlementEnvironment()

  config = withEntitlementsPlist(config, (config) => {
    config.modResults[APP_ATTEST_ENTITLEMENT] = entitlementEnvironment
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

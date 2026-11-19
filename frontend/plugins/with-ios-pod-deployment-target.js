const { withPodfile } = require("expo/config-plugins")

const postInstallHook = /^([ \t]*)post_install do \|installer\|$/m
const deploymentTargetBlock = `
    # Resource bundles can retain a lower deployment target than the app.
    minimum_ios = podfile_properties['ios.deploymentTarget'] || '15.1'
    installer.pods_project.targets.each do |target|
      target.build_configurations.each do |build_config|
        current_ios = build_config.build_settings['IPHONEOS_DEPLOYMENT_TARGET']
        next unless current_ios && Gem::Version.correct?(current_ios)
        next unless Gem::Version.new(current_ios) < Gem::Version.new(minimum_ios)

        build_config.build_settings['IPHONEOS_DEPLOYMENT_TARGET'] = minimum_ios
      end
    end
`

module.exports = (config) => withPodfile(config, (config) => {
    const { contents } = config.modResults
    if (contents.includes(deploymentTargetBlock)) return config

    const hook = contents.match(postInstallHook)
    if (!hook) throw new Error("Could not find the iOS Podfile post_install hook")

    // Apply this after React Native's own post-install build settings.
    const hookEnd = new RegExp(`^${hook[1]}end$`, "m")
    const bodyStart = hook.index + hook[0].length
    const body = contents.slice(bodyStart)
    if (!hookEnd.test(body)) throw new Error("Could not find the end of the iOS Podfile post_install hook")

    config.modResults.contents = contents.slice(0, bodyStart) + body.replace(hookEnd, (end) => `${deploymentTargetBlock}${end}`)
    return config
})

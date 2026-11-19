const { withAppDelegate, withInfoPlist } = require("expo/config-plugins")

// SDK 54 predates Expo's scene runtime. Remove this adapter when upgrading to
// an Expo SDK with built-in scene support: https://github.com/expo/fyi/blob/main/ios-scene-lifecycle.md
const marker = "// Elixir UIKit scene lifecycle (Expo SDK 54 compatibility)."
const legacyStartup = /#if os\(iOS\) \|\| os\(tvOS\)\r?\n\s*window = UIWindow\(frame: UIScreen\.main\.bounds\)\r?\n\s*factory\.startReactNative\(\r?\n\s*withModuleName: "main",\r?\n\s*in: window,\r?\n\s*launchOptions: launchOptions\)\r?\n#endif/

const sceneDelegate = `
${marker}
class ElixirSceneDelegate: UIResponder, UIWindowSceneDelegate {
  var window: UIWindow?

  private var appDelegate: AppDelegate? {
    UIApplication.shared.delegate as? AppDelegate
  }

  func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options connectionOptions: UIScene.ConnectionOptions) {
    guard let windowScene = scene as? UIWindowScene, let appDelegate else { return }

    let window = appDelegate.window ?? UIWindow(windowScene: windowScene)
    window.windowScene = windowScene
    window.frame = windowScene.coordinateSpace.bounds
    self.window = window
    appDelegate.window = window

    // Release starts React Native only after UIKit has supplied its scene.
    // Debug keeps Expo SDK 54's dev-launcher window and existing React host.
    if window.rootViewController == nil, let factory = appDelegate.reactNativeFactory {
      var launchOptions = appDelegate.sceneLaunchOptions ?? [:]
      if let context = connectionOptions.urlContexts.first {
        launchOptions[.url] = context.url
        launchOptions[.sourceApplication] = context.options.sourceApplication
        launchOptions[.annotation] = context.options.annotation
      }
      if let activity = connectionOptions.userActivities.first {
        launchOptions[.userActivityDictionary] = [
          UIApplication.LaunchOptionsKey.userActivityType.rawValue: activity.activityType,
          "UIApplicationLaunchOptionsUserActivityKey": activity
        ]
      }
      if let response = connectionOptions.notificationResponse {
        launchOptions[.remoteNotification] = response.notification.request.content.userInfo
      }
      factory.startReactNative(withModuleName: "main", in: window, launchOptions: launchOptions)
    }
    appDelegate.sceneLaunchOptions = nil
    window.makeKeyAndVisible()
  }

  // SDK 54 modules and MapKit still receive their app-delegate callbacks.
  func sceneDidBecomeActive(_ scene: UIScene) {
    appDelegate?.applicationDidBecomeActive(UIApplication.shared)
  }

  func sceneWillResignActive(_ scene: UIScene) {
    appDelegate?.applicationWillResignActive(UIApplication.shared)
  }

  func sceneWillEnterForeground(_ scene: UIScene) {
    appDelegate?.applicationWillEnterForeground(UIApplication.shared)
  }

  func sceneDidEnterBackground(_ scene: UIScene) {
    appDelegate?.applicationDidEnterBackground(UIApplication.shared)
  }

  func scene(_ scene: UIScene, openURLContexts contexts: Set<UIOpenURLContext>) {
    for context in contexts {
      var options: [UIApplication.OpenURLOptionsKey: Any] = [.openInPlace: context.options.openInPlace]
      options[.sourceApplication] = context.options.sourceApplication
      options[.annotation] = context.options.annotation
      _ = appDelegate?.application(UIApplication.shared, open: context.url, options: options)
    }
  }

  func scene(_ scene: UIScene, continue userActivity: NSUserActivity) {
    _ = appDelegate?.application(UIApplication.shared, continue: userActivity, restorationHandler: { _ in })
  }
}
`

module.exports = (config) => {
  config = withInfoPlist(config, (config) => {
    const existing = config.modResults.UIApplicationSceneManifest
    if (existing && existing.UISceneConfigurations?.UIWindowSceneSessionRoleApplication?.some(
      (scene) => scene.UISceneDelegateClassName !== "$(PRODUCT_MODULE_NAME).ElixirSceneDelegate",
    )) {
      throw new Error("with-ios-scene-lifecycle cannot replace an existing scene delegate")
    }
    config.modResults.UIApplicationSceneManifest = {
      UIApplicationSupportsMultipleScenes: false,
      UISceneConfigurations: {
        UIWindowSceneSessionRoleApplication: [{
          UISceneConfigurationName: "Default Configuration",
          UISceneClassName: "UIWindowScene",
          UISceneDelegateClassName: "$(PRODUCT_MODULE_NAME).ElixirSceneDelegate",
        }],
      },
    }
    return config
  })

  return withAppDelegate(config, (config) => {
    const appDelegate = config.modResults
    if (appDelegate.language !== "swift") throw new Error("with-ios-scene-lifecycle requires a Swift AppDelegate")
    if (appDelegate.contents.includes(marker)) return config
    if (!legacyStartup.test(appDelegate.contents)) {
      throw new Error("with-ios-scene-lifecycle could not find the Expo SDK 54 window startup block")
    }
    const factoryProperty = "  var reactNativeFactory: RCTReactNativeFactory?"
    if (!appDelegate.contents.includes(factoryProperty)) throw new Error("Missing React Native factory property")
    appDelegate.contents = appDelegate.contents
      .replace(factoryProperty, `${factoryProperty}\n  var sceneLaunchOptions: [UIApplication.LaunchOptionsKey: Any]?`)
      .replace(legacyStartup, `    sceneLaunchOptions = launchOptions
#if DEBUG
    // Expo SDK 54's development subscribers need a window during app launch.
    window = UIWindow(frame: .zero)
    factory.startReactNative(withModuleName: "main", in: window, launchOptions: launchOptions)
#endif`)
    appDelegate.contents += sceneDelegate
    return config
  })
}

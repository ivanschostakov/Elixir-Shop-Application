const assert = require("node:assert/strict")
const test = require("node:test")
const loadTs = require("./load-ts.cjs")

const delegate = `import Expo
import React
public class AppDelegate: ExpoAppDelegate {
  var window: UIWindow?
  var reactNativeFactory: RCTReactNativeFactory?
  func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
    bindReactNativeFactory(factory)
    yandexMapKit = YMKMapKit.sharedInstance()
#if os(iOS) || os(tvOS)
    window = UIWindow(frame: UIScreen.main.bounds)
    factory.startReactNative(
      withModuleName: "main",
      in: window,
      launchOptions: launchOptions)
#endif
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }
  public override func applicationDidBecomeActive(_ application: UIApplication) {
    super.applicationDidBecomeActive(application)
    yandexMapKit?.onStart()
  }
}
`

function setup(contents = delegate, plist = {}) {
    let appDelegate = { language: "swift", contents }
    let infoPlist = plist
    const plugin = loadTs("plugins/with-ios-scene-lifecycle.js", {
        "expo/config-plugins": {
            withInfoPlist(config, action) {
                infoPlist = action({ modResults: infoPlist }).modResults
                return config
            },
            withAppDelegate(config, action) {
                appDelegate = action({ modResults: appDelegate }).modResults
                return config
            },
        },
    })
    return { apply: () => plugin({}), contents: () => appDelegate.contents, plist: () => infoPlist }
}

test("scene migration survives prebuild and preserves the factory and MapKit callbacks", () => {
    const run = setup()
    run.apply()
    const source = run.contents()
    assert.ok(source.includes("bindReactNativeFactory(factory)"))
    assert.ok(source.includes("yandexMapKit?.onStart()"))
    assert.ok(!source.includes("UIScreen.main.bounds"))
    assert.match(source, /#if DEBUG[\s\S]*factory.startReactNative[\s\S]*#endif/)
    assert.ok(source.includes("UIWindow(windowScene: windowScene)"))
    assert.ok(source.includes("launchOptions[.url] = context.url"))
    assert.ok(source.includes("launchOptions[.remoteNotification]"))
    assert.ok(source.includes("applicationWillEnterForeground(UIApplication.shared)"))
    const manifest = run.plist().UIApplicationSceneManifest
    assert.equal(manifest.UIApplicationSupportsMultipleScenes, false)
    assert.equal(manifest.UISceneConfigurations.UIWindowSceneSessionRoleApplication[0].UISceneDelegateClassName,
        "$(PRODUCT_MODULE_NAME).ElixirSceneDelegate")
    run.apply()
    assert.equal(run.contents(), source)
})

test("scene migration refuses unknown native startup code and existing scene handlers", () => {
    assert.throws(() => setup("class CustomAppDelegate {}").apply(), /could not find/)
    assert.throws(() => setup(delegate, {
        UIApplicationSceneManifest: {
            UISceneConfigurations: { UIWindowSceneSessionRoleApplication: [{ UISceneDelegateClassName: "ExistingScene" }] },
        },
    }).apply(), /cannot replace/)
})

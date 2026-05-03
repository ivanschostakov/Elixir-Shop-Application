export type IosAppVersionPolicy = {
    minimumBuild: number
    latestBuild: number
    minimumJsBundleVersion: number
    latestJsBundleVersion: number
    storeUrl: string
}

export type AndroidAppVersionPolicy = {
    minimumVersionCode: number
    latestVersionCode: number
    minimumJsBundleVersion: number
    latestJsBundleVersion: number
    storeUrl: string
}

export type AppVersionPolicy = {
    ios: IosAppVersionPolicy
    android: AndroidAppVersionPolicy
}

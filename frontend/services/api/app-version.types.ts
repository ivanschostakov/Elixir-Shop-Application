export type IosAppVersionPolicy = {
    minimumBuild: number
    latestBuild: number
    storeUrl: string
}

export type AndroidAppVersionPolicy = {
    minimumVersionCode: number
    latestVersionCode: number
    storeUrl: string
}

export type AppVersionPolicy = {
    ios: IosAppVersionPolicy
    android: AndroidAppVersionPolicy
}

# Elixir Peptide App

This project uses Expo, React Native, Expo Router, and TypeScript.

The current setup is intentionally small:

- one root layout in `app/_layout.tsx`
- one home screen in `app/index.tsx`
- shared code that can target web and iOS from the same codebase

## Start the project

```bash
npm install
npm run ios
# or
npm run android

npm run start
```

`npm run start` now launches Metro for an Expo development build instead of Expo Go. Build the native client once with `npm run ios` or `npm run android`, then keep using `npm run start` while you work.

Useful commands:

```bash
npm run start
npm run android
npm run web
npm run ios
npm run prebuild:clean
npm run lint
```

If you add a library with native code or change app config, run `npm run prebuild:clean` and rebuild the dev client so the native projects stay in sync.

## iOS device builds with Xcode 27

Xcode 27 replaces Simulator with Device Hub. The Expo SDK 54 CLI still checks for
Simulator before listing devices, even when building for a physical iPhone. Our
`postinstall` script patches the CLI's app discovery, simulator opening, and window
focus to support Device Hub while preserving support for older Xcode versions.

For an existing dependency installation, apply the patch once, then retry the build:

```bash
node scripts/patch-expo-device-hub.cjs
npx expo run:ios --device --configuration Release
```

Run these commands from `frontend`. No additional clean prebuild is needed for this
CLI fix. If `xcode-select -p` already points to the intended Xcode, switching it again
will not fix the missing Simulator app error.

## Store Builds

Android testing build:

```bash
eas build --platform android --profile testing
```

iOS TestFlight build:

```bash
eas build --platform ios --profile testflight
```

iOS TestFlight submit:

```bash
eas submit --platform ios --profile testflight
```

## Why this structure

The default Expo tutorial screens were removed so the app starts from a cleaner base. This makes it
easier to learn React Native step by step without carrying demo code you do not plan to ship.

## Suggested roadmap

1. Build the first real screen flow for web and iOS.
2. Extract shared UI pieces only when they repeat.
3. Add backend or API integration after the first screens are clear.
4. Add Android once the product direction is validated.

# Elixir Peptide Mobile Application

Customer application for the [Elixir commerce platform](../README.md), built with Expo, React Native, Expo Router, and TypeScript. The Android application is available on [Google Play](https://play.google.com/store/apps/details?id=com.elixirpeptide.elixirpeptide).

The application includes product browsing, search, favorites, basket and checkout, delivery and payment screens, customer profiles, and AI chat. API access and available features depend on backend configuration and the signed-in account.

## Source Map

- `app/`: Expo Router screens and layouts, including guest and authenticated routes.
- `components/`: reusable interface components.
- `hooks/`: application state and feature-specific behavior.
- `tests/`: JavaScript regression checks.
- `scripts/`: Expo CLI wrapper and native map compatibility patches.

## Local Development

Use Node.js 20 through 24, as specified in `package.json`.

```bash
npm ci
cp .env.example .env.local
```

Configure the API connection in `.env.local` for the backend you are authorized to use. Native builds require the corresponding Android or iOS development tools.

Build and start a native development client:

```bash
npm run android
# Or, on macOS with the iOS toolchain:
npm run ios
```

For subsequent sessions:

```bash
npm run start
```

The start command targets an Expo development client. The native map and integrity integrations require a native build. The install hook applies versioned map compatibility patches, so keep the patch files under `scripts/`.

Web development is also available:

```bash
npm run web
```

Web support does not imply that every native integration behaves identically in a browser.

## Checks

```bash
npm run lint
npm run typecheck
npm run test:regressions
```

For a web production export:

```bash
npm run web:export
```

## Native Configuration and Store Builds

After changing native dependencies or app configuration, review and commit any intended native configuration changes before running `npm run prebuild:clean`. That command regenerates native projects and should not be treated as a routine cleanup command.

Build profiles are defined in `eas.json`. With the appropriate Expo account and signing access:

```bash
eas build --platform android --profile testing
eas build --platform ios --profile testflight
```

Use the [repository documentation](../README.md) for backend and administration setup. Store publishing requires the existing release process and signing credentials.

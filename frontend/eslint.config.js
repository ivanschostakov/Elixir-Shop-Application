// https://docs.expo.dev/guides/using-eslint/
const { defineConfig } = require('eslint/config');
const expoConfig = require('eslint-config-expo/flat');

module.exports = defineConfig([
  {
    ignores: ['**/.expo/**', '**/dist/**'],
  },
  expoConfig,
  {
    settings: {
      'import/resolver': {
        node: {
          extensions: ['.js', '.jsx', '.ts', '.tsx', '.d.ts', '.native.ts', '.native.tsx', '.web.ts', '.web.tsx'],
        },
      },
    },
  },
]);

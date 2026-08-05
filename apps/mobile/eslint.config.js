// https://docs.expo.dev/guides/using-eslint/
const { defineConfig } = require('eslint/config');
const path = require('node:path');
const expoConfig = require("eslint-config-expo/flat");

module.exports = defineConfig([
  expoConfig,
  {
    settings: {
      'import/resolver': {
        node: {
          paths: [
            path.resolve(__dirname, 'node_modules'),
            path.resolve(__dirname, '../../node_modules'),
          ],
        },
      },
    },
  },
  {
    ignores: ["dist/*"],
  }
]);

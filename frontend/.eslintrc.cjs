module.exports = {
  root: true,
  env: { browser: true, es2021: true, node: true },
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
  ],
  parser: "@typescript-eslint/parser",
  parserOptions: { ecmaVersion: "latest", sourceType: "module" },
  plugins: ["react-hooks", "react-refresh"],
  settings: { react: { version: "18" } },
  rules: {
    "react-hooks/rules-of-hooks": "error",
    "react-hooks/exhaustive-deps": "warn",
    "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
  },
  ignorePatterns: [
    "dist",
    ".eslintrc.cjs",
    "vite.config.ts",
    "tailwind.config.js",
    "postcss.config.js",
  ],
};

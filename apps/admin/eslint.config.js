import tseslint from '@typescript-eslint/eslint-plugin';
import tsParser from '@typescript-eslint/parser';

export default [
  { ignores: ['dist/**', 'node_modules/**'] },
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: {
      parser: tsParser,
      parserOptions: { ecmaVersion: 'latest', sourceType: 'module', ecmaFeatures: { jsx: true } },
      globals: {
        window: 'readonly', document: 'readonly', localStorage: 'readonly', sessionStorage: 'readonly', crypto: 'readonly',
        fetch: 'readonly', FormData: 'readonly', URLSearchParams: 'readonly', console: 'readonly',
        HTMLVideoElement: 'readonly', HTMLCanvasElement: 'readonly', CanvasRenderingContext2D: 'readonly',
        requestAnimationFrame: 'readonly', cancelAnimationFrame: 'readonly', PromiseRejectionEvent: 'readonly',
      },
    },
    plugins: { '@typescript-eslint': tseslint },
    rules: {
      ...tseslint.configs.recommended.rules,
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    },
  },
];

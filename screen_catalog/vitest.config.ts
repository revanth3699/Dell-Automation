// Unit tests for the catalog (src/__tests__). Same aliases as vite.config.ts so the tests read the app's real
// contract types, i18n text and resx-generated strings from the Rebit repo.
import path from 'node:path'
import { defineConfig } from 'vitest/config'
import { resolveWebSrc } from './scripts/webSrc.mjs'

const web = resolveWebSrc()

export default defineConfig({
  resolve: {
    alias: {
      '@app': path.join(web, 'src'),
      '@dds/react': path.join(web, 'node_modules/@dds/react'),
    },
    dedupe: ['react', 'react-dom', 'i18next', 'react-i18next'],
  },
  test: {
    environment: 'node',
    globals: true,
    include: ['src/__tests__/**/*.test.ts'],
    server: { fs: { allow: [web] } },
  },
})

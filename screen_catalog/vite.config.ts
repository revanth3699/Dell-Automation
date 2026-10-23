import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolveWebSrc } from './scripts/webSrc.mjs'

// The catalog lives in THIS repo; the app's real React code lives in the Rebit repo and is read from there
// (REBIT_WEB_SRC, see scripts/webSrc.mjs). Nothing in Rebit is copied or modified. `npm run dev` serves
// /catalog.html; `npm run build:catalog` writes dist-catalog/ for the audit and for automation.
const web = resolveWebSrc()
const here = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  base: './',
  // The app's static files — fonts, Dell logo, backgrounds — come from the app's own public folder.
  publicDir: path.join(web, 'public'),
  resolve: {
    alias: {
      '@app': path.join(web, 'src'),
      // The vendored design system is installed in the app's node_modules, not here.
      '@dds/react': path.join(web, 'node_modules/@dds/react'),
    },
    // One copy of React and friends (this folder's), even for the app's own files and the packages they pull in —
    // two copies break hooks.
    dedupe: ['react', 'react-dom', 'i18next', 'react-i18next'],
  },
  // Vite only serves files under its own root by default; the app's sources are outside it.
  server: { fs: { allow: [web, here] } },
  build: {
    outDir: 'dist-catalog',
    emptyOutDir: true,
    target: 'chrome110',
    sourcemap: true,
    rollupOptions: { input: 'catalog.html' },
  },
})

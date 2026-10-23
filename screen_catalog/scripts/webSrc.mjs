// Where is the Rebit app's React code? Every tool in this folder (vite.config.ts, the audit, the typecheck) asks here.
//
// The path comes from REBIT_WEB_SRC — the real environment variable, or a line in screen_catalog/.env (git-ignored;
// copy .env.example). It points at Rebit's  Cdm/Cdm/TargetPc.UI/web  folder, the one that contains src/App.tsx. A
// relative value is resolved against this folder.
//
// Nothing in the Rebit repo is changed or written to by anything here: the catalog only reads its files.
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

/** The screen_catalog folder. */
export const catalogRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

function fromDotEnv() {
  const file = path.join(catalogRoot, '.env')
  if (!fs.existsSync(file)) {
    return undefined
  }
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const match = /^\s*REBIT_WEB_SRC\s*=\s*(.*?)\s*$/.exec(line)
    if (match) {
      return match[1].replace(/^(['"])(.*)\1$/, '$2')
    }
  }
  return undefined
}

/**
 * Absolute path of Rebit's TargetPc.UI/web folder. Throws, with what to do about it, if it is not set or does not look
 * like that folder; warns (does not throw) if the generated text file is older than the resx it comes from.
 */
export function resolveWebSrc() {
  const value = process.env.REBIT_WEB_SRC || fromDotEnv()
  if (!value) {
    throw new Error(
      'REBIT_WEB_SRC is not set. Point it at Rebit\'s Cdm/Cdm/TargetPc.UI/web folder — either as an environment ' +
      'variable or in screen_catalog/.env (see .env.example).',
    )
  }
  const web = path.resolve(catalogRoot, value)

  const needed = [
    ['src/App.tsx', 'is this Rebit\'s TargetPc.UI/web folder?'],
    ['node_modules/@dds/react', 'run "npm install" in that folder first (the design system is installed there)'],
    ['src/i18n/locales/en/screens.json', 'run "npm run generate:i18n" in that folder first (it is generated from Resources.resx)'],
  ]
  const missing = needed.filter(([rel]) => !fs.existsSync(path.join(web, rel)))
  if (missing.length > 0) {
    throw new Error(
      `REBIT_WEB_SRC=${web} is not ready:\n` + missing.map(([rel, hint]) => `  - ${rel} not found — ${hint}`).join('\n'),
    )
  }

  const resx = path.join(web, '..', 'Resources', 'Resources.resx')
  const generated = path.join(web, 'src/i18n/locales/en/screens.json')
  if (fs.existsSync(resx) && fs.statSync(resx).mtimeMs > fs.statSync(generated).mtimeMs) {
    console.warn(
      'WARNING: Resources.resx is newer than the generated screens.json, so the catalog may show stale text. ' +
      'Run "npm run generate:i18n" in the Rebit web folder.',
    )
  }
  return web
}

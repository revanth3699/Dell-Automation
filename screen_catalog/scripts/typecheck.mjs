// Type-checks the catalog against the app's real types. This is what notices that the app's contract changed (a new
// ScreenId / OverlayId, a renamed state field): scenarios.ts and the tests are typed against bridge/contract.ts, so a
// change there that the catalog has not caught up with fails here instead of silently showing a wrong screen.
//
// tsconfig "paths" cannot read an environment variable, so the alias to the app is written into a generated,
// git-ignored tsconfig.generated.json first.
import fs from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { catalogRoot, resolveWebSrc } from './webSrc.mjs'

const web = resolveWebSrc().replace(/\\/g, '/')
const generated = path.join(catalogRoot, 'tsconfig.generated.json')
fs.writeFileSync(generated, JSON.stringify({
  extends: './tsconfig.json',
  compilerOptions: {
    paths: {
      '@app/*': [`${web}/src/*`],
      // The app's files must see THIS folder's React types, not their own copy (two copies of @types/react clash).
      react: ['./node_modules/@types/react'],
      'react/*': ['./node_modules/@types/react/*'],
      'react-dom': ['./node_modules/@types/react-dom'],
      'react-dom/*': ['./node_modules/@types/react-dom/*'],
    },
  },
  include: ['src', `${web}/src/vite-env.d.ts`],
}, null, 2))

const tsc = path.join(catalogRoot, 'node_modules', 'typescript', 'bin', 'tsc')
const result = spawnSync(process.execPath, [tsc, '-p', generated], { stdio: 'inherit', cwd: catalogRoot })
process.exit(result.status ?? 1)

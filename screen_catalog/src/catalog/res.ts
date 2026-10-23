// Resolves copy from Resources.resx (via the generated screens.json the app's own i18n loads) so catalog
// scenarios carry the SAME strings the native view models push — the native side reads
// Resources.Resources.<Key> from that resx, and this reads the identical key. That keeps text validation
// honest: a copy change in the resx shows up in the catalog with no scenario edit, instead of the catalog
// holding a second, drifting copy of the wording.
//
// {0}-style placeholders are String.Format arguments on the C# side; they are substituted here the same way.
// A key missing from the resx renders as a visible ⟦missing:Key⟧ marker so a typo fails loudly in a
// screenshot/text dump rather than silently showing nothing.
//
// Uses the global i18next instance directly: the app's i18n/index.ts (catalog main.tsx imports it) and the
// test bootstrap (i18nForTests.ts) both initialise that same singleton, so this works in either.
import i18n from 'i18next'

export function res(key: string, ...args: Array<string | number>): string {
  const raw = i18n.t(key, { ns: 'screens', defaultValue: `⟦missing:${key}⟧` }) as string
  return raw.replace(/\{(\d+)\}/g, (placeholder, index: string) => {
    const value = args[Number(index)]
    return value === undefined ? placeholder : String(value)
  })
}

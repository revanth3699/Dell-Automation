// Lightweight i18n bootstrap for jsdom tests. Avoids import.meta.glob (Vite-only)
// and the bridge.on() call in the production i18n/index.ts.
// Import this file once at the top of any test that renders a translated component.
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import screens from '@app/i18n/locales/en/screens.json'

if (!i18n.isInitialized) {
  i18n.use(initReactI18next).init({
    resources: { en: { screens } },
    lng: 'en',
    fallbackLng: 'en',
    ns: ['screens'],
    defaultNS: 'screens',
    interpolation: { escapeValue: false },
  })
}

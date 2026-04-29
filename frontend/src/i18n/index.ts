import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import he from './locales/he.json'

function applyDirection(lang: string) {
  document.documentElement.dir = lang === 'he' ? 'rtl' : 'ltr'
  document.documentElement.lang = lang
}

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      he: { translation: he },
    },
    lng: localStorage.getItem('lng') ?? 'en',
    fallbackLng: 'en',
    interpolation: { escapeValue: false },
  })

i18n.on('languageChanged', (lang) => {
  localStorage.setItem('lng', lang)
  applyDirection(lang)
})

applyDirection(i18n.language)

export default i18n

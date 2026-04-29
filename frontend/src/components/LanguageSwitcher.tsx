import { useTranslation } from 'react-i18next'

export default function LanguageSwitcher() {
  const { i18n } = useTranslation()
  const isHe = i18n.language === 'he'

  return (
    <button
      onClick={() => i18n.changeLanguage(isHe ? 'en' : 'he')}
      className="text-xs font-medium text-gray-400 hover:text-gray-700 transition-colors
                 px-2 py-1 rounded border border-gray-200 hover:border-gray-300"
      title={isHe ? 'Switch to English' : 'עבור לעברית'}
    >
      {isHe ? 'EN' : 'עב'}
    </button>
  )
}

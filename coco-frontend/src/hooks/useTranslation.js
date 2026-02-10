import { useState, useCallback } from 'react';

// A simple dictionary for demonstration purposes. 
// In a real app, this might be fetched from an API or loaded from JSON files.
const translations = {
  en: {
    "welcome": "Welcome",
    "dashboard": "Dashboard",
    "settings": "Settings",
    "profile": "Profile"
  },
  zh: {
    "welcome": "欢迎",
    "dashboard": "仪表盘",
    "settings": "设置",
    "profile": "个人资料"
  }
};

/**
 * Custom hook for handling translations within the application.
 * Allows switching languages and retrieving translated strings.
 */
export function useTranslation(initialLang = 'zh') {
  const [currentLang, setCurrentLang] = useState(initialLang);

  const t = useCallback((key) => {
    return translations[currentLang]?.[key] || key;
  }, [currentLang]);

  const changeLanguage = useCallback((lang) => {
    if (translations[lang]) {
      setCurrentLang(lang);
    } else {
      console.warn(`Language ${lang} not supported.`);
    }
  }, []);

  return { t, currentLang, changeLanguage };
}

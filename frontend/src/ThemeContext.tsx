import React, { createContext, useContext, useState, useEffect } from 'react'
import { lightTheme, darkTheme, Theme } from './theme'

interface ThemeContextType {
  isDark: boolean
  setIsDark: (dark: boolean) => void
  toggleDark: () => void
  theme: Theme
}

const ThemeContext = createContext<ThemeContextType>({
  isDark: false,
  setIsDark: () => {},
  toggleDark: () => {},
  theme: lightTheme,
})

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isDark, setIsDarkState] = useState<boolean>(() => {
    return localStorage.getItem('darkMode') === 'true'
  })

  useEffect(() => {
    localStorage.setItem('darkMode', String(isDark))
    if (isDark) {
      document.documentElement.classList.add('dark-mode')
      document.body.style.backgroundColor = darkTheme.color.bg
      document.body.style.color = darkTheme.color.textPrimary
    } else {
      document.documentElement.classList.remove('dark-mode')
      document.body.style.backgroundColor = lightTheme.color.bg
      document.body.style.color = lightTheme.color.textPrimary
    }
  }, [isDark])

  const setIsDark = (dark: boolean) => {
    setIsDarkState(dark)
  }

  const toggleDark = () => {
    setIsDarkState((prev) => !prev)
  }

  const currentTheme = isDark ? darkTheme : lightTheme

  return (
    <ThemeContext.Provider value={{ isDark, setIsDark, toggleDark, theme: currentTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export const useTheme = () => useContext(ThemeContext)

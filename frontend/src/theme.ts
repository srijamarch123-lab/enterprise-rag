export interface Theme {
  color: {
    bg: string
    surface: string
    surfaceMuted: string
    border: string
    borderStrong: string
    textPrimary: string
    textSecondary: string
    textTertiary: string
    adminAccent: string
    adminAccentHover: string
    adminAccentSoft: string
    chatAccent: string
    chatAccentHover: string
    chatAccentSoft: string
    success: string
    successSoft: string
    warning: string
    warningSoft: string
    danger: string
    dangerSoft: string
  }
  font: string
  radius: { sm: string; md: string; lg: string }
}

export const lightTheme: Theme = {
  color: {
    bg: '#F7F5F1',
    surface: '#FFFFFF',
    surfaceMuted: '#EDEAE1',
    border: '#DAD4C6',
    borderStrong: '#C7C0AE',
    textPrimary: '#2B2A27',
    textSecondary: '#63604F',
    textTertiary: '#8B8574',
    adminAccent: '#4E6E88',
    adminAccentHover: '#405C74',
    adminAccentSoft: '#D9E3EA',
    chatAccent: '#6E9163',
    chatAccentHover: '#5C7C52',
    chatAccentSoft: '#DCEAD5',
    success: '#5C9576',
    successSoft: '#DFEEE5',
    warning: '#C99149',
    warningSoft: '#F5E7D0',
    danger: '#BC6459',
    dangerSoft: '#F3DEDB',
  },
  font: "'Inter', system-ui, -apple-system, sans-serif",
  radius: { sm: '6px', md: '10px', lg: '14px' },
}

export const darkTheme: Theme = {
  color: {
    bg: '#0f0f0f',
    surface: '#1a1a1a',
    surfaceMuted: '#242424',
    border: '#2e2e2e',
    borderStrong: '#3a3a3a',
    textPrimary: '#f0f0f0',
    textSecondary: '#a0a0a0',
    textTertiary: '#666666',
    adminAccent: '#6E9163',
    adminAccentHover: '#5C7C52',
    adminAccentSoft: '#1e2e1c',
    chatAccent: '#6E9163',
    chatAccentHover: '#5C7C52',
    chatAccentSoft: '#1e2e1c',
    success: '#5C9576',
    successSoft: '#1a2e22',
    warning: '#C99149',
    warningSoft: '#2e2010',
    danger: '#BC6459',
    dangerSoft: '#2e1510',
  },
  font: "'Inter', system-ui, -apple-system, sans-serif",
  radius: { sm: '6px', md: '10px', lg: '14px' },
}

export const theme = lightTheme

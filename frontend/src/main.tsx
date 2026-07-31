if (import.meta.env.DEV) {
  import("react-grab");
}

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './i18n'
import App from './App.tsx'
import { AuthProvider } from './contexts/AuthContext'
import { initTheme } from './utils/theme'

declare global {
  interface Window {
    __INK_FRONTEND_VERSION__?: string
  }
}

const frontendVersion = import.meta.env.VITE_FRONTEND_VERSION ?? 'unknown'
window.__INK_FRONTEND_VERSION__ = frontendVersion
console.log(`🧾 Ink & Memory frontend version: ${frontendVersion}`)

initTheme()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </StrictMode>,
)

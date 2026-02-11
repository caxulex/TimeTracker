import React from 'react'
import ReactDOM from 'react-dom/client'

// Phase 3: Initialize Sentry BEFORE React renders
import { initSentry } from './lib/sentry'
initSentry()

import App from './App.tsx'
import './index.css'
import { applyBrandingStyles, setDocumentTitle } from './config/branding'

// Initialize branding on app start
applyBrandingStyles()
setDocumentTitle()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
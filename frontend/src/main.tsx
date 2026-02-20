import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './mobile.css'
import App from './App.tsx'
import { registerServiceWorker } from './lib/pwa'

registerServiceWorker()

const rootEl = document.getElementById('root')!
const root = createRoot(rootEl)
root.render(
  <StrictMode>
    <App />
  </StrictMode>
)

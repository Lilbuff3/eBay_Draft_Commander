import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import './mobile.css'
import App from './App.tsx'
// import { registerServiceWorker } from './lib/pwa'

// registerServiceWorker() // Disabled for mobile troubleshooting over HTTP

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: true,
      staleTime: 1000,
    },
  },
})

const rootEl = document.getElementById('root')!
const root = createRoot(rootEl)
root.render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>
)

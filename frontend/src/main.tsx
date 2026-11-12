import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { ApiError } from './api/client'
import App from './App'
import './index.css'
import { applyTheme, readTheme } from './lib/theme'

applyTheme(readTheme())

const queryClient: QueryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2 },
  },
  queryCache: new QueryCache({
    // A 401 anywhere means the session expired: re-check auth to show the login screen.
    onError: (err) => {
      if (err instanceof ApiError && err.status === 401) queryClient.invalidateQueries({ queryKey: ['me'] })
    },
  }),
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)

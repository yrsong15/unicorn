import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { useMe } from './api/hooks'
import Layout from './components/Layout'
import { Button, ErrorNote, Loading } from './components/ui'
import Dashboard from './pages/Dashboard'
import Fitness from './pages/Fitness'
import Login from './pages/Login'
import Records from './pages/Records'
import RunDetail from './pages/RunDetail'
import Runs from './pages/Runs'
import Settings from './pages/Settings'
import Shoes from './pages/Shoes'
import Training from './pages/Training'

/** Shown when the server can't be reached, instead of a login form that wouldn't work either. */
function Unreachable({ error, retrying, onRetry }: { error: unknown; retrying: boolean; onRetry: () => void }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-nav px-4">
      <div className="w-full max-w-sm rounded-2xl bg-surface p-6 shadow-xl">
        <h1 className="mb-3 text-xl font-semibold text-ink">Can't reach Unicorn</h1>
        <ErrorNote error={error} />
        <Button variant="primary" className="mt-4 w-full py-2" disabled={retrying} onClick={onRetry}>
          {retrying ? 'Trying again…' : 'Try again'}
        </Button>
      </div>
    </div>
  )
}

export default function App() {
  const me = useMe()
  if (me.isLoading) return <Loading />
  // A failed check means the server is down or unreachable, not that you're signed out.
  if (me.error && !me.data) return <Unreachable error={me.error} retrying={me.isFetching} onRetry={() => me.refetch()} />
  if (!me.data?.logged_in) return <Login />
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="runs" element={<Runs />} />
          <Route path="runs/:id" element={<RunDetail />} />
          <Route path="shoes" element={<Shoes />} />
          <Route path="fitness" element={<Fitness />} />
          <Route path="training" element={<Training />} />
          <Route path="records" element={<Records />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<Dashboard />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

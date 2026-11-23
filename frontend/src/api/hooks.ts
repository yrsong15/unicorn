import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, patch, post, put } from './client'
import type {
  Dashboard, FitnessKey, MetricsResponse, RangeKey, Records, RunDetail, RunSummary, Shoe, Sport, SyncStatus,
  TrainingResponse, Week,
} from './types'

export const useMe = () => useQuery({ queryKey: ['me'], queryFn: () => api<{ logged_in: boolean }>('/auth/me') })

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (password: string) => post('/auth/login', { password }),
    onSuccess: () => qc.invalidateQueries(),
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: () => post('/auth/logout'), onSuccess: () => qc.invalidateQueries() })
}

export const useWeekly = (range: RangeKey) =>
  useQuery({
    queryKey: ['weekly', range],
    queryFn: () => api<{ weeks: Week[]; load_per_run_mile: number | null }>(`/summary/weekly?range=${range}`),
    placeholderData: (prev) => prev,
  })

export const useDashboard = () => useQuery({ queryKey: ['dashboard'], queryFn: () => api<Dashboard>('/summary/dashboard') })

export interface RunFilters {
  start?: string
  end?: string
  shoe_id?: number
  ids?: number[]
  sport?: Sport | 'all'
  limit?: number
  offset?: number
}

export function useRuns(filters: RunFilters, enabled = true) {
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(filters)) {
    if (v === undefined || (Array.isArray(v) && v.length === 0)) continue
    params.set(k, Array.isArray(v) ? v.join(',') : String(v))
  }
  return useQuery({
    queryKey: ['runs', params.toString()],
    queryFn: () => api<{ items: RunSummary[]; total: number }>(`/runs?${params}`),
    enabled,
    placeholderData: (prev) => prev,
  })
}

export const useRun = (id: number) => useQuery({ queryKey: ['run', id], queryFn: () => api<RunDetail>(`/runs/${id}`) })

export interface SegmentInput { shoe_id: number; miles?: number | null; lap_from?: number | null; lap_to?: number | null }

function useInvalidateShoeData() {
  const qc = useQueryClient()
  return () => Promise.all(['runs', 'run', 'shoes', 'dashboard'].map((k) => qc.invalidateQueries({ queryKey: [k] })))
}

export function useSetRunShoes(runId: number) {
  const invalidate = useInvalidateShoeData()
  return useMutation({
    mutationFn: (segments: SegmentInput[]) => put<RunDetail>(`/runs/${runId}/shoes`, { segments }),
    onSuccess: invalidate,
  })
}

export const useShoes = () => useQuery({ queryKey: ['shoes'], queryFn: () => api<Shoe[]>('/shoes') })

export type ShoeInput = Partial<Omit<Shoe, 'id' | 'miles' | 'wear' | 'run_count'>>

export function useSaveShoe() {
  const invalidate = useInvalidateShoeData()
  return useMutation({
    mutationFn: ({ id, ...body }: ShoeInput & { id?: number }) =>
      id ? patch<Shoe>(`/shoes/${id}`, body) : post<Shoe>('/shoes', body),
    onSuccess: invalidate,
  })
}

export function useRetireShoe() {
  const invalidate = useInvalidateShoeData()
  return useMutation({
    mutationFn: ({ id, retire }: { id: number; retire: boolean }) =>
      post<Shoe>(`/shoes/${id}/${retire ? 'retire' : 'unretire'}`),
    onSuccess: invalidate,
  })
}

export const useFitness = (range: RangeKey) =>
  useQuery({
    queryKey: ['fitness', range],
    queryFn: () => api<MetricsResponse<FitnessKey>>(`/metrics/fitness?range=${range}`),
    placeholderData: (prev) => prev,
  })

export const useTraining = (range: RangeKey) =>
  useQuery({
    queryKey: ['training', range],
    queryFn: () => api<TrainingResponse>(`/metrics/training?range=${range}`),
    placeholderData: (prev) => prev,
  })

export const useRecords = () => useQuery({ queryKey: ['records'], queryFn: () => api<Records>('/records') })

export const useSyncStatus = () =>
  useQuery({ queryKey: ['sync-status'], queryFn: () => api<SyncStatus>('/sync/status'), refetchInterval: 60_000 })

export function useSync() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (ifStale: boolean) => post<SyncStatus>(`/sync${ifStale ? '?if_stale=true' : ''}`),
    onSettled: (data) => {
      qc.invalidateQueries({ queryKey: ['sync-status'] })
      if (data && !data.skipped) qc.invalidateQueries()
    },
  })
}

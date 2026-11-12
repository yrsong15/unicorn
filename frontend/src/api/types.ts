export type Category = 'road' | 'treadmill' | 'track' | 'trail'
export type RideCategory = 'road' | 'indoor' | 'mountain' | 'gravel'
export type Sport = 'run' | 'ride'
export type RangeKey = '3m' | '6m' | '1y' | 'ytd' | 'all'

export interface ShoeSegment {
  shoe_id: number
  shoe_name: string
  miles: number
  lap_from: number | null
  lap_to: number | null
}

export interface RunSummary {
  id: number
  garmin_activity_id: number
  name: string
  start_local: string
  local_date: string
  sport: Sport
  category: Category | RideCategory
  miles: number
  duration_s: number
  pace_s_per_mile: number | null
  speed_mph: number | null
  avg_hr: number | null
  training_load: number | null
  shoes: ShoeSegment[]
  unassigned_miles: number
}

export interface Lap {
  idx: number
  miles: number
  duration_s: number
  pace_s_per_mile: number | null
  speed_mph: number | null
  avg_hr: number | null
  avg_cadence: number | null
  elev_gain_ft: number | null
}

export interface RunDetail extends RunSummary {
  moving_s: number | null
  max_hr: number | null
  avg_cadence: number | null
  elev_gain_ft: number | null
  aerobic_te: number | null
  anaerobic_te: number | null
  vo2max: number | null
  hr_zones_s: number[] | null
  laps: Lap[]
}

export interface Shoe {
  id: number
  name: string
  brand: string | null
  model: string | null
  color: string | null
  start_miles: number
  retire_at_miles: number
  is_default: boolean
  default_for_category: Category | null
  retired_at: string | null
  notes: string | null
  miles: number
  wear: 'ok' | 'warn' | 'over'
  run_count: number
}

export interface Week {
  week_start: string
  week_end: string
  run_miles: number
  /** Ride training load converted at the trailing-year load per run mile. */
  ride_equiv_miles: number
  total_miles: number
  runs: number
  rides: number
  longest_miles: number
  rolling_avg: number
  rolling_avg_total: number
  run_ids: number[]
  ride_ids: number[]
}

export interface DailyMetrics {
  day: string
  vo2max: number | null
  resting_hr: number | null
  hrv_last_night: number | null
  hrv_weekly_avg: number | null
  hrv_status: string | null
  readiness_score: number | null
  readiness_level: string | null
  training_status: string | null
  acute_load: number | null
  chronic_load: number | null
  acwr: number | null
  race_5k_s: number | null
  race_10k_s: number | null
  race_half_s: number | null
  race_full_s: number | null
  lt_hr: number | null
  lt_pace_s_per_mile: number | null
}

export interface Dashboard {
  this_week: Week
  last_week: Week
  shoe_alerts: Shoe[]
  today: DailyMetrics | null
  load_per_run_mile: number | null
}

export interface SyncStatus {
  garmin: { status: 'disconnected' | 'ok' | 'needs_reconnect'; last_error: string | null; updated_at: string }
  last_sync_at: string | null
  status: 'idle' | 'running' | 'ok' | 'partial' | 'error'
  message: string | null
  last_activity_start: string | null
  stale: boolean
  skipped?: boolean
  reason?: string
}

export interface MetricsResponse<K extends keyof DailyMetrics> {
  range: RangeKey
  series: (Pick<DailyMetrics, K> & { day: string })[]
  latest: Pick<DailyMetrics, K>
}

export type FitnessKey =
  | 'vo2max' | 'resting_hr' | 'race_5k_s' | 'race_10k_s' | 'race_half_s' | 'race_full_s' | 'lt_hr' | 'lt_pace_s_per_mile'
export type TrainingKey =
  | 'acute_load' | 'chronic_load' | 'acwr' | 'readiness_score' | 'readiness_level'
  | 'hrv_last_night' | 'hrv_weekly_avg' | 'hrv_status' | 'training_status'

export interface TrainingResponse extends MetricsResponse<TrainingKey> {
  daily_load: { day: string; run: number; ride: number; total: number }[]
}

export interface Records {
  garmin_prs: { type_id: number; label: string; value: number; activity_id: number | null; date: string | null }[]
  longest_run: { run_id: number; miles: number; date: string; name: string } | null
  biggest_week: { week_start: string; miles: number; runs: number } | null
  current_streak_weeks: number
  longest_streak_weeks: number
  ytd: {
    this_year: number
    last_year_to_date: number
    last_year_total: number
    cumulative: { year: number; day_of_year: number; date: string; miles: number }[]
  } | null
  totals: { runs: number; miles: number; since: string } | null
}

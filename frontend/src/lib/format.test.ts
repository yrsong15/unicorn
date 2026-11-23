import { describe, expect, it } from 'vitest'

import { activityLabel, duration, mi, minutes, pace, paceOrSpeed, plural, titleCase } from './format'

describe('duration', () => {
  it('formats minutes and hours', () => {
    expect(duration(65)).toBe('1:05')
    expect(duration(3725)).toBe('1:02:05')
    expect(duration(59.6)).toBe('1:00')
  })

  it('shows a dash for missing values', () => {
    expect(duration(null)).toBe('–')
    expect(duration(undefined)).toBe('–')
  })
})

describe('pace and distance', () => {
  it('formats pace per mile', () => {
    expect(pace(450)).toBe('7:30/mi')
    expect(pace(null)).toBe('–')
  })

  it('formats miles, including zero', () => {
    expect(mi(3.14159)).toBe('3.1')
    expect(mi(0)).toBe('0.0')
    expect(mi(null)).toBe('–')
  })

  it('shows speed for rides and pace for runs', () => {
    expect(paceOrSpeed({ sport: 'ride', pace_s_per_mile: null, speed_mph: 15.25 })).toBe('15.3 mph')
    expect(paceOrSpeed({ sport: 'run', pace_s_per_mile: 480, speed_mph: null })).toBe('8:00/mi')
  })
})

describe('labels', () => {
  it('title-cases Garmin keys and drops numeric suffixes', () => {
    expect(titleCase('HIGH_AEROBIC_2')).toBe('High Aerobic')
    expect(titleCase(null)).toBe('–')
  })

  it('labels known categories and falls back for unknown ones', () => {
    expect(activityLabel({ sport: 'run', category: 'track' })).toBe('Track')
    expect(activityLabel({ sport: 'ride', category: 'gravel' })).toBe('Gravel ride')
    expect(activityLabel({ sport: 'run', category: 'ultra_trail' })).toBe('Ultra Trail')
    expect(activityLabel({ sport: 'sauna', category: 'sauna' })).toBe('Sauna')
  })
})

describe('sauna formatting', () => {
  it('formats minutes, with hours past 60', () => {
    expect(minutes(18.4)).toBe('18 min')
    expect(minutes(0)).toBe('0 min')
    expect(minutes(65)).toBe('1 h 05 min')
    expect(minutes(null)).toBe('–')
  })

  it('shows no pace for a sauna session', () => {
    expect(paceOrSpeed({ sport: 'sauna', pace_s_per_mile: null, speed_mph: null })).toBe('–')
  })

  it('pluralizes counts', () => {
    expect(plural(1, 'session')).toBe('1 session')
    expect(plural(3, 'session')).toBe('3 sessions')
  })
})

# TODO

## Sauna sessions from Garmin

Pull sauna activities from Garmin Connect and show them on the Dashboard.

- **Research first:** search the web for what's known about sauna and running training, e.g. heat acclimation, plasma volume, recovery, effects on HRV and resting HR, and timing relative to hard sessions. Prefer studies and reputable coaching sources over anecdotes. Use what you find to decide what's worth showing (for example, sauna sessions next to HRV or readiness trends) and whether sauna should count toward training load.

- **Import:** Garmin has no sauna activity type. Real logged sessions come back with `activityType.typeKey` = `other` and `activityName` = `Sauna` (seen in the Personal API's activity list on 2026-11-09; confirm `python-garminconnect` returns the same). Match on type `other` plus the name, then import those activities in `backend/app/garmin/parse.py` the same way rides are, e.g. `sport = "sauna"`. Keep them out of mileage, shoes, records and the run-equivalent conversion.
- **Data worth keeping:** date, start time, duration, average and max HR, and Garmin training load if present.
- **Dashboard:** something light that doesn't compete with the mileage chart, for example a "Sauna this week" stat tile (sessions and total minutes, with a delta vs last week) plus small markers on the weekly mileage chart for weeks with sauna sessions. Decide the design before building.
- **Training page:** consider whether sauna load belongs in the daily load chart, or should stay out because it isn't training.

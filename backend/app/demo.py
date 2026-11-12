"""Fake-but-plausible data for working on the UI before Garmin is connected."""

import random
from datetime import date, datetime, timedelta

from sqlmodel import Session, SQLModel, delete, select

from app.db import engine
from app.models import METERS_PER_MILE, DailyMetrics, Lap, PersonalRecord, Run, RunShoe, Shoe

# (weekday, kind, miles) for a typical week; 0 = Monday.
WEEK_PLAN = [(1, "workout", 7.0), (2, "easy", 5.0), (3, "easy", 6.0), (5, "long", 10.0), (6, "easy", 4.0), (0, "easy", 4.5)]


def seed(days: int = 460, rng_seed: int = 7) -> None:
    rng = random.Random(rng_seed)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        for model in (RunShoe, Lap, Run, Shoe, DailyMetrics, PersonalRecord):
            s.exec(delete(model))
        shoes = [
            Shoe(name="Pegasus 41", brand="Nike", model="Pegasus 41", color="#00539B", is_default=True),
            Shoe(name="Endorphin Speed 4", brand="Saucony", model="Endorphin Speed 4", color="#E89923", retire_at_miles=350),
            Shoe(name="Dragonfly 2", brand="Nike", model="ZoomX Dragonfly 2", color="#C84E00", retire_at_miles=250, default_for_category="track"),
            Shoe(name="Novablast 4", brand="ASICS", model="Novablast 4", color="#339898", start_miles=60),
            Shoe(name="Clifton 9", brand="HOKA", model="Clifton 9", retired_at=date.today() - timedelta(days=170), start_miles=0),
            Shoe(name="Ghost 15", brand="Brooks", model="Ghost 15", retired_at=date.today() - timedelta(days=300), start_miles=0),
        ]
        s.add_all(shoes)
        s.flush()
        daily, track, tempo, rotation, old, older = shoes[0], shoes[2], shoes[1], shoes[3], shoes[4], shoes[5]

        today = date.today()
        start = today - timedelta(days=days)
        activity_id = 17_000_000_000
        for offset in range(days + 1):
            day = start + timedelta(days=offset)
            progress = offset / days
            plan = {wd: (kind, mi) for wd, kind, mi in WEEK_PLAN}
            week_index = offset // 7
            cutback = week_index % 4 == 3
            if day.weekday() not in plan or rng.random() < 0.08:
                continue
            kind, base = plan[day.weekday()]
            miles = base * (0.8 + 0.45 * progress) * (0.75 if cutback else 1.0) * rng.uniform(0.9, 1.1)
            if kind == "long" and week_index % 6 == 5:
                miles *= 1.3
            easy_pace = 9 * 60 - 45 * progress + rng.uniform(-10, 10)  # s/mi
            category = "track" if kind == "workout" and day.weekday() == 1 else "road"
            hr = {"easy": 142, "long": 148, "workout": 158}[kind] + rng.uniform(-4, 4)
            activity_id += 1
            start_local = datetime.combine(day, datetime.min.time()) + timedelta(hours=6, minutes=rng.randint(0, 90))

            laps: list[tuple[float, float, float]] = []  # (miles, seconds, hr)
            if kind == "workout":
                laps.append((2.0, 2.0 * easy_pace, hr - 12))
                reps = max(3, int(miles - 3))
                for _ in range(reps):
                    laps.append((0.5, 0.5 * (easy_pace - 105), hr + 12))
                    laps.append((0.25, 0.25 * (easy_pace + 60), hr - 8))
                done = sum(lap[0] for lap in laps)
                laps.append((max(1.0, miles - done), max(1.0, miles - done) * easy_pace, hr - 10))
            else:
                whole = int(miles)
                laps = [(1.0, easy_pace * rng.uniform(0.97, 1.03), hr + rng.uniform(-3, 3)) for _ in range(whole)]
                if miles - whole > 0.05:
                    laps.append((miles - whole, (miles - whole) * easy_pace, hr))
            miles = sum(lap[0] for lap in laps)
            duration = sum(lap[1] for lap in laps)
            load = miles * {"easy": 9, "long": 11, "workout": 17}[kind]
            run = Run(
                garmin_activity_id=activity_id,
                start_local=start_local,
                start_utc=start_local + timedelta(hours=4),
                local_date=day,
                name={"easy": "Easy Run", "long": "Long Run", "workout": "Track Intervals"}[kind],
                type_key="track_running" if category == "track" else "running",
                category=category,
                distance_m=miles * METERS_PER_MILE,
                duration_s=duration,
                moving_s=duration * 0.99,
                avg_hr=hr,
                max_hr=hr + rng.uniform(15, 25),
                avg_cadence=170 + rng.uniform(-4, 8),
                elev_gain_m=miles * rng.uniform(5, 25),
                aerobic_te=round(rng.uniform(2.5, 4.2), 1),
                anaerobic_te=round(rng.uniform(0.2, 3.0 if kind == "workout" else 1.0), 1),
                training_load=load,
                vo2max=round(49 + 5 * progress + rng.uniform(-0.4, 0.4)),
                hr_zones=[duration * f for f in ((0.05, 0.55, 0.3, 0.08, 0.02) if kind != "workout" else (0.05, 0.3, 0.25, 0.25, 0.15))],
            )
            s.add(run)
            s.flush()
            for i, (lap_mi, lap_s, lap_hr) in enumerate(laps, start=1):
                s.add(Lap(run_id=run.id, idx=i, distance_m=lap_mi * METERS_PER_MILE, duration_s=lap_s,
                          avg_hr=lap_hr, avg_cadence=172.0, elev_gain_m=lap_mi * 8))

            # Shoes: workouts split warmup/cooldown (daily trainer) from reps (spikes/tempo shoe).
            shoe_for_easy = older if progress < 0.3 else old if progress < 0.62 else (daily if offset % 2 else rotation)
            if kind == "workout":
                reps_mi = sum(lap[0] for lap in laps[1:-1])
                s.add(RunShoe(run_id=run.id, shoe_id=shoe_for_easy.id, distance_m=laps[0][0] * METERS_PER_MILE, lap_from=1, lap_to=1))
                s.add(RunShoe(run_id=run.id, shoe_id=track.id, distance_m=reps_mi * METERS_PER_MILE, lap_from=2, lap_to=len(laps) - 1))
                if offset < days - 3:  # leave the newest workout's cooldown unassigned to show the warning
                    s.add(RunShoe(run_id=run.id, shoe_id=shoe_for_easy.id, distance_m=laps[-1][0] * METERS_PER_MILE, lap_from=len(laps), lap_to=len(laps)))
            elif kind == "long" and progress > 0.75:
                s.add(RunShoe(run_id=run.id, shoe_id=tempo.id, distance_m=run.distance_m))
            else:
                s.add(RunShoe(run_id=run.id, shoe_id=shoe_for_easy.id, distance_m=run.distance_m))

        # Easy rides, mostly in the last year: Wednesday evenings and some Saturdays.
        for offset in range(days + 1):
            day = start + timedelta(days=offset)
            progress = offset / days
            if progress < 0.2 or day.weekday() not in (2, 5) or rng.random() < (0.35 if day.weekday() == 2 else 0.6):
                continue
            indoor = rng.random() < 0.3
            ride_mi = rng.uniform(10, 16) if indoor else rng.uniform(14, 32)
            mph = rng.uniform(14, 16.5)
            seconds = ride_mi / mph * 3600
            activity_id += 1
            start_local = datetime.combine(day, datetime.min.time()) + timedelta(hours=17, minutes=rng.randint(0, 60))
            ride = Run(
                garmin_activity_id=activity_id,
                start_local=start_local,
                start_utc=start_local + timedelta(hours=4),
                local_date=day,
                name="Indoor Cycling" if indoor else "Easy Ride",
                type_key="indoor_cycling" if indoor else "road_biking",
                sport="ride",
                category="indoor" if indoor else "road",
                distance_m=ride_mi * METERS_PER_MILE,
                duration_s=seconds,
                moving_s=seconds * 0.97,
                avg_hr=128 + rng.uniform(-6, 6),
                max_hr=150 + rng.uniform(-6, 8),
                avg_cadence=86 + rng.uniform(-4, 4),
                elev_gain_m=0 if indoor else ride_mi * rng.uniform(4, 12),
                aerobic_te=round(rng.uniform(1.8, 3.0), 1),
                anaerobic_te=round(rng.uniform(0.0, 0.6), 1),
                # Some rides (e.g. a phone-recorded commute) come in without a training load.
                training_load=None if rng.random() < 0.1 else round(seconds / 60 * rng.uniform(0.7, 1.0)),
                hr_zones=[seconds * f for f in (0.2, 0.6, 0.18, 0.02, 0.0)],
            )
            s.add(ride)
            s.flush()
            whole = int(ride_mi // 5)
            for i in range(whole):
                s.add(Lap(run_id=ride.id, idx=i + 1, distance_m=5 * METERS_PER_MILE, duration_s=5 / mph * 3600,
                          avg_hr=ride.avg_hr, avg_cadence=ride.avg_cadence, elev_gain_m=0))

        acute = chronic = 300.0
        for offset in range(days + 1):
            day = start + timedelta(days=offset)
            progress = offset / days
            weekly_load = 380 + 260 * progress + (-90 if (offset // 7) % 4 == 3 else 0) + rng.uniform(-30, 30)
            acute = acute * 0.85 + weekly_load * 0.15
            chronic = chronic * 0.97 + weekly_load * 0.03
            vo2 = 49 + 5 * progress
            five_k = 21.5 * 60 - 110 * progress
            s.add(DailyMetrics(
                day=day,
                vo2max=round(vo2 + rng.uniform(-0.2, 0.2), 1),
                resting_hr=round(52 - 5 * progress + rng.uniform(-2, 2)),
                hrv_last_night=round(58 + 10 * progress + rng.uniform(-8, 8)),
                hrv_weekly_avg=round(58 + 10 * progress),
                hrv_status="BALANCED" if rng.random() > 0.12 else "UNBALANCED",
                readiness_score=round(min(100, max(10, 72 + rng.uniform(-30, 22)))),
                readiness_level=None,
                training_status="PRODUCTIVE_1" if acute / chronic > 1.0 else "MAINTAINING_1",
                acute_load=round(acute),
                chronic_load=round(chronic),
                acwr=round(acute / chronic, 2),
                race_5k_s=five_k,
                race_10k_s=five_k * 2.09,
                race_half_s=five_k * 4.65,
                race_full_s=five_k * 9.8,
                lt_hr=168,
                lt_pace_s_per_mile=7 * 60 + 20 - 25 * progress,
            ))
        for row in s.exec(select(DailyMetrics)):
            score = row.readiness_score or 0
            row.readiness_level = "HIGH" if score >= 75 else "MODERATE" if score >= 50 else "LOW"
        s.add_all([
            PersonalRecord(type_id=2, value=5 * 60 + 58, record_date=today - timedelta(days=40)),
            PersonalRecord(type_id=3, value=19 * 60 + 52, record_date=today - timedelta(days=75)),
            PersonalRecord(type_id=4, value=41 * 60 + 30, record_date=today - timedelta(days=150)),
            PersonalRecord(type_id=5, value=92 * 60 + 10, record_date=today - timedelta(days=200)),
            PersonalRecord(type_id=7, value=16.2 * METERS_PER_MILE, record_date=today - timedelta(days=30)),
        ])
        s.commit()

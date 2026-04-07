-- Allow catcher values in prediction_runs.position_track.
-- Safe to run multiple times.

alter table public.prediction_runs
  drop constraint if exists prediction_runs_position_track_check;

alter table public.prediction_runs
  add constraint prediction_runs_position_track_check
  check (position_track in ('pitcher', 'infielder', 'outfielder', 'catcher'));

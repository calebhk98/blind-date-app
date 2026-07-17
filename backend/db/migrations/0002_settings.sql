-- Runtime-editable settings store (design doc §7.4, issue #21).
--
-- A generic JSON-valued key/value table so settings can be edited in-app
-- (no redeploy) instead of only via CONFIG/env vars. Currently holds:
--   'hard_filter_criteria' -- JSON object mirroring
--       backend.logic.hard_filter.HardFilterCriteria
--   'hard_filter_enabled'  -- JSON boolean, the session-level draw-pool
--       toggle (design doc §7.4)
-- See backend/db/repository.py get_hard_filter_settings/set_hard_filter_settings
-- for the typed read/write helpers built on top of this table.

CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

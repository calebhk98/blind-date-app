-- Initial schema (design doc §6.1).
--
-- CHECK constraint values are the literal string values of the enums in
-- backend/domain/enums.py. They are generated with <Enum>.sql_check("col")
-- and hand-copied here (SQLite reads static .sql, it cannot import Python).
-- backend/tests/db/test_migrate.py asserts every enum value appears in this
-- file so the two never drift apart silently.

CREATE TABLE apps (
    app_id TEXT PRIMARY KEY,
    backend_type TEXT NOT NULL CHECK (backend_type IN ('web', 'appium')),
    display_name TEXT NOT NULL
);

CREATE TABLE profiles (
    profile_id TEXT PRIMARY KEY,
    app_id TEXT NOT NULL REFERENCES apps(app_id),
    external_id TEXT NOT NULL,
    bio_text TEXT,
    fetched_at TIMESTAMP NOT NULL,
    image_verdict TEXT NOT NULL DEFAULT 'pending' CHECK (image_verdict IN ('pending', 'yes', 'no')),
    text_verdict TEXT NOT NULL DEFAULT 'pending' CHECK (text_verdict IN ('pending', 'yes', 'no')),
    hard_filter_hit INTEGER NOT NULL DEFAULT 0 CHECK (hard_filter_hit IN (0, 1)),
    final_decision TEXT NOT NULL DEFAULT 'pending' CHECK (final_decision IN ('pending', 'yes', 'no')),
    decision_source TEXT CHECK (decision_source IS NULL OR decision_source IN ('auto', 'review')),
    swiped INTEGER NOT NULL DEFAULT 0 CHECK (swiped IN (0, 1))
);

CREATE TABLE photos (
    photo_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id),
    file_path TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    label TEXT NOT NULL DEFAULT 'pending' CHECK (label IN ('pending', 'yes', 'no', 'not_relevant')),
    judged_at TIMESTAMP
);

CREATE TABLE review_decisions (
    review_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id),
    trigger_reason TEXT NOT NULL CHECK (trigger_reason IN ('split_decision', 'all_not_relevant')),
    image_verdict_at_review TEXT,
    text_verdict_at_review TEXT,
    user_decision TEXT NOT NULL CHECK (user_decision IN ('yes', 'no')),
    decided_at TIMESTAMP NOT NULL
);

CREATE TABLE model_predictions (
    prediction_id TEXT PRIMARY KEY,
    model_name TEXT NOT NULL CHECK (model_name IN ('image', 'text', 'combined')),
    target_id TEXT NOT NULL,
    predicted_at TIMESTAMP NOT NULL,
    predicted_probability REAL NOT NULL,
    actual_label TEXT CHECK (actual_label IS NULL OR actual_label IN ('yes', 'no')),
    resolved_at TIMESTAMP
);

CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_profiles_app_id ON profiles(app_id);
CREATE INDEX idx_photos_profile_id ON photos(profile_id);
CREATE INDEX idx_photos_label ON photos(label);
CREATE INDEX idx_model_predictions_model_name ON model_predictions(model_name);

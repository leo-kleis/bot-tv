-- Migración: Agregar sub_tier y gifter_id a channel_users
ALTER TABLE channel_users
  ADD COLUMN IF NOT EXISTS sub_tier  TEXT DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS gifter_id TEXT DEFAULT NULL;

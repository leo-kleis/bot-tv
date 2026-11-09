-- Align schema and indexes idempotently with prisma/schema.prisma
CREATE INDEX IF NOT EXISTS "idx_users_username" ON "users"("username");
CREATE INDEX IF NOT EXISTS "idx_users_username_lower" ON "users"(LOWER("username"));
CREATE INDEX IF NOT EXISTS "idx_chat_history_channel_user" ON "chat_history"("channel_id", "user_id");
CREATE INDEX IF NOT EXISTS "idx_chat_history_channel_ts" ON "chat_history"("channel_id", "timestamp" DESC);
CREATE INDEX IF NOT EXISTS "idx_channel_users_followed" ON "channel_users"("channel_id", "followed_at" DESC);
CREATE INDEX IF NOT EXISTS "idx_channel_users_unfollowed" ON "channel_users"("channel_id", "unfollowed_at" DESC);
CREATE INDEX IF NOT EXISTS "idx_channel_users_gifter_id" ON "channel_users"("gifter_id");
CREATE INDEX IF NOT EXISTS "idx_api_consumption_ts" ON "api_consumption_log"("timestamp");
CREATE INDEX IF NOT EXISTS "idx_stream_events_event_data_gin" ON "stream_events" USING GIN ("event_data");

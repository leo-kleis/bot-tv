-- AlterTable
ALTER TABLE "chat_history" ADD COLUMN     "stream_id" TEXT;

-- CreateTable
CREATE TABLE "stream_sessions" (
    "stream_id" TEXT NOT NULL,
    "channel_id" TEXT NOT NULL,
    "title" TEXT,
    "category_name" TEXT,
    "is_live" BOOLEAN NOT NULL DEFAULT true,
    "started_at" TIMESTAMPTZ NOT NULL,
    "ended_at" TIMESTAMPTZ,
    "last_seen_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "peak_viewers" INTEGER NOT NULL DEFAULT 0,
    "close_reason" TEXT,

    CONSTRAINT "stream_sessions_pkey" PRIMARY KEY ("stream_id")
);

-- CreateTable
CREATE TABLE "viewer_snapshots" (
    "id" BIGSERIAL NOT NULL,
    "stream_id" TEXT NOT NULL,
    "channel_id" TEXT NOT NULL,
    "viewer_count" INTEGER NOT NULL,
    "recorded_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "viewer_snapshots_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "stream_events" (
    "id" BIGSERIAL NOT NULL,
    "stream_id" TEXT,
    "channel_id" TEXT NOT NULL,
    "event_type" TEXT NOT NULL,
    "event_data" JSONB NOT NULL DEFAULT '{}',
    "timestamp" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "stream_events_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "idx_stream_sessions_channel_started" ON "stream_sessions"("channel_id", "started_at" DESC);

-- CreateIndex
CREATE INDEX "idx_viewer_snapshots_stream_ts" ON "viewer_snapshots"("stream_id", "recorded_at" DESC);

-- CreateIndex
CREATE INDEX "idx_stream_events_stream_ts" ON "stream_events"("stream_id", "timestamp" DESC);

-- CreateIndex
CREATE INDEX "idx_stream_events_stream_type" ON "stream_events"("stream_id", "event_type");

-- CreateIndex
CREATE INDEX "idx_chat_history_stream_ts" ON "chat_history"("stream_id", "timestamp");

-- CreateIndex GIN
CREATE INDEX IF NOT EXISTS "idx_stream_events_event_data_gin" ON "stream_events" USING GIN ("event_data");

-- AddForeignKey
ALTER TABLE "viewer_snapshots" ADD CONSTRAINT "viewer_snapshots_stream_id_fkey" FOREIGN KEY ("stream_id") REFERENCES "stream_sessions"("stream_id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "stream_events" ADD CONSTRAINT "stream_events_stream_id_fkey" FOREIGN KEY ("stream_id") REFERENCES "stream_sessions"("stream_id") ON DELETE SET NULL ON UPDATE CASCADE;

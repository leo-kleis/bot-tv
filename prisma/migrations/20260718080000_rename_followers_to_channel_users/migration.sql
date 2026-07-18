-- 1. Renombrar la tabla followers a channel_users
ALTER TABLE "followers" RENAME TO "channel_users";

-- 2. Añadir las columnas de roles a la tabla renombrada
ALTER TABLE "channel_users" ADD COLUMN "is_moderator" BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE "channel_users" ADD COLUMN "is_vip" BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE "channel_users" ADD COLUMN "is_subscriber" BOOLEAN NOT NULL DEFAULT false;

-- 3. Mapear y migrar datos infiriendo el ID del canal desde los registros de followers y chat_history
DO $$
DECLARE
    v_channel_id TEXT;
BEGIN
    -- Obtener el ID del único canal usado actualmente
    SELECT channel_id INTO v_channel_id FROM "channel_users" LIMIT 1;
    
    IF v_channel_id IS NULL THEN
        SELECT channel_id INTO v_channel_id FROM "chat_history" LIMIT 1;
    END IF;

    -- Si hay un canal válido registrado, migramos los roles
    IF v_channel_id IS NOT NULL THEN
        -- Insertar primero en channel_users a usuarios que tienen algún rol activo pero no seguían el canal
        INSERT INTO "channel_users" (channel_id, user_id, followed_at, unfollowed_at, is_moderator, is_vip, is_subscriber)
        SELECT v_channel_id, u.user_id, NULL, NULL, u.is_moderator, u.is_vip, u.is_subscriber
        FROM "users" u
        WHERE (u.is_moderator = TRUE OR u.is_vip = TRUE OR u.is_subscriber = TRUE)
          AND NOT EXISTS (
              SELECT 1 FROM "channel_users" cu 
              WHERE cu.channel_id = v_channel_id AND cu.user_id = u.user_id
          );

        -- Actualizar los roles para los usuarios que ya existían en la tabla de seguidores
        UPDATE "channel_users" cu
        SET "is_moderator" = u."is_moderator",
            "is_vip" = u."is_vip",
            "is_subscriber" = u."is_subscriber"
        FROM "users" u
        WHERE cu.channel_id = v_channel_id AND cu.user_id = u.user_id;
    END IF;
END $$;

-- 4. Eliminar las columnas de roles globales de la tabla users
ALTER TABLE "users" DROP COLUMN "is_moderator";
ALTER TABLE "users" DROP COLUMN "is_vip";
ALTER TABLE "users" DROP COLUMN "is_subscriber";

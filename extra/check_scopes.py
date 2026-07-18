import asyncio
import sys

import aiohttp

sys.path.insert(0, "src")

from bot_tv.database.connection import create_pg_pool
from bot_tv.utils.security import get_fernet


async def check_token(token: str) -> dict:
    """Valida el token en Twitch y retorna la respuesta JSON."""
    url = "https://id.twitch.tv/oauth2/validate"
    headers = {"Authorization": f"OAuth {token}"}

    async with (
        aiohttp.ClientSession() as session,
        session.get(url, headers=headers) as response,
    ):
        return await response.json()


async def main():
    print("Conectando a la base de datos PostgreSQL...")
    try:
        pool = await create_pg_pool()
    except Exception as e:
        print(f"[X] Error al conectar a PostgreSQL: {e}")
        return

    fernet = get_fernet()

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id, username, token FROM tokens")

        if not rows:
            print("[X] No hay tokens almacenados en la base de datos.")
            return

        print(f"\nSe encontraron {len(rows)} tokens. Analizando Scopes...\n")
        print("-" * 50)

        for row in rows:
            username = row["username"]
            user_id = row["user_id"]
            encrypted_token = row["token"]

            print(f"[Usuario] Verificando cuenta: {username} (ID: {user_id})")

            try:
                decrypted_token = fernet.decrypt(encrypted_token.encode()).decode()
            except Exception as e:
                print(f"   [X] Error al desencriptar el token: {e}")
                print("-" * 50)
                continue

            validation_data = await check_token(decrypted_token)

            if "status" in validation_data and validation_data["status"] == 401:
                msg = validation_data.get("message", "Desconocido")
                print(f"   [X] Token inválido o expirado: {msg}")
            else:
                scopes = validation_data.get("scopes", [])
                client_id = validation_data.get("client_id")
                print(f"   [OK] Token válido. Client_ID: {client_id}")

                if "clips:edit" in scopes:
                    print("   [Clip] [clips:edit] [SI] lo tiene.")
                else:
                    print("   [X] [clips:edit] NO LO TIENE.")

                if "channel:read:subscriptions" in scopes:
                    print("   [Sub] [channel:read:subscriptions] [SI] lo tiene.")
                else:
                    print("   [X] [channel:read:subscriptions] NO LO TIENE.")

                print(f"   [Info] Listado de Scopes ({len(scopes)}):")
                for s in scopes:
                    print(f"        - {s}")

            print("-" * 50)

    except Exception as e:
        print(f"Error accediendo a la DB o validando: {e}")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())

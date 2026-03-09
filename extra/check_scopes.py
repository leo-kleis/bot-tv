import asyncio
import sqlite3
from pathlib import Path

import aiohttp

# Apuntamos a la base de datos de los tokens
DB_PATH = Path(__file__).resolve().parent.parent / "src" / "db" / "tokens.db"


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
    if not DB_PATH.exists():
        print(f"[X] No se encontró la base de datos en: {DB_PATH}")
        return

    print(f"Abriendo base de datos: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT user_id, username, token FROM tokens")
        tokens = cursor.fetchall()

        if not tokens:
            print("[X] No hay tokens almacenados en la base de datos.")
            return

        print(f"\nSe encontraron {len(tokens)} tokens. Analizando Scopes...\n")
        print("-" * 50)

        for row in tokens:
            username = row["username"]
            user_id = row["user_id"]
            token = row["token"]

            print(f"[Usuario] Verificando cuenta: {username} (ID: {user_id})")

            validation_data = await check_token(token)

            if "status" in validation_data and validation_data["status"] == 401:
                msg = validation_data.get("message", "Desconocido")
                print(f"   [X] Token inválido o expirado: {msg}")
            else:
                scopes = validation_data.get("scopes", [])
                client_id = validation_data.get("client_id")
                print(f"   [OK] Token válido. Client_ID: {client_id}")

                #! un if para cada scope
                if "clips:edit" in scopes:
                    print("   [Clip] [clips:edit] [SI] lo tiene.")
                else:
                    print("   [X] [clips:edit] NO LO TIENE.")

                print(f"   [Info] Listado de Scopes ({len(scopes)}):")
                for s in scopes:
                    print(f"        - {s}")

            print("-" * 50)

    except Exception as e:
        print(f"Error accediendo a la DB: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    asyncio.run(main())

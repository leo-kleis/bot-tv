import os
import sys

import requests
from dotenv import load_dotenv

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
USERS_URL = "https://api.twitch.tv/helix/users"


def get_app_access_token(client_id: str, client_secret: str) -> str:
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    }

    resp = requests.post(TOKEN_URL, data=data)
    if resp.status_code != 200:
        print("Error al obtener el app access token:")
        print(resp.status_code, resp.text)
        sys.exit(1)

    body = resp.json()
    return body["access_token"]


def get_user_id(access_token: str, client_id: str, username: str) -> str:
    params = {"login": username}
    headers = {
        "Client-Id": client_id,
        "Authorization": f"Bearer {access_token}",
    }

    resp = requests.get(USERS_URL, params=params, headers=headers)
    if resp.status_code != 200:
        print(f"Error al obtener datos de usuario para {username}:")
        print(resp.status_code, resp.text)
        sys.exit(1)

    data = resp.json().get("data", [])
    if not data:
        print(f"No se encontró el usuario '{username}'. ¿Está bien escrito?")
        sys.exit(1)

    return data[0]["id"]


def main():
    load_dotenv()

    client_id = os.getenv("TWITCH_CLIENT_ID")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Faltan TWITCH_CLIENT_ID o TWITCH_CLIENT_SECRET en el .env")
        sys.exit(1)

    print("Obteniendo app access token desde Twitch...")
    access_token = get_app_access_token(client_id, client_secret)
    print("Token obtenido correctamente.\n")

    bot_username = input("Username de la cuenta BOT (secundaria): ").strip().lower()
    owner_username = input("Username de la cuenta OWNER (principal): ").strip().lower()

    print("\nConsultando IDs en Twitch...\n")

    bot_id = get_user_id(access_token, client_id, bot_username)
    owner_id = get_user_id(access_token, client_id, owner_username)

    print("Resultados:")
    print(f"BOT_USERNAME : {bot_username}")
    print(f"BOT_ID       : {bot_id}")
    print()
    print(f"OWNER_USERNAME : {owner_username}")
    print(f"OWNER_ID       : {owner_id}")
    print("\nCopia estos valores en tu código de TwitchIO :)")


if __name__ == "__main__":
    main()

import os
import sys

import requests
from dotenv import load_dotenv

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
USERS_URL = "https://api.twitch.tv/helix/users"


def get_app_access_token(client_id: str, client_secret: str) -> str:
    """Obtiene un App Access Token desde Twitch usando Client Credentials."""
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


def get_user_by_id(access_token: str, client_id: str, user_id: str) -> dict | None:
    """
    Consulta la API de Twitch Helix /users usando un ID numérico.
    Retorna el diccionario con los datos del usuario, o None si no existe.
    """
    params = {"id": user_id}
    headers = {
        "Client-Id": client_id,
        "Authorization": f"Bearer {access_token}",
    }

    resp = requests.get(USERS_URL, params=params, headers=headers)
    if resp.status_code != 200:
        print(f"Error al consultar la API de Twitch (HTTP {resp.status_code}):")
        print(resp.text)
        sys.exit(1)

    data = resp.json().get("data", [])
    if not data:
        return None

    return data[0]


def print_user_info(user: dict) -> None:
    """Imprime de forma ordenada la información devuelta por la API."""
    twitch_username = user.get("login")
    print("\n--- Informacion del usuario ---")
    print(f"  ID              : {user.get('id')}")
    print(f"  Twitch          : https://twitch.tv/{twitch_username}")
    print(f"  Login           : {twitch_username}")
    print(f"  Display name    : {user.get('display_name')}")
    print(f"  Tipo de cuenta  : {user.get('broadcaster_type') or 'normal'}")
    print(f"  Descripcion     : {user.get('description') or '(sin descripcion)'}")
    print(f"  Creado el       : {user.get('created_at')}")
    print(f"  Vistas totales  : {user.get('view_count')}")
    print(f"  Avatar          : {user.get('profile_image_url')}")
    print("-------------------------------\n")


def main():
    load_dotenv()

    client_id = os.getenv("TWITCH_CLIENT_ID")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Faltan TWITCH_CLIENT_ID o TWITCH_CLIENT_SECRET en el .env")
        sys.exit(1)

    # Permite pasar el ID como argumento de linea de comandos o pedirlo manualmente
    if len(sys.argv) > 1:
        user_id = sys.argv[1].strip()
    else:
        user_id = input("Ingresa el ID numerico de Twitch a verificar: ").strip()

    if not user_id.isdigit():
        print(f"Error: '{user_id}' no es un ID numerico valido.")
        sys.exit(1)

    print("\nObteniendo token de acceso...")
    access_token = get_app_access_token(client_id, client_secret)
    print(f"Token obtenido. Consultando ID {user_id} en Twitch...\n")

    user = get_user_by_id(access_token, client_id, user_id)

    if user is None:
        print(f"No se encontro ningun usuario con el ID '{user_id}'.")
        print("Puede que el ID no exista o la cuenta haya sido eliminada.")
        sys.exit(0)

    print_user_info(user)


if __name__ == "__main__":
    main()

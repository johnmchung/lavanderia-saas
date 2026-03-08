import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")
NOMBRE_LAVANDERIA = os.getenv("NOMBRE_LAVANDERIA", "Lavandería")
LAVANDERIA_ID = int(os.getenv("LAVANDERIA_ID", "1"))


def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def get_lavanderia_data() -> dict:
    """Obtiene los datos de la lavandería activa desde la BD.
    Si falla (tabla no existe aún, error de red, etc.), usa variables de entorno como fallback."""
    try:
        sb = get_supabase()
        result = sb.table("lavanderias").select("*").eq("id", LAVANDERIA_ID).single().execute()
        if result.data:
            return result.data
    except Exception:
        pass
    # Fallback a variables de entorno (útil durante desarrollo o antes de migrar)
    return {
        "id": LAVANDERIA_ID,
        "nombre": NOMBRE_LAVANDERIA,
        "logo_url": None,
        "color_primario": "#16a34a",
        "telefono": None,
        "direccion": None,
    }

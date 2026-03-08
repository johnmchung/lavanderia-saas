import httpx
from app.config import WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, NOMBRE_LAVANDERIA


async def enviar_notificacion_listo(
    telefono: str, nombre_cliente: str, orden_id: int
):
    """
    Enviar mensaje de WhatsApp cuando la ropa está lista.
    Usa la API oficial de WhatsApp Cloud (Meta).

    Documentación: https://developers.facebook.com/docs/whatsapp/cloud-api/messages/text-messages
    """

    # Si no hay token configurado, solo logear (modo desarrollo)
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        print(f"[MOCK WhatsApp] → {telefono}: ¡Hola {nombre_cliente}! "
              f"Tu ropa en {NOMBRE_LAVANDERIA} está lista (Orden #{orden_id}).")
        return {"status": "mock", "telefono": telefono}

    # Limpiar teléfono: quitar + y espacios
    telefono_limpio = telefono.replace("+", "").replace(" ", "").replace("-", "")

    url = f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_ID}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    mensaje = (
        f"¡Hola {nombre_cliente}! 👋\n\n"
        f"Tu ropa en *{NOMBRE_LAVANDERIA}* está lista para recoger.\n"
        f"📋 Orden #{orden_id}\n\n"
        f"¡Te esperamos!"
    )

    payload = {
        "messaging_product": "whatsapp",
        "to": telefono_limpio,
        "type": "text",
        "text": {"body": mensaje},
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            print(f"[WhatsApp OK] → {telefono}: Notificación enviada")
            return {"status": "sent", "telefono": telefono}
        except httpx.HTTPError as e:
            print(f"[WhatsApp ERROR] → {telefono}: {e}")
            return {"status": "error", "telefono": telefono, "error": str(e)}

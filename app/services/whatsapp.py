import httpx
from app.config import WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, NOMBRE_LAVANDERIA


async def _enviar_whatsapp(telefono: str, mensaje: str) -> dict:
    """Enviar mensaje de texto por WhatsApp Cloud API."""
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        print(f"[MOCK WhatsApp] → {telefono}: {mensaje}")
        return {"status": "mock", "telefono": telefono}

    telefono_limpio = telefono.replace("+", "").replace(" ", "").replace("-", "")
    url = f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
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


async def enviar_notificacion_listo(
    telefono: str, nombre_cliente: str, orden_id: int
):
    """Enviar mensaje de WhatsApp cuando la ropa de lavandería está lista."""
    mensaje = (
        f"¡Hola {nombre_cliente}! 👋\n\n"
        f"Tu ropa en *{NOMBRE_LAVANDERIA}* está lista para recoger.\n"
        f"📋 Orden #{orden_id}\n\n"
        f"¡Te esperamos!"
    )
    return await _enviar_whatsapp(telefono, mensaje)


async def enviar_recordatorio_vencimiento(
    telefono: str, nombre_lavanderia: str, dias: int, template: str
):
    """Recordatorio de vencimiento de suscripción al owner."""
    mensaje = template.format(
        nombre=nombre_lavanderia,
        lavanderia=nombre_lavanderia,
        dias=dias,
    )
    return await _enviar_whatsapp(telefono, mensaje)


async def enviar_notificacion_sastreria_lista(
    telefono: str, nombre_cliente: str, trabajo_id: int, prenda: str
):
    """Enviar mensaje de WhatsApp cuando un trabajo de sastrería está listo."""
    mensaje = (
        f"¡Hola {nombre_cliente}! 👋\n\n"
        f"Tu trabajo de sastrería en *{NOMBRE_LAVANDERIA}* está listo para recoger.\n"
        f"✂️ Trabajo #{trabajo_id} - {prenda}\n\n"
        f"¡Te esperamos!"
    )
    return await _enviar_whatsapp(telefono, mensaje)

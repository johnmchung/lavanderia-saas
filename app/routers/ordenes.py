from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.config import get_supabase
from app.services.whatsapp import enviar_notificacion_listo

router = APIRouter()


class ServicioOrdenItem(BaseModel):
    servicio_id: int
    precio_personalizado: Optional[float] = None  # None = usar precio del catálogo


class OrdenCreate(BaseModel):
    cliente_id: int
    kilos: float
    servicios: list[ServicioOrdenItem]
    es_domicilio: bool = False
    direccion_entrega: Optional[str] = None
    notas: Optional[str] = None
    fecha_entrega_estimada: Optional[str] = None  # ISO 8601 string, e.g. "2024-03-10T17:00:00"


class CambiarEstatus(BaseModel):
    estatus: str  # recibido, en_proceso, listo, entregado


class PagoCreate(BaseModel):
    monto: float
    metodo: str  # yappy, nequi, efectivo, otro
    notas: Optional[str] = None


@router.get("/")
async def listar_ordenes(
    estatus: Optional[str] = None,
    fecha: Optional[str] = None,  # formato: YYYY-MM-DD
):
    """Listar órdenes. Filtrar por estatus y/o fecha."""
    db = get_supabase()

    # Usar la vista que tiene todo calculado
    query = db.table("vista_ordenes").select("*").order("created_at", desc=True)

    if estatus:
        query = query.eq("estatus", estatus)
    if fecha:
        query = query.gte("created_at", f"{fecha}T00:00:00").lte(
            "created_at", f"{fecha}T23:59:59"
        )

    result = query.execute()
    return result.data


@router.get("/{orden_id}")
async def obtener_orden(orden_id: int):
    db = get_supabase()
    result = (
        db.table("vista_ordenes").select("*").eq("id", orden_id).execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    orden = result.data[0]

    # Traer detalle de servicios
    servicios = (
        db.table("orden_servicios")
        .select("*, servicios(nombre)")
        .eq("orden_id", orden_id)
        .execute()
    )
    orden["detalle_servicios"] = servicios.data

    # Traer pagos
    pagos = (
        db.table("pagos")
        .select("*")
        .eq("orden_id", orden_id)
        .order("created_at")
        .execute()
    )
    orden["pagos"] = pagos.data

    return orden


@router.post("/")
async def crear_orden(orden: OrdenCreate):
    """Crear una nueva orden con sus servicios."""
    db = get_supabase()

    # Verificar que el cliente existe
    cliente = (
        db.table("clientes")
        .select("id")
        .eq("id", orden.cliente_id)
        .execute()
    )
    if not cliente.data:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    # Obtener precios de los servicios seleccionados
    servicio_ids = [item.servicio_id for item in orden.servicios]
    precios_custom = {item.servicio_id: item.precio_personalizado for item in orden.servicios}

    servicios = (
        db.table("servicios")
        .select("id, nombre, precio_por_kilo, tipo_precio")
        .in_("id", servicio_ids)
        .execute()
    )
    if not servicios.data:
        raise HTTPException(status_code=400, detail="Servicios no válidos")

    # Crear la orden
    orden_data = {
        "cliente_id": orden.cliente_id,
        "kilos": orden.kilos,
        "es_domicilio": orden.es_domicilio,
        "direccion_entrega": orden.direccion_entrega if orden.es_domicilio else None,
        "estatus": "recibido",
        "notas": orden.notas,
        "fecha_entrega_estimada": orden.fecha_entrega_estimada,
    }
    nueva_orden = db.table("ordenes").insert(orden_data).execute()
    orden_id = nueva_orden.data[0]["id"]

    # Crear los registros de servicios con subtotales (usando precio personalizado si existe)
    for servicio in servicios.data:
        tipo = servicio.get("tipo_precio", "por_kilo")
        precio_catalogo = servicio["precio_por_kilo"]
        precio = precios_custom.get(servicio["id"]) or precio_catalogo
        if tipo == "fijo":
            subtotal = round(precio, 2)
        else:
            subtotal = round(orden.kilos * precio, 2)
        db.table("orden_servicios").insert(
            {
                "orden_id": orden_id,
                "servicio_id": servicio["id"],
                "precio_por_kilo": precio,  # precio real cobrado
                "tipo_precio": tipo,
                "subtotal": subtotal,
            }
        ).execute()

    # Retornar la orden completa
    result = (
        db.table("vista_ordenes").select("*").eq("id", orden_id).execute()
    )
    return result.data[0]


@router.patch("/{orden_id}/estatus")
async def cambiar_estatus(orden_id: int, datos: CambiarEstatus):
    """Cambiar el estatus de una orden. Si cambia a 'listo', envía WhatsApp."""
    db = get_supabase()

    estatuses_validos = ["recibido", "en_proceso", "listo", "entregado"]
    if datos.estatus not in estatuses_validos:
        raise HTTPException(
            status_code=400,
            detail=f"Estatus inválido. Opciones: {estatuses_validos}",
        )

    # Actualizar estatus
    result = (
        db.table("ordenes")
        .update({"estatus": datos.estatus})
        .eq("id", orden_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    # Si cambió a "listo", enviar notificación por WhatsApp
    if datos.estatus == "listo":
        orden_completa = (
            db.table("vista_ordenes").select("*").eq("id", orden_id).execute()
        )
        if orden_completa.data:
            orden = orden_completa.data[0]
            await enviar_notificacion_listo(
                telefono=orden["cliente_telefono"],
                nombre_cliente=orden["cliente_nombre"],
                orden_id=orden["id"],
            )

    return {"message": f"Orden {orden_id} actualizada a '{datos.estatus}'"}


@router.post("/{orden_id}/pagos")
async def registrar_pago(orden_id: int, pago: PagoCreate):
    """Registrar un pago para una orden."""
    db = get_supabase()

    metodos_validos = ["yappy", "nequi", "efectivo", "otro"]
    if pago.metodo not in metodos_validos:
        raise HTTPException(
            status_code=400,
            detail=f"Método inválido. Opciones: {metodos_validos}",
        )

    # Verificar que la orden existe
    orden = db.table("ordenes").select("id").eq("id", orden_id).execute()
    if not orden.data:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    pago_data = {
        "orden_id": orden_id,
        "monto": pago.monto,
        "metodo": pago.metodo,
        "notas": pago.notas,
    }
    result = db.table("pagos").insert(pago_data).execute()
    return result.data[0]

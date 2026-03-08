from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.config import get_supabase
from app.services.whatsapp import enviar_notificacion_sastreria_lista

router = APIRouter()

TIPOS_TRABAJO = ["ruedo", "zipper", "boton", "otro"]
ESTATUSES_VALIDOS = ["recibido", "en_proceso", "listo", "entregado"]


class SastreriaCreate(BaseModel):
    cliente_id: int
    descripcion: str
    tipo_trabajo: str  # ruedo, zipper, boton, otro
    prenda: str
    precio: float
    fecha_entrega_estimada: Optional[str] = None  # ISO 8601
    notas: Optional[str] = None


class CambiarEstatus(BaseModel):
    estatus: str


class NotasUpdate(BaseModel):
    notas: Optional[str] = None


@router.get("/")
async def listar_trabajos(
    estatus: Optional[str] = None,
    fecha: Optional[str] = None,  # YYYY-MM-DD
):
    """Listar trabajos de sastrería. Filtrar por estatus y/o fecha."""
    db = get_supabase()

    query = (
        db.table("sastreria")
        .select("*, clientes(nombre, telefono)")
        .order("created_at", desc=True)
    )

    if estatus:
        query = query.eq("estatus", estatus)
    if fecha:
        query = query.gte("created_at", f"{fecha}T00:00:00").lte(
            "created_at", f"{fecha}T23:59:59"
        )

    result = query.execute()

    # Aplanar datos del cliente para facilitar uso en frontend
    trabajos = []
    for t in result.data:
        cliente = t.pop("clientes", {}) or {}
        t["cliente_nombre"] = cliente.get("nombre", "—")
        t["cliente_telefono"] = cliente.get("telefono", "—")
        trabajos.append(t)

    return trabajos


@router.get("/{trabajo_id}")
async def obtener_trabajo(trabajo_id: int):
    db = get_supabase()
    result = (
        db.table("sastreria")
        .select("*, clientes(nombre, telefono)")
        .eq("id", trabajo_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")

    t = result.data[0]
    cliente = t.pop("clientes", {}) or {}
    t["cliente_nombre"] = cliente.get("nombre", "—")
    t["cliente_telefono"] = cliente.get("telefono", "—")
    return t


@router.post("/")
async def crear_trabajo(trabajo: SastreriaCreate):
    """Crear un nuevo trabajo de sastrería."""
    db = get_supabase()

    if trabajo.tipo_trabajo not in TIPOS_TRABAJO:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de trabajo inválido. Opciones: {TIPOS_TRABAJO}",
        )

    # Verificar que el cliente existe
    cliente = db.table("clientes").select("id").eq("id", trabajo.cliente_id).execute()
    if not cliente.data:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    data = {
        "cliente_id": trabajo.cliente_id,
        "descripcion": trabajo.descripcion,
        "tipo_trabajo": trabajo.tipo_trabajo,
        "prenda": trabajo.prenda,
        "precio": trabajo.precio,
        "estatus": "recibido",
        "fecha_entrega_estimada": trabajo.fecha_entrega_estimada,
        "notas": trabajo.notas,
    }
    result = db.table("sastreria").insert(data).execute()
    nuevo = result.data[0]

    # Enriquecer con datos del cliente
    cli = db.table("clientes").select("nombre, telefono").eq("id", trabajo.cliente_id).execute()
    if cli.data:
        nuevo["cliente_nombre"] = cli.data[0]["nombre"]
        nuevo["cliente_telefono"] = cli.data[0]["telefono"]

    return nuevo


@router.patch("/{trabajo_id}/estatus")
async def cambiar_estatus(trabajo_id: int, datos: CambiarEstatus):
    """Cambiar estatus. Si cambia a 'listo', envía WhatsApp al cliente."""
    db = get_supabase()

    if datos.estatus not in ESTATUSES_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Estatus inválido. Opciones: {ESTATUSES_VALIDOS}",
        )

    result = (
        db.table("sastreria")
        .update({"estatus": datos.estatus})
        .eq("id", trabajo_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")

    if datos.estatus == "listo":
        trabajo = (
            db.table("sastreria")
            .select("*, clientes(nombre, telefono)")
            .eq("id", trabajo_id)
            .execute()
        )
        if trabajo.data:
            t = trabajo.data[0]
            cliente = t.get("clientes") or {}
            await enviar_notificacion_sastreria_lista(
                telefono=cliente.get("telefono", ""),
                nombre_cliente=cliente.get("nombre", ""),
                trabajo_id=t["id"],
                prenda=t["prenda"],
            )

    return {"message": f"Trabajo {trabajo_id} actualizado a '{datos.estatus}'"}


@router.patch("/{trabajo_id}/notas")
async def actualizar_notas(trabajo_id: int, datos: NotasUpdate):
    """Actualizar las notas de un trabajo."""
    db = get_supabase()
    result = (
        db.table("sastreria")
        .update({"notas": datos.notas})
        .eq("id", trabajo_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    return {"message": f"Notas del trabajo {trabajo_id} actualizadas"}


@router.delete("/{trabajo_id}")
async def eliminar_trabajo(trabajo_id: int):
    """Eliminar un trabajo de sastrería."""
    db = get_supabase()
    result = db.table("sastreria").delete().eq("id", trabajo_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    return {"message": f"Trabajo {trabajo_id} eliminado"}

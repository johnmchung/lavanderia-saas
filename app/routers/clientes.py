from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.config import get_supabase

router = APIRouter()


class ClienteCreate(BaseModel):
    nombre: str
    telefono: str  # +507XXXXXXXX
    direccion: Optional[str] = None
    notas: Optional[str] = None


class ClienteUpdate(BaseModel):
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    notas: Optional[str] = None


@router.get("/")
async def listar_clientes(buscar: Optional[str] = None):
    """Listar todos los clientes, opcionalmente filtrar por nombre o teléfono."""
    db = get_supabase()
    query = db.table("clientes").select("*").order("nombre")

    if buscar:
        query = query.or_(f"nombre.ilike.%{buscar}%,telefono.ilike.%{buscar}%")

    result = query.execute()
    return result.data


@router.get("/{cliente_id}/perfil")
async def perfil_cliente(cliente_id: int):
    """Perfil completo del cliente: datos, estadísticas y últimas 10 órdenes."""
    db = get_supabase()

    cliente_res = db.table("clientes").select("*").eq("id", cliente_id).execute()
    if not cliente_res.data:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    cliente = cliente_res.data[0]

    ordenes_res = (
        db.table("vista_ordenes")
        .select("id,estatus,precio_total,total_pagado,created_at,servicios,kilos")
        .eq("cliente_id", cliente_id)
        .order("created_at", desc=True)
        .execute()
    )
    ordenes = ordenes_res.data or []

    total_ordenes = len(ordenes)
    total_gastado = sum(float(o.get("precio_total") or 0) for o in ordenes)
    total_pagado_sum = sum(float(o.get("total_pagado") or 0) for o in ordenes)
    saldo_pendiente = total_gastado - total_pagado_sum

    fechas = sorted([o["created_at"] for o in ordenes if o.get("created_at")])
    primera_visita = fechas[0] if fechas else None
    ultima_visita = fechas[-1] if fechas else None

    return {
        "cliente": cliente,
        "estadisticas": {
            "total_ordenes": total_ordenes,
            "total_gastado": round(total_gastado, 2),
            "saldo_pendiente": round(saldo_pendiente, 2),
            "es_frecuente": total_ordenes > 10,
            "primera_visita": primera_visita,
            "ultima_visita": ultima_visita,
        },
        "ultimas_ordenes": ordenes[:10],
    }


@router.get("/{cliente_id}")
async def obtener_cliente(cliente_id: int):
    db = get_supabase()
    result = db.table("clientes").select("*").eq("id", cliente_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return result.data[0]


@router.post("/")
async def crear_cliente(cliente: ClienteCreate):
    """Crear un nuevo cliente."""
    db = get_supabase()

    # Validar formato de teléfono panameño
    telefono = cliente.telefono.strip()
    if not telefono.startswith("+507"):
        telefono = f"+507{telefono}"

    data = {
        "nombre": cliente.nombre.strip(),
        "telefono": telefono,
        "direccion": cliente.direccion,
        "notas": cliente.notas,
    }

    result = db.table("clientes").insert(data).execute()
    return result.data[0]


@router.patch("/{cliente_id}")
async def actualizar_cliente(cliente_id: int, cliente: ClienteUpdate):
    db = get_supabase()
    data = {k: v for k, v in cliente.model_dump().items() if v is not None}

    if not data:
        raise HTTPException(status_code=400, detail="Nada que actualizar")

    result = db.table("clientes").update(data).eq("id", cliente_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return result.data[0]

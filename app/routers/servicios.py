from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.config import get_supabase

router = APIRouter()

TIPOS_VALIDOS = ("por_kilo", "fijo")


class ServicioCreate(BaseModel):
    nombre: str
    precio: float
    tipo_precio: str = "por_kilo"  # 'por_kilo' o 'fijo'


class ServicioUpdate(BaseModel):
    precio: Optional[float] = None
    tipo_precio: Optional[str] = None
    activo: Optional[bool] = None


@router.get("/")
async def listar_servicios():
    db = get_supabase()
    result = db.table("servicios").select("*").eq("activo", True).order("id").execute()
    return result.data


@router.get("/todos")
async def listar_todos_servicios():
    """Devuelve activos e inactivos (para la página de administración)."""
    db = get_supabase()
    result = db.table("servicios").select("*").order("id").execute()
    return result.data


@router.post("/")
async def crear_servicio(datos: ServicioCreate):
    nombre = datos.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="El nombre es obligatorio")
    if datos.precio <= 0:
        raise HTTPException(status_code=400, detail="El precio debe ser mayor a 0")
    if datos.tipo_precio not in TIPOS_VALIDOS:
        raise HTTPException(status_code=400, detail="tipo_precio debe ser 'por_kilo' o 'fijo'")

    db = get_supabase()
    result = db.table("servicios").insert({
        "nombre": nombre,
        "precio_por_kilo": datos.precio,
        "tipo_precio": datos.tipo_precio,
        "activo": True,
    }).execute()
    return result.data[0]


@router.patch("/{servicio_id}")
async def actualizar_servicio(servicio_id: int, datos: ServicioUpdate):
    updates = {}
    if datos.precio is not None:
        if datos.precio <= 0:
            raise HTTPException(status_code=400, detail="El precio debe ser mayor a 0")
        updates["precio_por_kilo"] = datos.precio
    if datos.tipo_precio is not None:
        if datos.tipo_precio not in TIPOS_VALIDOS:
            raise HTTPException(status_code=400, detail="tipo_precio debe ser 'por_kilo' o 'fijo'")
        updates["tipo_precio"] = datos.tipo_precio
    if datos.activo is not None:
        updates["activo"] = datos.activo

    if not updates:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")

    db = get_supabase()
    result = db.table("servicios").update(updates).eq("id", servicio_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    return result.data[0]

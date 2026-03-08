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

from fastapi import APIRouter
from typing import Optional
from app.config import get_supabase, LAVANDERIA_ID

router = APIRouter()


@router.get("/")
async def buscar(q: Optional[str] = ""):
    q = (q or "").strip()
    if len(q) < 2:
        return {"clientes": [], "ordenes": []}

    db = get_supabase()

    # ── Clientes: buscar por nombre o teléfono ─────────────────────────────
    clientes_res = (
        db.table("clientes")
        .select("id, nombre, telefono")
        .eq("lavanderia_id", LAVANDERIA_ID)
        .or_(f"nombre.ilike.%{q}%,telefono.ilike.%{q}%")
        .order("nombre")
        .limit(5)
        .execute()
    )
    clientes = clientes_res.data or []

    # ── Órdenes: buscar por nombre de cliente y (si es número) por id ──────
    try:
        if q.isdigit():
            ordenes_res = (
                db.table("vista_ordenes")
                .select("id, cliente_nombre, estatus, created_at")
                .or_(f"id.eq.{int(q)},cliente_nombre.ilike.%{q}%")
                .order("created_at", desc=True)
                .limit(5)
                .execute()
            )
        else:
            ordenes_res = (
                db.table("vista_ordenes")
                .select("id, cliente_nombre, estatus, created_at")
                .ilike("cliente_nombre", f"%{q}%")
                .order("created_at", desc=True)
                .limit(5)
                .execute()
            )
        ordenes = ordenes_res.data or []
    except Exception:
        ordenes = []

    return {"clientes": clientes, "ordenes": ordenes}

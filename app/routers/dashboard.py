from fastapi import APIRouter
from datetime import date
from app.config import get_supabase

router = APIRouter()


@router.get("/hoy")
async def resumen_hoy():
    """Resumen del día: ventas totales, órdenes por estatus, métodos de pago."""
    db = get_supabase()
    hoy = date.today().isoformat()

    # Órdenes del día con totales
    ordenes = (
        db.table("vista_ordenes")
        .select("*")
        .gte("created_at", f"{hoy}T00:00:00")
        .lte("created_at", f"{hoy}T23:59:59")
        .execute()
    )

    datos = ordenes.data or []

    # Calcular métricas
    total_ordenes = len(datos)
    ventas_total = sum(float(o.get("precio_total", 0)) for o in datos)
    total_cobrado = sum(float(o.get("total_pagado", 0)) for o in datos)
    pendiente_cobro = ventas_total - total_cobrado

    # Contar por estatus
    por_estatus = {}
    for o in datos:
        est = o["estatus"]
        por_estatus[est] = por_estatus.get(est, 0) + 1

    # Órdenes pendientes de entrega (no solo de hoy, todas)
    pendientes = (
        db.table("vista_ordenes")
        .select("*", count="exact")
        .in_("estatus", ["recibido", "en_proceso", "listo"])
        .execute()
    )

    return {
        "fecha": hoy,
        "total_ordenes_hoy": total_ordenes,
        "ventas_total": round(ventas_total, 2),
        "total_cobrado": round(total_cobrado, 2),
        "pendiente_cobro": round(pendiente_cobro, 2),
        "ordenes_por_estatus": por_estatus,
        "total_pendientes_entrega": pendientes.count or 0,
    }

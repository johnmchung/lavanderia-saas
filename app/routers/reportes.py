from fastapi import APIRouter
from app.config import get_supabase

router = APIRouter()


@router.get("/deudas")
async def deudas_pendientes():
    """Clientes con saldo pendiente > 0, ordenados de mayor a menor deuda."""
    db = get_supabase()

    ordenes = (
        db.table("vista_ordenes")
        .select("cliente_id,cliente_nombre,cliente_telefono,precio_total,total_pagado,id")
        .execute()
    )

    datos = ordenes.data or []

    # Agrupar por cliente y sumar saldo pendiente
    clientes = {}
    for o in datos:
        precio = float(o.get("precio_total") or 0)
        pagado = float(o.get("total_pagado") or 0)
        saldo = precio - pagado
        if saldo <= 0:
            continue

        cid = o["cliente_id"]
        if cid not in clientes:
            clientes[cid] = {
                "cliente_id": cid,
                "nombre": o.get("cliente_nombre", ""),
                "telefono": o.get("cliente_telefono", ""),
                "ordenes_con_deuda": 0,
                "total_deuda": 0.0,
            }
        clientes[cid]["ordenes_con_deuda"] += 1
        clientes[cid]["total_deuda"] += saldo

    lista = sorted(clientes.values(), key=lambda x: x["total_deuda"], reverse=True)

    for c in lista:
        c["total_deuda"] = round(c["total_deuda"], 2)

    total_general = round(sum(c["total_deuda"] for c in lista), 2)

    return {
        "total_general": total_general,
        "total_clientes": len(lista),
        "deudores": lista,
    }

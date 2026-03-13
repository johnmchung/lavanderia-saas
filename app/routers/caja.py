from datetime import date

from fastapi import APIRouter

from app.config import LAVANDERIA_ID, get_supabase

router = APIRouter()

METODOS = ["efectivo", "yappy", "nequi", "otro"]


@router.get("/resumen")
async def resumen_caja():
    db = get_supabase()
    hoy = date.today().isoformat()

    # Pagos de hoy filtrando por lavanderia_id via join con ordenes
    pagos_res = (
        db.table("pagos")
        .select(
            "id, monto, metodo, created_at, orden_id,"
            " ordenes!inner(lavanderia_id, clientes!inner(nombre))"
        )
        .eq("ordenes.lavanderia_id", LAVANDERIA_ID)
        .gte("created_at", f"{hoy}T00:00:00")
        .lte("created_at", f"{hoy}T23:59:59")
        .order("created_at")
        .execute()
    )
    pagos = pagos_res.data or []

    total_cobrado = sum(float(p["monto"]) for p in pagos)
    desglose = {m: {"count": 0, "total": 0.0} for m in METODOS}
    lista_pagos = []

    for p in pagos:
        metodo = p.get("metodo") or "otro"
        if metodo not in desglose:
            metodo = "otro"
        desglose[metodo]["count"] += 1
        desglose[metodo]["total"] = round(desglose[metodo]["total"] + float(p["monto"]), 2)

        cliente_nombre = "—"
        orden_data = p.get("ordenes")
        if orden_data and orden_data.get("clientes"):
            cliente_nombre = orden_data["clientes"].get("nombre", "—")

        hora_utc = p["created_at"][11:16] if p.get("created_at") else "—"

        lista_pagos.append(
            {
                "id": p["id"],
                "hora": hora_utc,
                "orden_id": p["orden_id"],
                "cliente": cliente_nombre,
                "monto": float(p["monto"]),
                "metodo": metodo,
            }
        )

    # Órdenes creadas hoy
    ordenes_res = (
        db.table("ordenes")
        .select("id, estatus")
        .eq("lavanderia_id", LAVANDERIA_ID)
        .gte("created_at", f"{hoy}T00:00:00")
        .lte("created_at", f"{hoy}T23:59:59")
        .execute()
    )
    ordenes = ordenes_res.data or []
    ordenes_creadas = len(ordenes)
    ordenes_entregadas = sum(1 for o in ordenes if o["estatus"] == "entregado")
    ordenes_con_pago = len({p["orden_id"] for p in pagos})

    return {
        "fecha": hoy,
        "total_cobrado": round(total_cobrado, 2),
        "num_pagos": len(pagos),
        "ordenes_con_pago": ordenes_con_pago,
        "ordenes_creadas_hoy": ordenes_creadas,
        "ordenes_entregadas_hoy": ordenes_entregadas,
        "desglose": desglose,
        "pagos": lista_pagos,
    }

from fastapi import APIRouter
from datetime import date, timedelta
from collections import defaultdict
from app.config import get_supabase

router = APIRouter()


@router.get("/hoy")
async def resumen_hoy():
    """Resumen del día: ventas, estatus, cobro, ticket promedio, hora pico."""
    db = get_supabase()
    hoy = date.today().isoformat()

    ordenes = (
        db.table("vista_ordenes")
        .select("*")
        .gte("created_at", f"{hoy}T00:00:00")
        .lte("created_at", f"{hoy}T23:59:59")
        .execute()
    )

    datos = ordenes.data or []
    total_ordenes = len(datos)
    ventas_total = sum(float(o.get("precio_total", 0)) for o in datos)
    total_cobrado = sum(float(o.get("total_pagado", 0)) for o in datos)
    pendiente_cobro = ventas_total - total_cobrado

    # Contar por estatus
    por_estatus: dict[str, int] = {}
    for o in datos:
        est = o["estatus"]
        por_estatus[est] = por_estatus.get(est, 0) + 1

    # Órdenes por hora del día
    por_hora: dict[int, int] = defaultdict(int)
    for o in datos:
        try:
            hora = int(o["created_at"][11:13])
            por_hora[hora] += 1
        except Exception:
            pass

    hora_pico = max(por_hora, key=lambda h: por_hora[h]) if por_hora else None
    hora_pico_label = f"{hora_pico:02d}:00" if hora_pico is not None else "—"

    # Métricas derivadas
    ticket_promedio = round(ventas_total / total_ordenes, 2) if total_ordenes > 0 else 0.0
    tasa_cobro = round((total_cobrado / ventas_total) * 100, 1) if ventas_total > 0 else 0.0

    # Órdenes pendientes históricas (todos los días)
    pendientes = (
        db.table("vista_ordenes")
        .select("id", count="exact")
        .in_("estatus", ["recibido", "en_proceso", "listo"])
        .execute()
    )

    return {
        "fecha": hoy,
        "total_ordenes_hoy": total_ordenes,
        "ventas_total": round(ventas_total, 2),
        "total_cobrado": round(total_cobrado, 2),
        "pendiente_cobro": round(pendiente_cobro, 2),
        "ticket_promedio": ticket_promedio,
        "tasa_cobro": tasa_cobro,
        "hora_pico": hora_pico_label,
        "ordenes_por_estatus": por_estatus,
        "total_pendientes_entrega": pendientes.count or 0,
    }


@router.get("/semana")
async def resumen_semana():
    """Comparación esta semana vs semana pasada + últimos 7 días para gráfico."""
    db = get_supabase()
    hoy = date.today()
    hace_14 = hoy - timedelta(days=13)

    ordenes = (
        db.table("vista_ordenes")
        .select("created_at, precio_total")
        .gte("created_at", f"{hace_14.isoformat()}T00:00:00")
        .lte("created_at", f"{hoy.isoformat()}T23:59:59")
        .execute()
    )

    # Agrupar por fecha
    por_dia: dict[str, float] = defaultdict(float)
    for o in (ordenes.data or []):
        try:
            fecha = o["created_at"][:10]
            por_dia[fecha] += float(o.get("precio_total", 0))
        except Exception:
            pass

    # Últimos 7 días para el gráfico (Dom=0 … Sáb=6)
    dias_es = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"]
    ultimos_7 = []
    for i in range(6, -1, -1):
        d = hoy - timedelta(days=i)
        fecha_str = d.isoformat()
        ultimos_7.append({
            "fecha": fecha_str,
            "label": dias_es[(d.weekday() + 1) % 7],
            "ventas": round(por_dia.get(fecha_str, 0.0), 2),
        })

    # Esta semana (lunes → hoy)
    lunes = hoy - timedelta(days=hoy.weekday())
    esta_semana = round(sum(
        por_dia.get((lunes + timedelta(days=i)).isoformat(), 0.0)
        for i in range((hoy - lunes).days + 1)
    ), 2)

    # Semana pasada (lunes → domingo anteriores)
    lunes_pasado = lunes - timedelta(days=7)
    semana_pasada = round(sum(
        por_dia.get((lunes_pasado + timedelta(days=i)).isoformat(), 0.0)
        for i in range(7)
    ), 2)

    variacion = 0.0
    if semana_pasada > 0:
        variacion = round(((esta_semana - semana_pasada) / semana_pasada) * 100, 1)

    return {
        "esta_semana": esta_semana,
        "semana_pasada": semana_pasada,
        "variacion_pct": variacion,
        "ultimos_7_dias": ultimos_7,
    }


@router.get("/top-servicios")
async def top_servicios():
    """Top 5 servicios más vendidos (por cantidad de unidades)."""
    db = get_supabase()
    try:
        result = (
            db.table("orden_servicios")
            .select("servicio_id, cantidad, servicios(nombre)")
            .execute()
        )

        conteo: dict = defaultdict(lambda: {"nombre": "—", "cantidad": 0})
        for row in (result.data or []):
            sid = row.get("servicio_id")
            srv = row.get("servicios")
            nombre = srv.get("nombre", f"#{sid}") if isinstance(srv, dict) else f"#{sid}"
            conteo[sid]["nombre"] = nombre
            conteo[sid]["cantidad"] += int(row.get("cantidad") or 1)

        top = sorted(conteo.values(), key=lambda x: x["cantidad"], reverse=True)[:5]
        return {"top_servicios": top}
    except Exception:
        return {"top_servicios": []}


@router.get("/top-clientes")
async def top_clientes():
    """Top 5 clientes más frecuentes (por número de órdenes)."""
    db = get_supabase()
    try:
        result = (
            db.table("ordenes")
            .select("cliente_id, clientes(nombre)")
            .execute()
        )

        conteo: dict = defaultdict(lambda: {"nombre": "—", "ordenes": 0})
        for row in (result.data or []):
            cid = row.get("cliente_id")
            cli = row.get("clientes")
            nombre = cli.get("nombre", f"#{cid}") if isinstance(cli, dict) else f"#{cid}"
            conteo[cid]["nombre"] = nombre
            conteo[cid]["ordenes"] += 1

        top = sorted(conteo.values(), key=lambda x: x["ordenes"], reverse=True)[:5]
        return {"top_clientes": top}
    except Exception:
        return {"top_clientes": []}

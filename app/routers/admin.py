import secrets
import string
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.config import get_supabase, get_supabase_with_token
from app.utils import calcular_estatus_suscripcion

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Autenticación superadmin ───────────────────────────────────────────────

async def _require_superadmin(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=403, detail="Sin autenticación")
    try:
        sb = get_supabase_with_token(token)
        user_resp = sb.auth.get_user(token)
        if not user_resp.user:
            raise HTTPException(status_code=403, detail="Token inválido")
        result = (
            sb.table("usuarios")
            .select("id, email, rol, lavanderia_id, activo")
            .eq("id", user_resp.user.id)
            .eq("activo", True)
            .single()
            .execute()
        )
        if not result.data or result.data["rol"] != "superadmin":
            raise HTTPException(status_code=403, detail="Solo superadmin")
        return result.data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=403, detail="Sin autorización")


def _generar_password(longitud: int = 12) -> str:
    chars = string.ascii_letters + string.digits + "!@#$"
    return "".join(secrets.choice(chars) for _ in range(longitud))


# ── Schemas ────────────────────────────────────────────────────────────────

class NuevaLavanderiaPayload(BaseModel):
    nombre: str
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    ciudad: Optional[str] = None
    color_primario: str = "#16a34a"
    plan: str = "trial"
    dias_trial: int = 14
    owner_email: str
    owner_password: Optional[str] = None


class NuevoOwnerPayload(BaseModel):
    owner_email: str
    owner_password: Optional[str] = None


class ActualizarLavanderiaPayload(BaseModel):
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    ciudad: Optional[str] = None
    color_primario: Optional[str] = None
    plan: Optional[str] = None
    monto_plan: Optional[float] = None
    fecha_vencimiento_plan: Optional[str] = None  # ISO date string YYYY-MM-DD


class NuevoPagoPayload(BaseModel):
    lavanderia_id: int
    monto: float
    metodo: str  # yappy / nequi / efectivo / transferencia
    periodo_desde: Optional[str] = None  # YYYY-MM-DD
    periodo_hasta: Optional[str] = None  # YYYY-MM-DD
    notas: Optional[str] = None


class ActualizarConfigPayload(BaseModel):
    precio_mensual: Optional[str] = None
    precio_anual: Optional[str] = None
    mensaje_vencimiento_whatsapp: Optional[str] = None
    contacto_nombre: Optional[str] = None
    contacto_telefono: Optional[str] = None


# ── Helpers ────────────────────────────────────────────────────────────────

def _calcular_mrr(lavanderias: list, config: dict) -> float:
    precio_mensual = float(config.get("precio_mensual") or 25)
    precio_anual = float(config.get("precio_anual") or 250)
    mrr = 0.0
    for lav in lavanderias:
        estatus = calcular_estatus_suscripcion(lav)
        if estatus != "activa":
            continue
        plan = lav.get("plan", "mensual")
        if plan == "mensual":
            mrr += precio_mensual
        elif plan == "anual":
            mrr += precio_anual / 12
    return round(mrr, 2)


# ── DASHBOARD SAAS ─────────────────────────────────────────────────────────

@router.get("/dashboard-saas")
async def get_dashboard_saas(_: dict = Depends(_require_superadmin)):
    sb = get_supabase()
    hoy = date.today()
    primer_dia_mes = hoy.replace(day=1).isoformat()
    hace_7 = (hoy - timedelta(days=7)).isoformat()
    hace_30 = (hoy - timedelta(days=30)).isoformat()

    # Todas las lavanderías
    lav_res = sb.table("lavanderias").select("*").execute()
    todas = lav_res.data or []

    # Config de precios
    cfg_res = sb.table("config_saas").select("clave, valor").execute()
    config = {r["clave"]: r["valor"] for r in (cfg_res.data or [])}
    precio_mensual = float(config.get("precio_mensual") or 25)
    precio_anual = float(config.get("precio_anual") or 250)

    total = len(todas)
    activas = inactivas = trial_count = nuevas_mes = 0
    ingresos_estimados = 0.0
    suscripciones = []

    for lav in todas:
        estatus = calcular_estatus_suscripcion(lav)
        lav["_estatus"] = estatus

        if estatus == "activa":
            activas += 1
            plan = lav.get("plan", "mensual")
            if plan == "mensual":
                ingresos_estimados += precio_mensual
            elif plan == "anual":
                ingresos_estimados += precio_anual / 12
        elif estatus == "trial":
            trial_count += 1
        else:
            inactivas += 1

        # Nuevas este mes
        created = lav.get("created_at", "")
        if created and created[:7] == primer_dia_mes[:7]:
            nuevas_mes += 1

        # Fila de suscripción
        venc = lav.get("fecha_vencimiento_plan")
        dias_restantes = None
        if venc:
            try:
                v = datetime.fromisoformat(venc.replace("Z", "+00:00")).date()
                dias_restantes = (v - hoy).days
            except Exception:
                pass

        suscripciones.append({
            "id": lav["id"],
            "nombre": lav["nombre"],
            "plan": lav.get("plan", "—"),
            "fecha_vencimiento": venc[:10] if venc else None,
            "dias_restantes": dias_restantes,
            "estatus": estatus,
            "activo": lav.get("activo", False),
        })

    # Ordenar: más urgentes primero (vencidas o próximas a vencer)
    suscripciones.sort(key=lambda x: (x["dias_restantes"] is None, x["dias_restantes"] if x["dias_restantes"] is not None else 9999))

    # Actividad últimos 7 días
    ord_7d = (
        sb.table("ordenes")
        .select("lavanderia_id, created_at")
        .gte("created_at", f"{hace_7}T00:00:00")
        .execute()
    )
    lav_con_act_7d = {o["lavanderia_id"] for o in (ord_7d.data or []) if o.get("lavanderia_id")}

    # Última actividad en últimos 30 días
    ord_30d = (
        sb.table("ordenes")
        .select("lavanderia_id, created_at")
        .gte("created_at", f"{hace_30}T00:00:00")
        .execute()
    )
    ultima_orden_map: dict = {}
    for o in (ord_30d.data or []):
        lid = o.get("lavanderia_id")
        if lid:
            fecha = (o.get("created_at") or "")[:10]
            if lid not in ultima_orden_map or fecha > ultima_orden_map[lid]:
                ultima_orden_map[lid] = fecha

    sin_actividad_7d = [
        {
            "id": lav["id"],
            "nombre": lav["nombre"],
            "ultima_orden": ultima_orden_map.get(lav["id"]),
        }
        for lav in todas
        if lav.get("activo") and lav["id"] not in lav_con_act_7d
    ]

    # Crecimiento por mes — últimos 6 meses
    meses: dict = {}
    for i in range(5, -1, -1):
        year = hoy.year
        month = hoy.month - i
        while month <= 0:
            month += 12
            year -= 1
        mes_key = f"{year:04d}-{month:02d}"
        meses[mes_key] = 0

    for lav in todas:
        created = (lav.get("created_at") or "")[:7]
        if created in meses:
            meses[created] += 1

    return {
        "total": total,
        "activas": activas,
        "trial": trial_count,
        "inactivas": inactivas,
        "nuevas_mes": nuevas_mes,
        "ingresos_estimados": round(ingresos_estimados, 2),
        "suscripciones": suscripciones,
        "sin_actividad_7d": sin_actividad_7d,
        "crecimiento_meses": [{"mes": k, "count": v} for k, v in meses.items()],
    }


# ── STATS ──────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(_: dict = Depends(_require_superadmin)):
    sb = get_supabase()
    hoy = date.today().isoformat()
    primer_dia_mes = date.today().replace(day=1).isoformat()
    hace_7 = (date.today() - timedelta(days=7)).isoformat()

    # Lavanderías
    lav_res = sb.table("lavanderias").select("*").execute()
    todas = lav_res.data or []

    activas = inactivas = trial_count = 0
    sin_actividad_7d = []
    vencidas_alerta = []

    for lav in todas:
        estatus = calcular_estatus_suscripcion(lav)
        lav["_estatus"] = estatus
        if estatus == "activa":
            activas += 1
        elif estatus == "trial":
            trial_count += 1
        else:
            inactivas += 1

        if estatus in ("vencida", "suspendida"):
            vencidas_alerta.append({"id": lav["id"], "nombre": lav["nombre"], "estatus": estatus})

    # Config (para MRR)
    cfg_res = sb.table("config_saas").select("clave, valor").execute()
    config = {r["clave"]: r["valor"] for r in (cfg_res.data or [])}
    mrr = _calcular_mrr([l for l in todas if l.get("activo")], config)

    # Órdenes hoy
    ord_hoy = (
        sb.table("ordenes")
        .select("id, lavanderia_id")
        .gte("created_at", f"{hoy}T00:00:00")
        .lte("created_at", f"{hoy}T23:59:59")
        .execute()
    )
    ordenes_hoy = ord_hoy.data or []
    total_ordenes_hoy = len(ordenes_hoy)

    # Ventas hoy
    total_ventas_hoy = 0.0
    ids_hoy = [o["id"] for o in ordenes_hoy]
    if ids_hoy:
        v = sb.table("orden_servicios").select("subtotal").in_("orden_id", ids_hoy).execute()
        total_ventas_hoy = sum(float(r.get("subtotal") or 0) for r in (v.data or []))

    # Órdenes mes
    ord_mes = (
        sb.table("ordenes")
        .select("id, lavanderia_id")
        .gte("created_at", f"{primer_dia_mes}T00:00:00")
        .execute()
    )
    ordenes_mes_data = ord_mes.data or []
    total_ordenes_mes = len(ordenes_mes_data)

    # Top 3
    lav_nombres = {l["id"]: l["nombre"] for l in todas}
    conteo: dict = {}
    for o in ordenes_mes_data:
        lid = o.get("lavanderia_id")
        if lid:
            conteo[lid] = conteo.get(lid, 0) + 1
    top3_mes = [
        {"nombre": lav_nombres.get(lid, f"ID {lid}"), "ordenes": cnt}
        for lid, cnt in sorted(conteo.items(), key=lambda x: x[1], reverse=True)[:3]
    ]

    # Sin actividad 7 días
    ord_7d = (
        sb.table("ordenes")
        .select("lavanderia_id")
        .gte("created_at", f"{hace_7}T00:00:00")
        .execute()
    )
    lav_con_actividad = {o["lavanderia_id"] for o in (ord_7d.data or []) if o.get("lavanderia_id")}
    sin_actividad_7d = [
        {"id": l["id"], "nombre": l["nombre"]}
        for l in todas
        if l.get("activo") and l["id"] not in lav_con_actividad
    ]

    return {
        "mrr": mrr,
        "total_activas": activas,
        "total_trial": trial_count,
        "total_inactivas": inactivas,
        "total_ordenes_hoy": total_ordenes_hoy,
        "total_ventas_hoy": round(total_ventas_hoy, 2),
        "total_ordenes_mes": total_ordenes_mes,
        "top3_mes": top3_mes,
        "sin_actividad_7d": sin_actividad_7d,
        "vencidas_alerta": vencidas_alerta,
    }


# ── LAVANDERÍAS ────────────────────────────────────────────────────────────

@router.post("/lavanderias")
async def crear_lavanderia(
    data: NuevaLavanderiaPayload,
    _: dict = Depends(_require_superadmin),
):
    sb = get_supabase()
    password = data.owner_password or _generar_password()
    hoy = datetime.utcnow()

    if data.plan == "trial":
        fecha_venc = (hoy + timedelta(days=data.dias_trial)).isoformat()
    else:
        fecha_venc = (hoy + timedelta(days=30)).isoformat()

    lav_res = (
        sb.table("lavanderias")
        .insert({
            "nombre": data.nombre,
            "telefono": data.telefono,
            "direccion": data.direccion,
            "ciudad": data.ciudad,
            "color_primario": data.color_primario,
            "plan": data.plan,
            "dias_trial": data.dias_trial,
            "fecha_inicio_plan": hoy.isoformat(),
            "fecha_vencimiento_plan": fecha_venc,
            "monto_plan": 0 if data.plan == "trial" else 25,
            "activo": True,
        })
        .execute()
    )
    if not lav_res.data:
        raise HTTPException(status_code=500, detail="Error creando la lavandería")

    lavanderia_id = lav_res.data[0]["id"]

    try:
        auth_res = sb.auth.admin.create_user({
            "email": data.owner_email,
            "password": password,
            "email_confirm": True,
        })
        if not auth_res.user:
            raise Exception("No se obtuvo user de auth")
        user_id = auth_res.user.id
    except Exception as e:
        sb.table("lavanderias").delete().eq("id", lavanderia_id).execute()
        raise HTTPException(status_code=500, detail=f"Error creando usuario Auth: {str(e)}")

    try:
        sb.table("usuarios").insert({
            "id": str(user_id),
            "email": data.owner_email,
            "rol": "owner",
            "lavanderia_id": lavanderia_id,
            "activo": True,
        }).execute()
    except Exception as e:
        try:
            sb.table("lavanderias").delete().eq("id", lavanderia_id).execute()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Error registrando usuario: {str(e)}")

    return {
        "ok": True,
        "lavanderia_id": lavanderia_id,
        "owner_email": data.owner_email,
        "owner_password_temporal": password,
    }


@router.post("/lavanderias/{lavanderia_id}/owner")
async def crear_owner_existente(
    lavanderia_id: int,
    data: NuevoOwnerPayload,
    _: dict = Depends(_require_superadmin),
):
    sb = get_supabase()
    lav_res = sb.table("lavanderias").select("id").eq("id", lavanderia_id).single().execute()
    if not lav_res.data:
        raise HTTPException(status_code=404, detail="Lavandería no encontrada")

    existing = (
        sb.table("usuarios")
        .select("id")
        .eq("lavanderia_id", lavanderia_id)
        .eq("rol", "owner")
        .eq("activo", True)
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=409, detail="Esta lavandería ya tiene un owner activo")

    password = data.owner_password or _generar_password()

    try:
        auth_res = sb.auth.admin.create_user({
            "email": data.owner_email,
            "password": password,
            "email_confirm": True,
        })
        if not auth_res.user:
            raise Exception("No user returned")
        user_id = auth_res.user.id
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error Auth: {str(e)}")

    try:
        sb.table("usuarios").insert({
            "id": str(user_id),
            "email": data.owner_email,
            "rol": "owner",
            "lavanderia_id": lavanderia_id,
            "activo": True,
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error registrando usuario: {str(e)}")

    return {
        "ok": True,
        "lavanderia_id": lavanderia_id,
        "owner_email": data.owner_email,
        "owner_password_temporal": password,
    }


@router.patch("/lavanderias/{lavanderia_id}")
async def actualizar_lavanderia(
    lavanderia_id: int,
    data: ActualizarLavanderiaPayload,
    _: dict = Depends(_require_superadmin),
):
    sb = get_supabase()
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        return {"ok": True}

    if "fecha_vencimiento_plan" in updates:
        # Accept YYYY-MM-DD, store as full ISO
        d = updates["fecha_vencimiento_plan"]
        if len(d) == 10:
            updates["fecha_vencimiento_plan"] = f"{d}T23:59:59+00:00"

    sb.table("lavanderias").update(updates).eq("id", lavanderia_id).execute()
    return {"ok": True}


@router.patch("/lavanderias/{lavanderia_id}/toggle")
async def toggle_lavanderia(
    lavanderia_id: int,
    _: dict = Depends(_require_superadmin),
):
    sb = get_supabase()
    current = (
        sb.table("lavanderias").select("activo").eq("id", lavanderia_id).single().execute()
    )
    if not current.data:
        raise HTTPException(status_code=404, detail="Lavandería no encontrada")

    nuevo_estado = not current.data["activo"]
    sb.table("lavanderias").update({"activo": nuevo_estado}).eq("id", lavanderia_id).execute()
    sb.table("usuarios").update({"activo": nuevo_estado}).eq("lavanderia_id", lavanderia_id).neq("rol", "superadmin").execute()
    return {"ok": True, "activo": nuevo_estado}


@router.delete("/lavanderias/{lavanderia_id}")
async def eliminar_lavanderia(
    lavanderia_id: int,
    _: dict = Depends(_require_superadmin),
):
    sb = get_supabase()
    # Soft delete: desactivar y limpiar owner
    sb.table("lavanderias").update({"activo": False}).eq("id", lavanderia_id).execute()
    sb.table("usuarios").update({"activo": False}).eq("lavanderia_id", lavanderia_id).neq("rol", "superadmin").execute()
    return {"ok": True}


@router.get("/lavanderias/{lavanderia_id}/detalle")
async def get_lavanderia_detalle(
    lavanderia_id: int,
    _: dict = Depends(_require_superadmin),
):
    sb = get_supabase()
    hoy = date.today()
    primer_dia_mes = hoy.replace(day=1).isoformat()

    # Lavandería
    lav_res = sb.table("lavanderias").select("*").eq("id", lavanderia_id).single().execute()
    if not lav_res.data:
        raise HTTPException(status_code=404, detail="Lavandería no encontrada")
    lav = lav_res.data

    # Usuarios (owner + empleados activos)
    usuarios_res = (
        sb.table("usuarios")
        .select("id, email, rol, activo")
        .eq("lavanderia_id", lavanderia_id)
        .eq("activo", True)
        .execute()
    )
    usuarios = usuarios_res.data or []
    owner = next((u for u in usuarios if u["rol"] == "owner"), None)
    empleados_count = sum(1 for u in usuarios if u["rol"] == "employee")

    # Días restantes del plan
    dias_restantes = None
    tiene_deuda = False
    venc_str = lav.get("fecha_vencimiento_plan")
    if venc_str:
        try:
            venc = datetime.fromisoformat(venc_str.replace("Z", "+00:00")).date()
            dias_restantes = (venc - hoy).days
            tiene_deuda = dias_restantes < 0
        except Exception:
            pass

    # Historial de pagos (últimos 5)
    pagos_res = (
        sb.table("pagos_suscripcion")
        .select("*")
        .eq("lavanderia_id", lavanderia_id)
        .order("fecha_pago", desc=True)
        .limit(5)
        .execute()
    )
    pagos = pagos_res.data or []

    # Últimas 3 órdenes
    ordenes_res = (
        sb.table("ordenes")
        .select("id, created_at, estatus")
        .eq("lavanderia_id", lavanderia_id)
        .order("created_at", desc=True)
        .limit(3)
        .execute()
    )
    ultimas_ordenes = ordenes_res.data or []

    # Total órdenes mes actual
    ord_mes_res = (
        sb.table("ordenes")
        .select("id")
        .eq("lavanderia_id", lavanderia_id)
        .gte("created_at", f"{primer_dia_mes}T00:00:00")
        .execute()
    )
    total_ordenes_mes = len(ord_mes_res.data or [])

    return {
        "lavanderia": lav,
        "owner": owner,
        "empleados_count": empleados_count,
        "pagos": pagos,
        "dias_restantes": dias_restantes,
        "tiene_deuda": tiene_deuda,
        "ultimas_ordenes": ultimas_ordenes,
        "total_ordenes_mes": total_ordenes_mes,
    }


# ── FACTURACIÓN ────────────────────────────────────────────────────────────

@router.get("/billing")
async def get_billing(_: dict = Depends(_require_superadmin)):
    sb = get_supabase()
    hoy = date.today()
    primer_dia_mes = hoy.replace(day=1).isoformat()

    # Pagos del mes actual
    pagos_mes_res = (
        sb.table("pagos_suscripcion")
        .select("*")
        .gte("fecha_pago", f"{primer_dia_mes}T00:00:00")
        .order("fecha_pago", desc=True)
        .execute()
    )
    pagos_mes = pagos_mes_res.data or []

    # Historial completo (últimos 60)
    historial_res = (
        sb.table("pagos_suscripcion")
        .select("*, lavanderias(nombre)")
        .order("fecha_pago", desc=True)
        .limit(60)
        .execute()
    )
    # Flatten nested nombre
    historial = []
    for p in (historial_res.data or []):
        row = {**p}
        lav = row.pop("lavanderias", None)
        row["lavanderia_nombre"] = lav["nombre"] if isinstance(lav, dict) else f"ID {row.get('lavanderia_id')}"
        historial.append(row)

    # Lavanderías activas con vencimiento para pendientes
    lavs_res = (
        sb.table("lavanderias")
        .select("id, nombre, plan, monto_plan, fecha_vencimiento_plan, activo, ciudad")
        .eq("activo", True)
        .execute()
    )
    pendientes = []
    for lav in (lavs_res.data or []):
        venc_str = lav.get("fecha_vencimiento_plan")
        if not venc_str:
            continue
        try:
            venc = datetime.fromisoformat(venc_str.replace("Z", "+00:00")).date()
            dias_vencido = (hoy - venc).days
            if dias_vencido >= 0:
                pendientes.append({
                    **lav,
                    "dias_vencido": dias_vencido,
                })
        except Exception:
            pass
    pendientes.sort(key=lambda x: x["dias_vencido"], reverse=True)

    # Nombres para pagos_mes (join manual)
    lav_nombres = {l["id"]: l["nombre"] for l in (lavs_res.data or [])}
    # Fill all lavanderías for complete map
    all_lavs = sb.table("lavanderias").select("id, nombre").execute()
    for l in (all_lavs.data or []):
        lav_nombres[l["id"]] = l["nombre"]

    for p in pagos_mes:
        p["lavanderia_nombre"] = lav_nombres.get(p.get("lavanderia_id"), "—")

    total_cobrado = round(sum(float(p.get("monto") or 0) for p in pagos_mes), 2)
    total_pendiente = round(sum(float(p.get("monto_plan") or 0) for p in pendientes), 2)

    return {
        "total_cobrado_mes": total_cobrado,
        "total_pendiente": total_pendiente,
        "pagos_mes": pagos_mes,
        "pendientes": pendientes,
        "historial": historial,
    }


@router.post("/billing/pago")
async def registrar_pago(
    data: NuevoPagoPayload,
    _: dict = Depends(_require_superadmin),
):
    sb = get_supabase()

    pago_res = sb.table("pagos_suscripcion").insert({
        "lavanderia_id": data.lavanderia_id,
        "monto": data.monto,
        "metodo": data.metodo,
        "fecha_pago": datetime.utcnow().isoformat(),
        "periodo_desde": data.periodo_desde,
        "periodo_hasta": data.periodo_hasta,
        "notas": data.notas,
    }).execute()

    # Extender vencimiento si se especificó periodo_hasta
    if data.periodo_hasta:
        sb.table("lavanderias").update({
            "fecha_vencimiento_plan": f"{data.periodo_hasta}T23:59:59+00:00",
            "activo": True,
            "monto_plan": data.monto,
        }).eq("id", data.lavanderia_id).execute()
        # Reactivar usuarios de esa lavandería
        sb.table("usuarios").update({"activo": True}).eq("lavanderia_id", data.lavanderia_id).neq("rol", "superadmin").execute()

    return {"ok": True, "pago": pago_res.data[0] if pago_res.data else {}}


# ── CONFIGURACIÓN ──────────────────────────────────────────────────────────

@router.get("/config")
async def get_config(_: dict = Depends(_require_superadmin)):
    sb = get_supabase()
    rows = sb.table("config_saas").select("clave, valor").execute()
    return {r["clave"]: r["valor"] for r in (rows.data or [])}


@router.patch("/config")
async def update_config(
    data: ActualizarConfigPayload,
    _: dict = Depends(_require_superadmin),
):
    sb = get_supabase()
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    for clave, valor in updates.items():
        sb.table("config_saas").upsert(
            {"clave": clave, "valor": str(valor)},
            on_conflict="clave",
        ).execute()
    return {"ok": True}


# ── NOTIFICACIONES WHATSAPP ────────────────────────────────────────────────

@router.post("/notificar-vencimientos")
async def notificar_vencimientos(_: dict = Depends(_require_superadmin)):
    from app.services.whatsapp import enviar_recordatorio_vencimiento

    sb = get_supabase()
    hoy = date.today()
    en_3_dias = hoy + timedelta(days=3)

    # Template desde config
    cfg = sb.table("config_saas").select("clave, valor").execute()
    config = {r["clave"]: r["valor"] for r in (cfg.data or [])}
    template = config.get(
        "mensaje_vencimiento_whatsapp",
        "Hola {nombre}, tu suscripción de {lavanderia} vence en {dias} días.",
    )

    # Lavanderías que vencen en ~3 días
    desde = f"{(en_3_dias - timedelta(days=1)).isoformat()}T00:00:00"
    hasta = f"{(en_3_dias + timedelta(days=1)).isoformat()}T23:59:59"

    lavs_res = (
        sb.table("lavanderias")
        .select("id, nombre, telefono, fecha_vencimiento_plan")
        .gte("fecha_vencimiento_plan", desde)
        .lte("fecha_vencimiento_plan", hasta)
        .eq("activo", True)
        .execute()
    )

    resultados = []
    for lav in (lavs_res.data or []):
        telefono = lav.get("telefono")
        if not telefono:
            resultados.append({"lavanderia": lav["nombre"], "status": "sin_telefono"})
            continue
        try:
            venc = datetime.fromisoformat(lav["fecha_vencimiento_plan"].replace("Z", "+00:00")).date()
            dias = (venc - hoy).days
        except Exception:
            dias = 3

        res = await enviar_recordatorio_vencimiento(telefono, lav["nombre"], dias, template)
        resultados.append({"lavanderia": lav["nombre"], **res})

    return {"ok": True, "notificados": len(lavs_res.data or []), "resultados": resultados}


# ── IMPERSONACIÓN ──────────────────────────────────────────────────────────

@router.post("/impersonate/stop")
async def detener_impersonacion():
    resp = RedirectResponse("/admin", status_code=302)
    resp.delete_cookie("impersonate_lavanderia_id")
    return resp


@router.post("/impersonate/{lavanderia_id}")
async def iniciar_impersonacion(
    lavanderia_id: int,
    _: dict = Depends(_require_superadmin),
):
    sb = get_supabase()
    owner_res = (
        sb.table("usuarios")
        .select("id")
        .eq("lavanderia_id", lavanderia_id)
        .eq("rol", "owner")
        .eq("activo", True)
        .limit(1)
        .execute()
    )
    if not owner_res.data:
        raise HTTPException(status_code=404, detail="No hay owner activo en esta lavandería")

    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie(
        key="impersonate_lavanderia_id",
        value=str(lavanderia_id),
        httponly=True,
        samesite="lax",
        max_age=60 * 60,
    )
    return resp

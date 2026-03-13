from datetime import date

from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import ordenes, clientes, dashboard, servicios, reportes, sastreria
from app.routers import auth as auth_router
from app.routers import admin as admin_router
from app.routers import busqueda as busqueda_router
from app.routers import caja as caja_router
from app.config import get_lavanderia_data, get_supabase_with_token
from app.utils import calcular_estatus_suscripcion

app = FastAPI(title="Lavandería SaaS", version="1.0.0")

# Static files y templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Routers de la API
app.include_router(ordenes.router, prefix="/api/ordenes", tags=["ordenes"])
app.include_router(clientes.router, prefix="/api/clientes", tags=["clientes"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(servicios.router, prefix="/api/servicios", tags=["servicios"])
app.include_router(reportes.router, prefix="/api/reportes", tags=["reportes"])
app.include_router(sastreria.router, prefix="/api/sastreria", tags=["sastreria"])
app.include_router(auth_router.router)
app.include_router(admin_router.router)
app.include_router(busqueda_router.router, prefix="/api/busqueda", tags=["busqueda"])
app.include_router(caja_router.router, prefix="/api/caja", tags=["caja"])


# ── Excepciones de autenticación ──────────────────────────────────────────────

class AuthError(Exception):
    def __init__(self, redirect_to: str = "/login"):
        self.redirect_to = redirect_to


@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError):
    return RedirectResponse(exc.redirect_to, status_code=302)


# ── Dependencias de autenticación ─────────────────────────────────────────────

async def get_current_user(request: Request) -> dict:
    """Verifica el token JWT y devuelve los datos del usuario o redirige a /login.
    Si el superadmin tiene una cookie de impersonación activa, retorna los datos
    del owner impersonado para que pueda dar soporte en contexto."""
    token = request.cookies.get("access_token")
    if not token:
        raise AuthError("/login")
    try:
        sb = get_supabase_with_token(token)
        user_resp = sb.auth.get_user(token)
        if not user_resp.user:
            raise AuthError("/login")

        user_id = user_resp.user.id
        result = (
            sb.table("usuarios")
            .select("id, email, rol, lavanderia_id, activo")
            .eq("id", user_id)
            .eq("activo", True)
            .single()
            .execute()
        )
        if not result.data:
            raise AuthError("/login")

        user = result.data

        # Impersonación: solo disponible para superadmin
        impersonate_id = request.cookies.get("impersonate_lavanderia_id")
        if user["rol"] == "superadmin" and impersonate_id:
            try:
                from app.config import get_supabase
                sb_admin = get_supabase()
                lavanderia_id = int(impersonate_id)
                owner_res = (
                    sb_admin.table("usuarios")
                    .select("id, email, rol, lavanderia_id, activo")
                    .eq("lavanderia_id", lavanderia_id)
                    .eq("rol", "owner")
                    .eq("activo", True)
                    .limit(1)
                    .execute()
                )
                if owner_res.data:
                    impersonated = dict(owner_res.data[0])
                    impersonated["_impersonando"] = True
                    impersonated["_superadmin_email"] = user["email"]
                    impersonated["_impersonate_lavanderia_id"] = lavanderia_id
                    return impersonated
            except Exception:
                pass

        return user
    except AuthError:
        raise
    except Exception:
        raise AuthError("/login")


async def require_owner(user: dict = Depends(get_current_user)) -> dict:
    """Requiere rol owner o superadmin. Employee es redirigido al inicio."""
    if user["rol"] == "employee":
        raise AuthError("/")
    return user


async def require_superadmin(user: dict = Depends(get_current_user)) -> dict:
    """Requiere rol superadmin."""
    if user["rol"] != "superadmin":
        raise AuthError("/")
    return user


# ── Páginas HTML ──────────────────────────────────────────────────────────────

@app.get("/login")
async def pagina_login(request: Request):
    # Si ya tiene sesión válida, redirigir al inicio
    token = request.cookies.get("access_token")
    if token:
        try:
            sb = get_supabase_with_token(token)
            user_resp = sb.auth.get_user(token)
            if user_resp.user:
                result = (
                    sb.table("usuarios")
                    .select("rol")
                    .eq("id", user_resp.user.id)
                    .eq("activo", True)
                    .single()
                    .execute()
                )
                if result.data:
                    dest = "/admin" if result.data["rol"] == "superadmin" else "/"
                    return RedirectResponse(dest, status_code=302)
        except Exception:
            pass

    error = request.query_params.get("error")
    error_msg = None
    if error == "1":
        error_msg = "Credenciales incorrectas. Intenta de nuevo."
    elif error == "2":
        error_msg = "Usuario inactivo o sin acceso."

    return templates.TemplateResponse("pages/login.html", {
        "request": request,
        "error_msg": error_msg,
    })


@app.get("/admin")
async def pagina_admin(request: Request, user: dict = Depends(require_superadmin)):
    try:
        from app.config import get_supabase
        sb = get_supabase()

        lavanderias_res = sb.table("lavanderias").select("*").order("id").execute()
        lista = lavanderias_res.data or []

        # Órdenes del mes por lavandería
        primer_dia_mes = date.today().replace(day=1).isoformat()
        ord_mes = (
            sb.table("ordenes")
            .select("lavanderia_id")
            .gte("created_at", f"{primer_dia_mes}T00:00:00")
            .execute()
        )
        conteo_ordenes: dict = {}
        for o in (ord_mes.data or []):
            lid = o.get("lavanderia_id")
            if lid:
                conteo_ordenes[lid] = conteo_ordenes.get(lid, 0) + 1

        # Owner por lavandería
        owners_res = (
            sb.table("usuarios")
            .select("lavanderia_id, email")
            .eq("rol", "owner")
            .eq("activo", True)
            .execute()
        )
        owner_map = {o["lavanderia_id"]: o["email"] for o in (owners_res.data or [])}

        for lav in lista:
            lav["owner_email"] = owner_map.get(lav["id"])
            lav["ordenes_mes"] = conteo_ordenes.get(lav["id"], 0)
            lav["estatus_suscripcion"] = calcular_estatus_suscripcion(lav)

    except Exception:
        lista = []

    return templates.TemplateResponse("pages/admin.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
        "current_user": user,
        "lavanderias": lista,
    })


@app.get("/")
async def pagina_ordenes(request: Request, user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("pages/ordenes.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
        "current_user": user,
    })


@app.get("/nueva-orden")
async def pagina_nueva_orden(request: Request, user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("pages/nueva_orden.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
        "current_user": user,
    })


@app.get("/clientes")
async def pagina_clientes(request: Request, user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("pages/clientes.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
        "current_user": user,
    })


@app.get("/clientes/{cliente_id}")
async def pagina_perfil_cliente(
    request: Request,
    cliente_id: int,
    user: dict = Depends(require_owner),
):
    return templates.TemplateResponse("pages/perfil_cliente.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
        "current_user": user,
        "cliente_id": cliente_id,
    })


@app.get("/servicios")
async def pagina_servicios(request: Request, user: dict = Depends(require_owner)):
    return templates.TemplateResponse("pages/servicios.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
        "current_user": user,
    })


@app.get("/dashboard")
async def pagina_dashboard(request: Request, user: dict = Depends(require_owner)):
    return templates.TemplateResponse("pages/dashboard.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
        "current_user": user,
    })


@app.get("/deudas")
async def pagina_deudas(request: Request, user: dict = Depends(require_owner)):
    return templates.TemplateResponse("pages/deudas.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
        "current_user": user,
    })


@app.get("/sastreria")
async def pagina_sastreria(request: Request, user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("pages/sastreria.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
        "current_user": user,
    })


@app.get("/sastreria/nueva")
async def pagina_nueva_sastreria(request: Request, user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("pages/nueva_sastreria.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
        "current_user": user,
    })


@app.get("/caja")
async def pagina_caja(request: Request, user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("pages/caja.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
        "current_user": user,
    })


@app.get("/orden/{orden_id}/etiqueta")
async def pagina_etiqueta(
    request: Request,
    orden_id: int,
    user: dict = Depends(get_current_user),
):
    return templates.TemplateResponse("pages/etiqueta.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
        "current_user": user,
        "orden_id": orden_id,
        "orden_id_str": str(orden_id).zfill(4),
    })

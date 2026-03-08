from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import ordenes, clientes, dashboard, servicios, reportes, sastreria
from app.config import get_lavanderia_data

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


# ---- Páginas HTML ----

@app.get("/")
async def pagina_ordenes(request: Request):
    return templates.TemplateResponse("pages/ordenes.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
    })


@app.get("/nueva-orden")
async def pagina_nueva_orden(request: Request):
    return templates.TemplateResponse("pages/nueva_orden.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
    })


@app.get("/clientes")
async def pagina_clientes(request: Request):
    return templates.TemplateResponse("pages/clientes.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
    })


@app.get("/clientes/{cliente_id}")
async def pagina_perfil_cliente(request: Request, cliente_id: int):
    return templates.TemplateResponse("pages/perfil_cliente.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
        "cliente_id": cliente_id,
    })


@app.get("/servicios")
async def pagina_servicios(request: Request):
    return templates.TemplateResponse("pages/servicios.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
    })


@app.get("/dashboard")
async def pagina_dashboard(request: Request):
    return templates.TemplateResponse("pages/dashboard.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
    })


@app.get("/deudas")
async def pagina_deudas(request: Request):
    return templates.TemplateResponse("pages/deudas.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
    })


@app.get("/sastreria")
async def pagina_sastreria(request: Request):
    return templates.TemplateResponse("pages/sastreria.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
    })


@app.get("/sastreria/nueva")
async def pagina_nueva_sastreria(request: Request):
    return templates.TemplateResponse("pages/nueva_sastreria.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
    })


@app.get("/orden/{orden_id}/etiqueta")
async def pagina_etiqueta(request: Request, orden_id: int):
    return templates.TemplateResponse("pages/etiqueta.html", {
        "request": request,
        "lavanderia": get_lavanderia_data(),
        "orden_id": orden_id,
        "orden_id_str": str(orden_id).zfill(4),
    })

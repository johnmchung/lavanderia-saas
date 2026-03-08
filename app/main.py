from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import ordenes, clientes, dashboard, servicios
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

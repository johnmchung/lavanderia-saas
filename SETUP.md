# Lavandería SaaS - Guía de Setup

## Requisitos
- Python 3.10+
- Cuenta gratuita en Supabase (https://supabase.com)

## Paso 1: Instalar dependencias
```bash
cd lavanderia-saas
pip install -r requirements.txt
```

## Paso 2: Crear proyecto en Supabase
1. Ve a https://supabase.com y crea un proyecto gratuito
2. Ve a SQL Editor y pega todo el contenido de `sql/schema.sql`
3. Ejecuta el SQL
4. Ve a Settings → API y copia tu URL y anon key

## Paso 3: Configurar variables de entorno
```bash
cp .env.example .env
```
Edita `.env` con tu URL y key de Supabase.
Para WhatsApp, déjalo vacío por ahora (funcionará en modo mock).

## Paso 4: Correr la app
```bash
python run.py
```
Abre http://localhost:8000 en tu celular o navegador.

## Estructura del proyecto
```
lavanderia-saas/
├── app/
│   ├── main.py              ← App principal FastAPI
│   ├── config.py             ← Configuración y Supabase
│   ├── routers/
│   │   ├── ordenes.py        ← API de órdenes (CRUD + estatus)
│   │   ├── clientes.py       ← API de clientes
│   │   └── dashboard.py      ← API del dashboard
│   ├── services/
│   │   └── whatsapp.py       ← Notificaciones WhatsApp
│   └── templates/
│       ├── base.html          ← Layout con nav inferior
│       └── pages/
│           ├── ordenes.html   ← Lista de órdenes
│           ├── nueva_orden.html ← Formulario nueva orden
│           └── dashboard.html  ← Resumen del día
├── sql/
│   └── schema.sql            ← Esquema de base de datos
├── .env.example
├── requirements.txt
└── run.py                    ← Punto de entrada
```

## API Endpoints
- `GET  /api/ordenes/` - Listar órdenes (filtrar por ?estatus=X&fecha=YYYY-MM-DD)
- `POST /api/ordenes/` - Crear orden
- `GET  /api/ordenes/{id}` - Detalle de orden
- `PATCH /api/ordenes/{id}/estatus` - Cambiar estatus (envía WhatsApp si → listo)
- `POST /api/ordenes/{id}/pagos` - Registrar pago
- `GET  /api/clientes/` - Listar/buscar clientes
- `POST /api/clientes/` - Crear cliente
- `GET  /api/dashboard/hoy` - Resumen del día

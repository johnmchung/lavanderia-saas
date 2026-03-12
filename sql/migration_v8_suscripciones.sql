-- ============================================================
-- Migration v8: Suscripciones y facturación SaaS
-- Ejecutar en Supabase SQL Editor
-- ============================================================

-- ── 1. Nuevas columnas en lavanderias ─────────────────────────────────────
ALTER TABLE lavanderias
    ADD COLUMN IF NOT EXISTS plan                  VARCHAR(20)     NOT NULL DEFAULT 'mensual'
        CHECK (plan IN ('trial', 'mensual', 'anual')),
    ADD COLUMN IF NOT EXISTS ciudad                VARCHAR(100),
    ADD COLUMN IF NOT EXISTS fecha_inicio_plan     TIMESTAMPTZ     DEFAULT now(),
    ADD COLUMN IF NOT EXISTS fecha_vencimiento_plan TIMESTAMPTZ    DEFAULT (now() + INTERVAL '30 days'),
    ADD COLUMN IF NOT EXISTS dias_trial            INTEGER         NOT NULL DEFAULT 14,
    ADD COLUMN IF NOT EXISTS monto_plan            DECIMAL(10,2)   DEFAULT 25.00;

-- Dar a lavanderías existentes un mes de gracia
UPDATE lavanderias
SET fecha_inicio_plan      = COALESCE(fecha_inicio_plan, created_at, now()),
    fecha_vencimiento_plan = COALESCE(fecha_vencimiento_plan, now() + INTERVAL '30 days')
WHERE fecha_vencimiento_plan IS NULL;


-- ── 2. Tabla pagos_suscripcion ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pagos_suscripcion (
    id             SERIAL      PRIMARY KEY,
    lavanderia_id  INTEGER     NOT NULL REFERENCES lavanderias(id) ON DELETE CASCADE,
    monto          DECIMAL(10,2) NOT NULL,
    metodo         VARCHAR(30) NOT NULL
        CHECK (metodo IN ('yappy', 'nequi', 'efectivo', 'transferencia')),
    fecha_pago     TIMESTAMPTZ NOT NULL DEFAULT now(),
    periodo_desde  DATE,
    periodo_hasta  DATE,
    notas          TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS pagos_suscripcion_lavanderia_idx ON pagos_suscripcion(lavanderia_id);
CREATE INDEX IF NOT EXISTS pagos_suscripcion_fecha_idx      ON pagos_suscripcion(fecha_pago DESC);


-- ── 3. Tabla config_saas ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS config_saas (
    id         SERIAL      PRIMARY KEY,
    clave      VARCHAR(100) UNIQUE NOT NULL,
    valor      TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Valores por defecto
INSERT INTO config_saas (clave, valor) VALUES
    ('precio_mensual',                 '25.00'),
    ('precio_anual',                   '250.00'),
    ('mensaje_vencimiento_whatsapp',
     'Hola {nombre}, tu suscripción de {lavanderia} vence en {dias} días. Contáctanos para renovar y seguir sin interrupciones.'),
    ('contacto_nombre',   'Soporte SaaS'),
    ('contacto_telefono', '')
ON CONFLICT (clave) DO NOTHING;

-- ============================================
-- Lavandería SaaS - Esquema de Base de Datos
-- Ejecutar en Supabase SQL Editor
-- ============================================

-- Tabla de lavanderías (multi-tenant)
CREATE TABLE lavanderias (
    id BIGSERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    logo_url TEXT,
    color_primario VARCHAR(20) DEFAULT '#16a34a',
    telefono VARCHAR(20),
    direccion TEXT,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insertar lavandería inicial
INSERT INTO lavanderias (nombre, color_primario) VALUES ('ECO PRETTY', '#16a34a');

-- Tabla de clientes
CREATE TABLE clientes (
    id BIGSERIAL PRIMARY KEY,
    lavanderia_id BIGINT REFERENCES lavanderias(id),
    nombre VARCHAR(100) NOT NULL,
    telefono VARCHAR(20) NOT NULL,  -- formato: +507XXXXXXXX
    direccion TEXT,                   -- para domicilios
    notas TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índice para búsqueda rápida por teléfono
CREATE INDEX idx_clientes_telefono ON clientes(telefono);

-- Catálogo de servicios con precios
CREATE TABLE servicios (
    id BIGSERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    precio_por_kilo DECIMAL(10,2) NOT NULL,   -- precio (por kilo o fijo según tipo_precio)
    tipo_precio VARCHAR(10) DEFAULT 'por_kilo'
        CHECK (tipo_precio IN ('por_kilo', 'fijo')),
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insertar servicios iniciales
INSERT INTO servicios (nombre, precio_por_kilo, tipo_precio) VALUES
    ('Lavado', 3.00, 'por_kilo'),
    ('Secado', 2.00, 'por_kilo'),
    ('Doblado', 1.50, 'por_kilo'),
    ('Lavado + Secado', 4.50, 'por_kilo'),
    ('Lavado + Secado + Doblado', 6.00, 'por_kilo');

-- Tabla de órdenes
CREATE TABLE ordenes (
    id BIGSERIAL PRIMARY KEY,
    lavanderia_id BIGINT REFERENCES lavanderias(id),
    cliente_id BIGINT NOT NULL REFERENCES clientes(id),
    kilos DECIMAL(10,2) NOT NULL,
    es_domicilio BOOLEAN DEFAULT FALSE,
    direccion_entrega TEXT,            -- si es domicilio
    estatus VARCHAR(20) DEFAULT 'recibido'
        CHECK (estatus IN ('recibido', 'en_proceso', 'listo', 'entregado')),
    notas TEXT,
    notas_internas TEXT,               -- solo visible para el staff
    fecha_entrega_estimada TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_clientes_lavanderia ON clientes(lavanderia_id);
CREATE INDEX idx_ordenes_estatus ON ordenes(estatus);
CREATE INDEX idx_ordenes_cliente ON ordenes(cliente_id);
CREATE INDEX idx_ordenes_fecha ON ordenes(created_at);
CREATE INDEX idx_ordenes_lavanderia ON ordenes(lavanderia_id);

-- Servicios incluidos en cada orden (una orden puede tener varios servicios)
CREATE TABLE orden_servicios (
    id BIGSERIAL PRIMARY KEY,
    orden_id BIGINT NOT NULL REFERENCES ordenes(id) ON DELETE CASCADE,
    servicio_id BIGINT NOT NULL REFERENCES servicios(id),
    precio_por_kilo DECIMAL(10,2) NOT NULL,  -- precio snapshot al momento de la orden
    tipo_precio VARCHAR(10) DEFAULT 'por_kilo', -- snapshot del tipo al momento de la orden
    subtotal DECIMAL(10,2) NOT NULL           -- monto real cobrado por este servicio
);

CREATE INDEX idx_orden_servicios_orden ON orden_servicios(orden_id);

-- Tabla de pagos
CREATE TABLE pagos (
    id BIGSERIAL PRIMARY KEY,
    orden_id BIGINT NOT NULL REFERENCES ordenes(id),
    monto DECIMAL(10,2) NOT NULL,
    metodo VARCHAR(20) NOT NULL
        CHECK (metodo IN ('yappy', 'nequi', 'efectivo', 'otro')),
    notas TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pagos_orden ON pagos(orden_id);

-- Vista útil: resumen de orden con total calculado
CREATE VIEW vista_ordenes AS
SELECT
    o.id,
    o.cliente_id,
    c.nombre AS cliente_nombre,
    c.telefono AS cliente_telefono,
    o.kilos,
    o.es_domicilio,
    o.direccion_entrega,
    o.estatus,
    o.notas,
    o.notas_internas,
    o.fecha_entrega_estimada,
    o.created_at,
    o.updated_at,
    COALESCE(SUM(os.subtotal), 0) AS precio_total,
    COALESCE(SUM(p.monto), 0) AS total_pagado,
    COALESCE(SUM(os.subtotal), 0) - COALESCE(SUM(p.monto), 0) AS saldo_pendiente,
    STRING_AGG(DISTINCT s.nombre, ', ') AS servicios
FROM ordenes o
JOIN clientes c ON o.cliente_id = c.id
LEFT JOIN orden_servicios os ON o.id = os.orden_id
LEFT JOIN servicios s ON os.servicio_id = s.id
LEFT JOIN pagos p ON o.id = p.orden_id
GROUP BY o.id, c.nombre, c.telefono;

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_ordenes_updated
    BEFORE UPDATE ON ordenes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Tabla de sastrería
CREATE TABLE sastreria (
    id BIGSERIAL PRIMARY KEY,
    lavanderia_id BIGINT REFERENCES lavanderias(id),
    cliente_id BIGINT NOT NULL REFERENCES clientes(id),
    descripcion TEXT NOT NULL,
    tipo_trabajo VARCHAR(20) NOT NULL
        CHECK (tipo_trabajo IN ('ruedo', 'zipper', 'boton', 'otro')),
    prenda VARCHAR(100) NOT NULL,
    precio DECIMAL(10,2) NOT NULL,
    estatus VARCHAR(20) DEFAULT 'recibido'
        CHECK (estatus IN ('recibido', 'en_proceso', 'listo', 'entregado')),
    fecha_entrega_estimada TIMESTAMPTZ,
    notas TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sastreria_estatus ON sastreria(estatus);
CREATE INDEX idx_sastreria_cliente ON sastreria(cliente_id);
CREATE INDEX idx_sastreria_lavanderia ON sastreria(lavanderia_id);
CREATE INDEX idx_sastreria_fecha ON sastreria(created_at);

CREATE TRIGGER trigger_sastreria_updated
    BEFORE UPDATE ON sastreria
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

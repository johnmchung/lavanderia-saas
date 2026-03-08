-- ============================================
-- Migración v3: Multi-tenant básico
-- Agrega tabla lavanderias y lavanderia_id a
-- clientes y ordenes
-- ============================================

-- 1. Crear tabla de lavanderías
CREATE TABLE IF NOT EXISTS lavanderias (
    id BIGSERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    logo_url TEXT,
    color_primario VARCHAR(20) DEFAULT '#16a34a',
    telefono VARCHAR(20),
    direccion TEXT,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Insertar la lavandería actual como primer registro
--    Ajusta el nombre si es diferente a "ECO PRETTY"
INSERT INTO lavanderias (id, nombre, color_primario)
VALUES (1, 'ECO PRETTY', '#16a34a')
ON CONFLICT (id) DO NOTHING;

-- Resetear la secuencia para que el siguiente id auto sea 2
SELECT setval('lavanderias_id_seq', 1);

-- 3. Agregar lavanderia_id a clientes (nullable para retrocompatibilidad)
ALTER TABLE clientes
    ADD COLUMN IF NOT EXISTS lavanderia_id BIGINT REFERENCES lavanderias(id);

-- 4. Asignar lavanderia_id=1 a todos los clientes existentes
UPDATE clientes SET lavanderia_id = 1 WHERE lavanderia_id IS NULL;

-- 5. Agregar lavanderia_id a ordenes (nullable para retrocompatibilidad)
ALTER TABLE ordenes
    ADD COLUMN IF NOT EXISTS lavanderia_id BIGINT REFERENCES lavanderias(id);

-- 6. Asignar lavanderia_id=1 a todas las órdenes existentes
UPDATE ordenes SET lavanderia_id = 1 WHERE lavanderia_id IS NULL;

-- 7. Índices para filtrado por lavandería
CREATE INDEX IF NOT EXISTS idx_clientes_lavanderia ON clientes(lavanderia_id);
CREATE INDEX IF NOT EXISTS idx_ordenes_lavanderia ON ordenes(lavanderia_id);

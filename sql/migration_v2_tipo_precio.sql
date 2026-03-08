-- ============================================
-- Migración v2: soporte precio fijo y por kilo
-- Ejecutar en Supabase SQL Editor
-- ============================================

-- 1. Agregar columna tipo_precio a servicios
ALTER TABLE servicios
    ADD COLUMN IF NOT EXISTS tipo_precio VARCHAR(10) DEFAULT 'por_kilo'
        CHECK (tipo_precio IN ('por_kilo', 'fijo'));

-- 2. Asegurarse de que los servicios existentes tengan tipo_precio
UPDATE servicios SET tipo_precio = 'por_kilo' WHERE tipo_precio IS NULL;

-- 3. Agregar snapshot de tipo_precio en orden_servicios (para historial exacto)
ALTER TABLE orden_servicios
    ADD COLUMN IF NOT EXISTS tipo_precio VARCHAR(10) DEFAULT 'por_kilo';

-- Poblar el historial con 'por_kilo' para órdenes anteriores
UPDATE orden_servicios SET tipo_precio = 'por_kilo' WHERE tipo_precio IS NULL;

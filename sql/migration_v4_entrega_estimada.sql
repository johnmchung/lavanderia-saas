-- ============================================
-- Migración v4: Fecha de entrega estimada
-- Agrega campo fecha_entrega_estimada a ordenes
-- y actualiza la vista vista_ordenes
-- ============================================

-- 1. Agregar columna a la tabla ordenes
ALTER TABLE ordenes
    ADD COLUMN IF NOT EXISTS fecha_entrega_estimada TIMESTAMPTZ;

-- 2. Recrear la vista para incluir el nuevo campo
CREATE OR REPLACE VIEW vista_ordenes AS
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

-- ============================================
-- Migration v6: Módulo de Sastrería
-- Ejecutar en Supabase SQL Editor
-- ============================================

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

-- Reutiliza la función update_updated_at() ya existente
CREATE TRIGGER trigger_sastreria_updated
    BEFORE UPDATE ON sastreria
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

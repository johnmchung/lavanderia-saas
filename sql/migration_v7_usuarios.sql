-- ============================================================
-- Migration v7: Sistema de autenticación — tabla de usuarios
-- Ejecutar en Supabase SQL Editor
-- ============================================================

-- Tabla usuarios (vinculada a Supabase Auth)
CREATE TABLE IF NOT EXISTS usuarios (
    id            UUID        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email         TEXT        NOT NULL,
    rol           TEXT        NOT NULL CHECK (rol IN ('superadmin', 'owner', 'employee')),
    lavanderia_id INT         REFERENCES lavanderias(id),
    activo        BOOLEAN     NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RLS
ALTER TABLE usuarios ENABLE ROW LEVEL SECURITY;

-- Cada usuario puede leer su propio registro
CREATE POLICY "usuarios_self_select" ON usuarios
    FOR SELECT USING (auth.uid() = id);

-- ============================================================
-- Para crear el primer superadmin, hazlo desde Supabase:
--
-- 1. En Authentication > Users, crear el usuario con email/pass
-- 2. Copiar el UUID generado
-- 3. Ejecutar:
--
--   INSERT INTO usuarios (id, email, rol, lavanderia_id)
--   VALUES ('uuid-del-auth-user', 'admin@ejemplo.com', 'superadmin', NULL);
--
-- Para un owner:
--   INSERT INTO usuarios (id, email, rol, lavanderia_id)
--   VALUES ('uuid-del-auth-user', 'owner@ejemplo.com', 'owner', 1);
--
-- Para un employee:
--   INSERT INTO usuarios (id, email, rol, lavanderia_id)
--   VALUES ('uuid-del-auth-user', 'empleado@ejemplo.com', 'employee', 1);
-- ============================================================

from datetime import date, datetime, timedelta


def calcular_estatus_suscripcion(lav: dict) -> str:
    """
    Devuelve: 'trial' | 'activa' | 'vencida' | 'suspendida'

    Lógica:
    - Si plan=trial y fecha_inicio + dias_trial > hoy  → trial
    - Si fecha_vencimiento > hoy                       → activa
    - Si hoy - 7 < fecha_vencimiento <= hoy            → vencida
    - Si fecha_vencimiento <= hoy - 7                  → suspendida
    """
    plan = lav.get("plan") or "mensual"
    venc_str = lav.get("fecha_vencimiento_plan")
    inicio_str = lav.get("fecha_inicio_plan")
    dias_trial = lav.get("dias_trial") or 14
    hoy = date.today()

    if plan == "trial" and inicio_str:
        try:
            inicio = datetime.fromisoformat(inicio_str.replace("Z", "+00:00")).date()
            fin_trial = inicio + timedelta(days=dias_trial)
            if fin_trial > hoy:
                return "trial"
            # Trial expirado sin pago → usar fin_trial como vencimiento
            if not venc_str:
                delta = (hoy - fin_trial).days
                return "vencida" if delta <= 7 else "suspendida"
        except Exception:
            pass

    if not venc_str:
        return "activa"  # Legado sin fecha → considerar activa

    try:
        venc = datetime.fromisoformat(venc_str.replace("Z", "+00:00")).date()
        if venc > hoy:
            return "activa"
        elif venc > hoy - timedelta(days=7):
            return "vencida"
        else:
            return "suspendida"
    except Exception:
        return "activa"

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from app.config import get_supabase, get_supabase_with_token

router = APIRouter(tags=["auth"])


@router.post("/login")
async def do_login(
    email: str = Form(...),
    password: str = Form(...),
):
    print(f"[DEBUG LOGIN] email recibido: {email}")
    try:
        sb = get_supabase()
        response = sb.auth.sign_in_with_password({"email": email, "password": password})

        if not response.session:
            print(f"[DEBUG LOGIN] sin sesión — response completo: {response}")
            return RedirectResponse("/login?error=1", status_code=302)

        token = response.session.access_token
        user_id = response.user.id
        print(f"[DEBUG LOGIN] auth OK — user_id: {user_id}")

        # Obtener rol desde la tabla usuarios (usa JWT del usuario → RLS)
        sb_auth = get_supabase_with_token(token)
        result = (
            sb_auth.table("usuarios")
            .select("rol")
            .eq("id", user_id)
            .eq("activo", True)
            .single()
            .execute()
        )

        print(f"[DEBUG LOGIN] usuarios query result: {result.data}")

        if not result.data:
            return RedirectResponse("/login?error=2", status_code=302)

        rol = result.data["rol"]
        redirect_url = "/admin" if rol == "superadmin" else "/"

        resp = RedirectResponse(redirect_url, status_code=302)
        resp.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 7,  # 7 días
        )
        return resp

    except Exception as e:
        print(f"[DEBUG LOGIN] excepción: {type(e).__name__}: {e}")
        return RedirectResponse("/login?error=1", status_code=302)


@router.post("/logout")
async def do_logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie("access_token")
    return resp

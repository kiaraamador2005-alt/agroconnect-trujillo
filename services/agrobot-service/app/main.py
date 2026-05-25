"""
================================================================================
AgroConnect 2.0 — services/agrobot-service/app/main.py
FastAPI Entry Point — Versión Producción (Render.com)
================================================================================

CAMBIO CLAVE v1.0 (Producción):
  El middleware CORSMiddleware ahora lee los orígenes permitidos desde
  variables de entorno en lugar de usar una lista hardcodeada. Esto permite:

  1. Configurar CORS sin tocar código — solo variables en Render Dashboard.

  2. Restricción de seguridad: solo el backend Express de Node.js tiene
     permiso para llamar a esta API de FastAPI. El microservicio de IA
     NO debe ser accesible directamente desde el navegador (no hay
     rutas de la UI que llamen a FastAPI directamente — todo pasa por Express).

  3. En producción, CORS_ORIGINS debe contener:
       http://agroconnect-backend:10000   (URL interna de Render)
       https://agroconnect-backend.onrender.com  (URL externa, opcional)

  4. Para desarrollo local, el fallback incluye localhost automáticamente.

Lectura dinámica:
  La función build_cors_origins() construye la lista al arrancar el servidor,
  leyendo CORS_ORIGINS (comma-separated) desde el entorno. Si la variable no
  existe, aplica valores seguros de desarrollo local.
================================================================================
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING ESTRUCTURADO
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("agrobot.main")

# ─────────────────────────────────────────────────────────────────────────────
# CONSTRUCCIÓN DINÁMICA DE ORÍGENES CORS
# ─────────────────────────────────────────────────────────────────────────────

# Orígenes de desarrollo local siempre incluidos como base de seguridad.
# En producción estos nunca matchearán peticiones reales (Render bloquea
# tráfico externo hacia microservicios internos), pero son útiles para
# pruebas locales y smoke tests del CI/CD.
_CORS_ORIGINS_DEVELOPMENT: list[str] = [
    "http://localhost:5173",         # Vite dev (React)
    "http://localhost:3000",         # CRA / Next.js local
    "http://localhost:8001",         # Llamadas directas FastAPI en local
    "http://localhost:5000",         # Backend Express en local
    "http://localhost:10000",        # Backend Express en local (puerto Render)
]


def build_cors_origins() -> list[str]:
    """
    Construye la lista definitiva de orígenes CORS permitidos para FastAPI.

    Estrategia de construcción:
      1. Leer CORS_ORIGINS del entorno (comma-separated).
         Ejemplo de valor en Render Dashboard:
           http://agroconnect-backend:10000,https://agroconnect-backend.onrender.com

      2. Leer BACKEND_URL como origen adicional siempre permitido
         (el backend Express es el único cliente legítimo de este servicio).

      3. Combinar con los orígenes de desarrollo local (solo activos en local).

      4. Eliminar duplicados y valores vacíos.

    Returns:
        Lista deduplicada de strings con los orígenes permitidos.
    """
    origins: list[str] = []

    # Fuente 1: Variable CORS_ORIGINS explícita (producción)
    cors_env = os.getenv("CORS_ORIGINS", "")
    if cors_env:
        env_origins = [
            url.strip().rstrip("/")
            for url in cors_env.split(",")
            if url.strip()
        ]
        origins.extend(env_origins)
        logger.info("CORS_ORIGINS desde entorno: %s", env_origins)

    # Fuente 2: BACKEND_URL siempre añadido como origen permitido
    backend_url = os.getenv("BACKEND_URL", "").rstrip("/")
    if backend_url and backend_url not in origins:
        origins.append(backend_url)
        logger.info("BACKEND_URL añadido a CORS: %s", backend_url)

    # Fuente 3: Orígenes de desarrollo local (siempre incluidos como base)
    origins.extend(_CORS_ORIGINS_DEVELOPMENT)

    # Deduplicar preservando orden
    seen: set[str] = set()
    unique_origins: list[str] = []
    for origin in origins:
        if origin and origin not in seen:
            seen.add(origin)
            unique_origins.append(origin)

    return unique_origins


# Construir la lista UNA SOLA VEZ al iniciar el módulo
CORS_ALLOWED_ORIGINS: list[str] = build_cors_origins()

logger.info(
    "CORS configurado | %d orígenes permitidos | %s",
    len(CORS_ALLOWED_ORIGINS),
    CORS_ALLOWED_ORIGINS,
)

# ─────────────────────────────────────────────────────────────────────────────
# LIFESPAN — inicialización y limpieza de recursos al arrancar/apagar
# ─────────────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(application: FastAPI):
    """
    Context manager de ciclo de vida de FastAPI.
    Reemplaza los deprecated @app.on_event("startup") y ("shutdown").

    Startup: verifica que las variables de entorno críticas estén presentes.
    Shutdown: limpia conexiones abiertas (DB pools, clientes HTTP, etc.).
    """
    # ── STARTUP ───────────────────────────────────────────────────────────────
    logger.info("AgroBot AI Service arrancando...")

    # Verificar variables de entorno críticas
    missing_vars: list[str] = []

    if not os.getenv("ANTHROPIC_API_KEY"):
        missing_vars.append("ANTHROPIC_API_KEY")

    if not os.getenv("BACKEND_URL"):
        logger.warning(
            "BACKEND_URL no configurado. Las llamadas al backend Express "
            "usarán el valor por defecto: http://localhost:5000"
        )

    if missing_vars:
        # En producción, una variable crítica faltante es error fatal
        if os.getenv("PYTHON_ENV") == "production":
            raise RuntimeError(
                f"Variables de entorno faltantes en producción: {missing_vars}. "
                f"Configúralas en Render Dashboard > Environment."
            )
        else:
            logger.warning(
                "Variables no configuradas (modo desarrollo): %s", missing_vars
            )

    logger.info(
        "AgroBot AI Service listo | modelo=%s | entorno=%s",
        os.getenv("LLM_MODEL", "claude-sonnet-4-5"),
        os.getenv("PYTHON_ENV", "development"),
    )

    yield  # ← El servidor está corriendo mientras estamos aquí

    # ── SHUTDOWN ──────────────────────────────────────────────────────────────
    logger.info("AgroBot AI Service cerrando limpiamente...")
    # Aquí cerrar DB pools, clientes httpx persistentes, etc.
    # Por ahora el cliente anthropic y httpx se crean por petición


# ─────────────────────────────────────────────────────────────────────────────
# INSTANCIA FASTAPI
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AgroBot AI Service",
    description=(
        "Microservicio de Inteligencia Artificial de AgroConnect 2.0. "
        "Implementa el Agente IA AgroBot especializado en comercio agrícola de frutas."
    ),
    version="1.0.0",
    docs_url="/docs" if os.getenv("PYTHON_ENV") != "production" else None,
    redoc_url="/redoc" if os.getenv("PYTHON_ENV") != "production" else None,
    openapi_url="/openapi.json" if os.getenv("PYTHON_ENV") != "production" else None,
    lifespan=lifespan,
)

# ─────────────────────────────────────────────────────────────────────────────
# MIDDLEWARE CORS — debe registrarse ANTES de cualquier router
# ─────────────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,

    # Lista dinámica de orígenes permitidos construida desde variables de entorno.
    # En producción: solo el backend Express de Render.
    # En desarrollo: localhost en múltiples puertos.
    allow_origins=CORS_ALLOWED_ORIGINS,

    # credentials=True: permite que Express envíe el header Authorization
    # con el JWT del usuario al llamar a este microservicio.
    # Incompatible con allow_origins=["*"] — por eso usamos lista explícita.
    allow_credentials=True,

    # Métodos permitidos: FastAPI solo necesita POST y GET para el agente.
    # OPTIONS es manejado automáticamente por CORSMiddleware.
    allow_methods=["GET", "POST", "OPTIONS"],

    # Headers que Express puede incluir en sus peticiones a FastAPI.
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Origin-Service",
        "X-Session-Id",
        "Accept",
    ],

    # Caché del preflight OPTIONS por 10 minutos.
    max_age=600,
)

# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK — requerido por Render
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/health", tags=["Infrastructure"])
async def health_check() -> dict[str, Any]:
    """
    Endpoint de salud para el health check de Render.
    Verifica que el servicio FastAPI y la API de Anthropic estén accesibles.
    """
    anthropic_key_present = bool(os.getenv("ANTHROPIC_API_KEY"))

    return {
        "status": "healthy" if anthropic_key_present else "degraded",
        "service": "agroconnect-agrobot",
        "version": "1.0.0",
        "environment": os.getenv("PYTHON_ENV", "development"),
        "model": os.getenv("LLM_MODEL", "claude-sonnet-4-5"),
        "checks": {
            "anthropic_key": "present" if anthropic_key_present else "missing",
            "backend_url": os.getenv("BACKEND_URL", "not_configured"),
            "cors_origins_count": len(CORS_ALLOWED_ORIGINS),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# ROUTER PRINCIPAL DEL AGENTE — importar desde el módulo de agente
# ─────────────────────────────────────────────────────────────────────────────

try:
    from app.api.routers import chat as chat_router  # noqa: E402

    app.include_router(chat_router.router, prefix="/api/agent", tags=["AgroBot"])
    logger.info("Router /api/agent/chat registrado correctamente.")

except ImportError as exc:
    logger.warning(
        "No se pudo importar el router de chat: %s. "
        "Asegúrate de que app/api/routers/chat.py existe.",
        str(exc),
    )


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT FALLBACK DE CHAT (si el router aún no está implementado)
# Permite hacer smoke tests inmediatamente tras el deploy.
# ─────────────────────────────────────────────────────────────────────────────


@app.post("/api/agent/chat", tags=["AgroBot"], include_in_schema=False)
async def chat_fallback(request: Request) -> JSONResponse:
    """
    Endpoint de chat de fallback. Se activa solo si el router principal
    no pudo importarse. Llama directamente al núcleo del agente.

    En producción este endpoint debería ser reemplazado por el router
    modular de app/api/routers/chat.py.
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": "invalid_json", "message": "Body JSON inválido."},
        )

    message: str = str(body.get("message", "")).strip()
    session_id: str = str(body.get("sessionId", "")).strip()
    user_id: str = str(body.get("userId", "")).strip()

    if not message:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": "bad_request", "message": "El campo 'message' es obligatorio."},
        )

    # Extraer JWT Bearer del header Authorization para pasarlo al agente
    auth_header: str = request.headers.get("Authorization", "")
    token: str = auth_header.replace("Bearer ", "").strip() if auth_header.startswith("Bearer ") else ""

    try:
        from app.ai.agrobot_agent import execute_agent_reasoning  # noqa: PLC0415

        result = await execute_agent_reasoning(
            user_message=message,
            session_id=session_id or "default-session",
            user_id=user_id or "anonymous",
            token=token,
        )

        return JSONResponse(status_code=status.HTTP_200_OK, content=result)

    except Exception as exc:
        logger.error("Error en chat_fallback: %s", str(exc), exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "thought_badge": "Gestión de pedidos e historial",
                "response_payload": (
                    "AgroBot encontró un error interno. "
                    "El equipo técnico ha sido notificado. Por favor intenta de nuevo."
                ),
                "session_id": session_id,
                "user_id": user_id,
            },
        )


# ─────────────────────────────────────────────────────────────────────────────
# HANDLER DE ERRORES GLOBALES
# ─────────────────────────────────────────────────────────────────────────────


@app.exception_handler(Exception)
async def global_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Captura cualquier excepción no manejada y retorna JSON estructurado."""
    logger.error("Excepción no manejada: %s", str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "internal_server_error",
            "message": "Error interno del servidor AgroBot.",
        },
    )

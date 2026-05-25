/**
 * ============================================================================
 * AgroConnect 2.0 — backend/src/server.js
 * Servidor Express principal — Versión Producción (Render.com)
 * ============================================================================
 *
 * CAMBIO CLAVE v1.0 (Producción):
 *   El middleware CORS ahora usa un validador de origen dinámico en lugar
 *   del wildcard '*'. Esto es OBLIGATORIO porque:
 *
 *   1. Las peticiones del frontend React llevan `credentials: true`
 *      (cookies de sesión o el header Authorization con JWT Bearer).
 *
 *   2. El estándar CORS prohíbe explícitamente usar Access-Control-Allow-Origin: *
 *      cuando la petición contiene credenciales. Los navegadores bloquean la
 *      respuesta con error "CORS: wildcard not allowed with credentials".
 *
 *   3. El validador dinámico acepta solo:
 *      - http://localhost:5173  (dev local con Vite)
 *      - http://localhost:3000  (dev local alternativo)
 *      - El dominio exacto de process.env.FRONTEND_URL  (Vercel en producción)
 *
 * ============================================================================
 */

"use strict";

const express = require("express");
const cors = require("cors");
const helmet = require("helmet");
const rateLimit = require("express-rate-limit");
const { PrismaClient } = require("@prisma/client");

// ─────────────────────────────────────────────────────────────────────────────
// INICIALIZACIÓN
// ─────────────────────────────────────────────────────────────────────────────

const app = express();
const prisma = new PrismaClient();
const PORT = process.env.PORT || 10000;
const NODE_ENV = process.env.NODE_ENV || "development";

// ─────────────────────────────────────────────────────────────────────────────
// LISTA DE ORÍGENES PERMITIDOS (construida una sola vez al arrancar)
// ─────────────────────────────────────────────────────────────────────────────
//
// Reglas de composición:
//   • Siempre se permiten los orígenes de desarrollo local.
//   • En producción se añade dinámicamente FRONTEND_URL desde el entorno.
//   • Se eliminan duplicados y valores vacíos para evitar falsos positivos.
//
// ─────────────────────────────────────────────────────────────────────────────

const ALLOWED_ORIGINS_BASE = [
  "http://localhost:5173",    // Vite dev server (React)
  "http://localhost:3000",    // Create React App / Next.js local
  "http://localhost:4173",    // Vite preview
];

/**
 * Construye la lista definitiva de orígenes permitidos combinando
 * los orígenes de desarrollo con el dominio de producción en Vercel.
 *
 * FRONTEND_URL puede contener múltiples URLs separadas por coma para
 * soportar, por ejemplo, un dominio custom + el dominio *.vercel.app:
 *   FRONTEND_URL=https://agroconnect.app,https://agroconnect.vercel.app
 *
 * @returns {string[]} Lista deduplicada de orígenes permitidos.
 */
function buildAllowedOrigins() {
  const productionOrigins = (process.env.FRONTEND_URL || "")
    .split(",")
    .map((url) => url.trim().replace(/\/$/, "")) // quitar trailing slash
    .filter(Boolean);

  const combined = [...ALLOWED_ORIGINS_BASE, ...productionOrigins];

  // Deduplicar preservando orden
  return [...new Set(combined)];
}

const ALLOWED_ORIGINS = buildAllowedOrigins();

console.info(
  `[CORS] Orígenes permitidos (${NODE_ENV}): ${ALLOWED_ORIGINS.join(" | ")}`
);

// ─────────────────────────────────────────────────────────────────────────────
// FUNCIÓN VALIDADORA DE ORIGEN — corazón del CORS seguro
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Valida dinámicamente si el origen de la petición está en la lista
 * de orígenes permitidos. Esta función es invocada por el middleware
 * cors() en cada petición entrante.
 *
 * Lógica de validación:
 *   1. Si `origin` es undefined → petición server-to-server o curl sin Origin
 *      header (ej: Render health checks, llamadas internas del microservicio
 *      Python). Se permite sin restricciones.
 *
 *   2. Si `origin` está en ALLOWED_ORIGINS → se permite, se refleja el origen
 *      en Access-Control-Allow-Origin para compatibilidad con credenciales.
 *
 *   3. En cualquier otro caso → se rechaza con error claro para el navegador.
 *
 * @param {string|undefined} origin - Valor del header Origin de la petición.
 * @param {Function} callback - Callback de cors() con firma (error, allow).
 */
function corsOriginValidator(origin, callback) {
  // Caso 1: Sin header Origin (petición interna o herramienta como curl/Postman)
  if (!origin) {
    return callback(null, true);
  }

  // Caso 2: Origen en lista blanca
  if (ALLOWED_ORIGINS.includes(origin)) {
    return callback(null, true);
  }

  // Caso 3: Origen no permitido — el browser bloqueará la respuesta
  const errorMessage =
    `CORS bloqueado: el origen '${origin}' no está en la lista de orígenes ` +
    `permitidos. Agrega la URL correcta a FRONTEND_URL en Render Dashboard.`;

  console.warn(`[CORS] ${errorMessage}`);
  return callback(new Error(errorMessage), false);
}

// ─────────────────────────────────────────────────────────────────────────────
// CONFIGURACIÓN CORS COMPLETA
// ─────────────────────────────────────────────────────────────────────────────

const corsOptions = {
  /**
   * Función validadora dinámica en lugar del wildcard estático '*'.
   * Permite reflejar exactamente el Origin de la petición cuando es válido,
   * lo cual es requerido por el estándar para peticiones con `credentials: true`.
   */
  origin: corsOriginValidator,

  /**
   * credentials: true → el navegador enviará cookies, cabeceras Authorization
   * y certificados TLS de cliente en las peticiones cross-origin.
   * OBLIGATORIO para que React pueda enviar el JWT Bearer en cada request.
   */
  credentials: true,

  /**
   * Métodos HTTP permitidos para operaciones CRUD de la API REST.
   */
  methods: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],

  /**
   * Headers que el frontend React puede incluir en sus peticiones.
   * Authorization: portador del JWT.
   * Content-Type: para peticiones JSON y multipart (upload de fotos de lotes).
   * X-Session-Id: trazabilidad de sesión AgroBot.
   */
  allowedHeaders: [
    "Content-Type",
    "Authorization",
    "X-Session-Id",
    "X-Origin-Service",
    "Accept",
  ],

  /**
   * Headers de la respuesta que el browser puede leer desde JavaScript.
   * X-Request-Id facilita correlación de logs en Render + Grafana.
   */
  exposedHeaders: ["X-Request-Id"],

  /**
   * Cachea el resultado del preflight OPTIONS durante 10 minutos.
   * Reduce requests OPTIONS redundantes en producción.
   */
  maxAge: 600,

  /**
   * Responder con status 200 a OPTIONS (algunos browsers legacy requieren esto).
   */
  optionsSuccessStatus: 200,
};

// ─────────────────────────────────────────────────────────────────────────────
// RATE LIMITER — protección ante abuso de la API
// ─────────────────────────────────────────────────────────────────────────────

const apiLimiter = rateLimit({
  windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS || "60000", 10),
  max: parseInt(process.env.RATE_LIMIT_MAX_REQUESTS || "100", 10),
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    success: false,
    error: "rate_limit_exceeded",
    message: "Demasiadas peticiones. Por favor espera un momento e intenta de nuevo.",
  },
  // Excluir el health check del rate limit para que Render no lo bloquee
  skip: (req) => req.path === "/api/health",
});

// ─────────────────────────────────────────────────────────────────────────────
// MIDDLEWARES GLOBALES (orden importa)
// ─────────────────────────────────────────────────────────────────────────────

// 1. Helmet: cabeceras de seguridad HTTP (CSP, HSTS, X-Frame-Options, etc.)
app.use(
  helmet({
    crossOriginResourcePolicy: { policy: "cross-origin" }, // necesario para imágenes S3/CDN
    contentSecurityPolicy: NODE_ENV === "production",      // activar CSP solo en prod
  })
);

// 2. CORS: debe ir ANTES de cualquier router para interceptar peticiones OPTIONS
app.use(cors(corsOptions));

// 3. Responder explícitamente a preflight OPTIONS en todas las rutas
//    cors() ya maneja esto, pero lo reforzamos para reverse proxies de Render
app.options("*", cors(corsOptions));

// 4. Rate limiting sobre todas las rutas /api/*
app.use("/api", apiLimiter);

// 5. Parseo de JSON con límite de tamaño (protección ante DoS por payload enorme)
app.use(express.json({ limit: "10mb" }));
app.use(express.urlencoded({ extended: true, limit: "10mb" }));

// 6. Log de peticiones en desarrollo (evitar en producción para no saturar logs)
if (NODE_ENV === "development") {
  const morgan = require("morgan");
  app.use(morgan("dev"));
}

// ─────────────────────────────────────────────────────────────────────────────
// HEALTH CHECK — requerido por Render para saber si el servicio está vivo
// ─────────────────────────────────────────────────────────────────────────────

app.get("/api/health", async (_req, res) => {
  let dbStatus = "ok";

  try {
    // Verificar conectividad con Neon PostgreSQL
    await prisma.$queryRaw`SELECT 1`;
  } catch (error) {
    dbStatus = "error";
    console.error("[Health] DB no disponible:", error.message);
  }

  const status = dbStatus === "ok" ? 200 : 503;

  res.status(status).json({
    status: dbStatus === "ok" ? "healthy" : "degraded",
    service: "agroconnect-backend",
    version: process.env.npm_package_version || "1.0.0",
    environment: NODE_ENV,
    timestamp: new Date().toISOString(),
    checks: {
      database: dbStatus,
      uptime_seconds: Math.floor(process.uptime()),
    },
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// ROUTERS — importa tus routers existentes aquí
// ─────────────────────────────────────────────────────────────────────────────
// Descomenta y ajusta los paths según tu estructura actual de routers:
//
// const authRoutes      = require("./routes/authRoutes");
// const chatRoutes      = require("./routes/chatRoutes");
// const lotRoutes       = require("./routes/lotRoutes");
// const orderRoutes     = require("./routes/orderRoutes");
// const userRoutes      = require("./routes/userRoutes");
//
// app.use("/api/auth",   authRoutes);
// app.use("/api/chat",   chatRoutes);
// app.use("/api/lots",   lotRoutes);
// app.use("/api/orders", orderRoutes);
// app.use("/api/users",  userRoutes);

// ─────────────────────────────────────────────────────────────────────────────
// MIDDLEWARE DE ERROR GLOBAL
// ─────────────────────────────────────────────────────────────────────────────

// Captura errores CORS (origen no permitido) con respuesta JSON amigable
// eslint-disable-next-line no-unused-vars
app.use((err, req, res, next) => {
  // Error de CORS — el message contiene "CORS bloqueado"
  if (err.message && err.message.startsWith("CORS bloqueado")) {
    return res.status(403).json({
      success: false,
      error: "cors_error",
      message: err.message,
    });
  }

  // Error genérico
  console.error(`[Express] Error no manejado | ${err.message}`, err.stack);
  return res.status(500).json({
    success: false,
    error: "internal_server_error",
    message:
      NODE_ENV === "development"
        ? err.message
        : "Error interno del servidor. El equipo técnico ha sido notificado.",
  });
});

// 404 — ruta no encontrada
app.use((_req, res) => {
  res.status(404).json({
    success: false,
    error: "not_found",
    message: "El endpoint solicitado no existe en AgroConnect API.",
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// ARRANQUE DEL SERVIDOR
// ─────────────────────────────────────────────────────────────────────────────

const server = app.listen(PORT, "0.0.0.0", () => {
  console.info(`
╔══════════════════════════════════════════════════════════╗
║          AgroConnect 2.0 — Backend API                   ║
╠══════════════════════════════════════════════════════════╣
║  Entorno  : ${NODE_ENV.padEnd(45)}║
║  Puerto   : ${String(PORT).padEnd(45)}║
║  CORS     : ${String(ALLOWED_ORIGINS.length + " orígenes configurados").padEnd(45)}║
╚══════════════════════════════════════════════════════════╝
  `);
});

// Graceful shutdown: esperar peticiones en vuelo antes de cerrar
// Render envía SIGTERM antes de reemplazar el contenedor en un nuevo deploy
process.on("SIGTERM", async () => {
  console.info("[Shutdown] SIGTERM recibido. Cerrando servidor limpiamente...");
  server.close(async () => {
    await prisma.$disconnect();
    console.info("[Shutdown] Servidor cerrado. DB desconectada. Goodbye.");
    process.exit(0);
  });
});

module.exports = app; // exportar para tests con supertest

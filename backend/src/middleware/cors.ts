import cors from "cors";
import { env } from "../config/env.js";

export const corsMiddleware = cors({
  origin: (origin, callback) => {
    // Allow requests with no origin (like mobile apps, curl, server-to-server)
    if (!origin) return callback(null, true);

    const normalizedOrigin = origin.replace(/\/+$/, "");
    const allowed = env.CORS_ORIGINS.some((allowedOrigin) => {
      const normalizedAllowed = allowedOrigin.replace(/\/+$/, "");
      return normalizedOrigin === normalizedAllowed || allowedOrigin === "*";
    });

    if (allowed) {
      return callback(null, true);
    }

    // In development, allow localhost on any port
    if (env.NODE_ENV !== "production" && /^http:\/\/localhost(:\d+)?$/.test(origin)) {
      return callback(null, true);
    }

    callback(new Error(`CORS origin not allowed: ${origin}`));
  },
  credentials: true,
  methods: ["GET", "HEAD", "PUT", "PATCH", "POST", "DELETE", "OPTIONS"],
  allowedHeaders: ["Content-Type", "Authorization", "X-Requested-With", "X-CSRFToken", "x-csrftoken"],
  exposedHeaders: ["Set-Cookie"],
});

import express, { Request, Response, NextFunction } from "express";
import session from "express-session";
import cookieParser from "cookie-parser";
import path from "path";
import crypto from "crypto";
import { fileURLToPath } from "url";
import { env } from "./config/env.js";
import { corsMiddleware } from "./middleware/cors.js";
import { attachUserMiddleware } from "./middleware/auth.js";
import { errorHandler, notFoundHandler } from "./middleware/error.js";
import { authRouter } from "./routes/auth.routes.js";
import { bootstrapRouter } from "./routes/bootstrap.routes.js";
import { profileRouter } from "./routes/profile.routes.js";
import { videoRouter } from "./routes/video.routes.js";
import { secureRouter } from "./routes/secure.routes.js";
import { aiRouter } from "./routes/ai.routes.js";
import { telegramRouter } from "./routes/telegram.routes.js";
import { pagesRouter } from "./routes/pages.routes.js";
import { seedInitialPortfoliosIfNeeded } from "./services/seed.service.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();

// Trust reverse proxy (Render / Cloudflare) for secure cookies and accurate IP
app.set("trust proxy", 1);

// Middleware
app.use(corsMiddleware);
app.use(express.json({ limit: "20mb" }));
app.use(express.urlencoded({ extended: true, limit: "20mb" }));
app.use(cookieParser());

// Session configuration
const isProd = env.IS_PRODUCTION;
app.use(
  session({
    secret: env.SESSION_SECRET,
    resave: false,
    saveUninitialized: false,
    cookie: {
      maxAge: 1000 * 60 * 60 * 24 * 14, // 14 days
      httpOnly: true,
      secure: isProd,
      sameSite: isProd ? "none" : "lax",
    },
  })
);

// Inject csrftoken cookie for compatibility with frontend fetchers
app.use((req: Request, res: Response, next: NextFunction) => {
  if (!req.cookies.csrftoken) {
    const token = crypto.randomBytes(16).toString("hex");
    res.cookie("csrftoken", token, {
      maxAge: 1000 * 60 * 60 * 24 * 14,
      secure: isProd,
      sameSite: isProd ? "none" : "lax",
    });
  }
  next();
});

// Attach authenticated user to request
app.use(attachUserMiddleware);

// Serve static assets
app.use("/static", express.static(path.resolve(__dirname, "../static")));

// API & Auth Routes
app.use("/auth", authRouter);
app.use("/api", bootstrapRouter);
app.use("/api", profileRouter);
app.use("/api", videoRouter);
app.use("/api/secure", secureRouter);
app.use("/api", aiRouter);
app.use("/api", telegramRouter);
app.use("/", pagesRouter);

// Health check
app.get("/health", (req: Request, res: Response) => {
  res.json({ ok: true, timestamp: new Date().toISOString(), runtime: "node-typescript" });
});

// 404 & Error Handlers
app.use(notFoundHandler);
app.use(errorHandler);

// Start server
const PORT = env.PORT;
app.listen(PORT, async () => {
  console.log(`🚀 [Portfolio Show Backend] Server listening on port ${PORT} (${env.NODE_ENV})`);
  try {
    await seedInitialPortfoliosIfNeeded();
    console.log("✅ Database initialized successfully");
  } catch (err) {
    console.warn("⚠️ Initial database seed skipped or failed:", err);
  }
});

import { Response, NextFunction } from "express";
import crypto from "crypto";
import { prisma } from "../db/prisma.js";
import { AuthenticatedRequest, SessionUser, AccountRole } from "../types/index.js";

export function generateViewerHash(req: AuthenticatedRequest): string {
  const ip = req.ip || req.socket.remoteAddress || "0.0.0.0";
  const userAgent = req.headers["user-agent"] || "";
  const key = req.session?.userId ? `user:${req.session.userId}` : `guest:${ip}:${userAgent}`;
  return crypto.createHash("sha256").update(key).digest("hex");
}

export async function attachUserMiddleware(
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
): Promise<void> {
  req.viewerHash = generateViewerHash(req);

  const userId = req.session?.userId;
  if (!userId) {
    req.user = undefined;
    return next();
  }

  try {
    const user = await prisma.user.findUnique({
      where: { id: userId },
      include: { editorProfile: true },
    });

    if (!user || !user.isActive) {
      req.user = undefined;
      return next();
    }

    const role: AccountRole = (user.editorProfile?.role as AccountRole) || "client";

    req.user = {
      id: user.id,
      username: user.username,
      email: user.email,
      isStaff: user.isStaff || role === "admin",
      role,
    };
  } catch (error) {
    req.user = undefined;
  }

  next();
}

export function requireAuth(req: AuthenticatedRequest, res: Response, next: NextFunction): void {
  if (!req.user) {
    res.status(401).json({ ok: false, error: "Authentication required", message: "Sign in to continue." });
    return;
  }
  next();
}

export function requireEditor(req: AuthenticatedRequest, res: Response, next: NextFunction): void {
  if (!req.user) {
    res.status(401).json({ ok: false, error: "Authentication required" });
    return;
  }
  if (req.user.role !== "editor" && req.user.role !== "admin" && !req.user.isStaff) {
    res.status(403).json({ ok: false, error: "Editor or Admin access required" });
    return;
  }
  next();
}

export function requireAdmin(req: AuthenticatedRequest, res: Response, next: NextFunction): void {
  if (!req.user) {
    res.status(401).json({ ok: false, error: "Authentication required" });
    return;
  }
  if (req.user.role !== "admin" && !req.user.isStaff) {
    res.status(403).json({ ok: false, error: "Admin access required" });
    return;
  }
  next();
}

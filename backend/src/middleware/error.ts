import { Request, Response, NextFunction } from "express";

export function errorHandler(err: any, req: Request, res: Response, next: NextFunction): void {
  const status = typeof err.status === "number" ? err.status : 500;
  const message = err.message || "An unexpected error occurred.";

  if (process.env.NODE_ENV !== "production") {
    console.error("[Error]", err);
  }

  res.status(status).json({
    ok: false,
    error: err.name || "Error",
    message,
  });
}

export function notFoundHandler(req: Request, res: Response): void {
  res.status(404).json({
    ok: false,
    error: "NotFound",
    message: `Cannot ${req.method} ${req.path}`,
  });
}

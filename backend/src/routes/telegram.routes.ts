import { Router, Request, Response } from "express";
import { env } from "../config/env.js";

export const telegramRouter = Router();

telegramRouter.post("/telegram/webhook/:secret/", async (req: Request, res: Response): Promise<void> => {
  if (req.params.secret !== env.TELEGRAM_WEBHOOK_SECRET && env.TELEGRAM_WEBHOOK_SECRET) {
    res.status(403).json({ ok: false, error: "Invalid webhook secret" });
    return;
  }

  // Acknowledge Telegram webhook
  res.json({ ok: true });
});

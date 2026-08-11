import { Router, Response } from "express";
import { buildBootstrapPayload } from "../services/bootstrap.service.js";
import { AuthenticatedRequest } from "../types/index.js";

export const bootstrapRouter = Router();

bootstrapRouter.get("/bootstrap/", async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  try {
    const payload = await buildBootstrapPayload(req);
    res.json(payload);
  } catch (error: any) {
    res.status(500).json({ ok: false, error: "Failed to load bootstrap data", message: error.message });
  }
});

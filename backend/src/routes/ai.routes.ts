import { Router, Response } from "express";
import { generateGroqResponse, generateGeminiResponse } from "../services/ai.service.js";
import { AuthenticatedRequest } from "../types/index.js";

export const aiRouter = Router();

aiRouter.post("/ai/groq/", async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  try {
    const prompt = req.body.prompt || req.body.message;
    if (!prompt) {
      res.status(400).json({ ok: false, error: "Prompt is required." });
      return;
    }

    const reply = await generateGroqResponse(prompt);
    res.json({ ok: true, reply });
  } catch (error: any) {
    res.status(500).json({ ok: false, error: error.message || "Groq AI generation failed." });
  }
});

aiRouter.post("/ai/gemini/", async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  try {
    const prompt = req.body.prompt || req.body.message;
    if (!prompt) {
      res.status(400).json({ ok: false, error: "Prompt is required." });
      return;
    }

    const reply = await generateGeminiResponse(prompt);
    res.json({ ok: true, reply });
  } catch (error: any) {
    res.status(500).json({ ok: false, error: error.message || "Gemini AI generation failed." });
  }
});

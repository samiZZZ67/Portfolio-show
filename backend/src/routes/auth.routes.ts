import { Router, Response } from "express";
import { registerUser, authenticateUser } from "../services/auth.service.js";
import { AuthenticatedRequest } from "../types/index.js";

export const authRouter = Router();

authRouter.post("/signup/", async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  try {
    const { username, password, email, bio } = req.body;
    const { user } = await registerUser({ username, password, email, bio });

    if (req.session) {
      req.session.userId = user.id;
      req.session.username = user.username;
    }

    res.json({
      ok: true,
      success: true,
      current_user: user.username,
      current_user_role: user.role,
      user,
    });
  } catch (error: any) {
    res.status(400).json({ ok: false, error: error.message || "Registration failed." });
  }
});

authRouter.post("/login/", async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  try {
    const { username, password } = req.body;
    const result = await authenticateUser(username, password);

    if (!result) {
      res.status(400).json({ ok: false, error: "Invalid username or password." });
      return;
    }

    if (req.session) {
      req.session.userId = result.user.id;
      req.session.username = result.user.username;
    }

    res.json({
      ok: true,
      success: true,
      current_user: result.user.username,
      current_user_role: result.user.role,
      user: result.user,
    });
  } catch (error: any) {
    res.status(400).json({ ok: false, error: error.message || "Login failed." });
  }
});

authRouter.post("/logout/", (req: AuthenticatedRequest, res: Response): void => {
  if (req.session) {
    req.session.destroy(() => {
      res.clearCookie("connect.sid");
      res.json({ ok: true, success: true, current_user: null });
    });
  } else {
    res.json({ ok: true, success: true, current_user: null });
  }
});

authRouter.get("/google/", (req: AuthenticatedRequest, res: Response): void => {
  res.redirect("/?google_auth=unavailable");
});

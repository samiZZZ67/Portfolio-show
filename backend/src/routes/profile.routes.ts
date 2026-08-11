import { Router, Response } from "express";
import { prisma } from "../db/prisma.js";
import { requireAuth } from "../middleware/auth.js";
import { formatEditor } from "../services/bootstrap.service.js";
import { AuthenticatedRequest } from "../types/index.js";

export const profileRouter = Router();

profileRouter.post("/profile/", requireAuth, async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  try {
    const userId = req.user!.id;
    const { cname, bio, avatar_url, clients_served, completed_projects } = req.body;

    const profile = await prisma.editorProfile.update({
      where: { userId },
      data: {
        ...(cname !== undefined ? { cname: String(cname).trim() } : {}),
        ...(bio !== undefined ? { bio: String(bio).trim() } : {}),
        ...(avatar_url !== undefined ? { avatarUrl: String(avatar_url).trim() } : {}),
        ...(clients_served !== undefined ? { clientsServed: parseInt(clients_served, 10) || 0 } : {}),
        ...(completed_projects !== undefined ? { completedProjects: parseInt(completed_projects, 10) || 0 } : {}),
      },
      include: {
        user: true,
        videos: {
          include: {
            publicLikes: true,
            publicRatings: true,
            downloadRequests: true,
            downloadGrants: true,
          },
        },
      },
    });

    res.json({
      ok: true,
      success: true,
      editor: formatEditor(profile, userId, req.viewerHash),
    });
  } catch (error: any) {
    res.status(400).json({ ok: false, error: error.message });
  }
});

profileRouter.post("/contacts/", requireAuth, async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  try {
    const userId = req.user!.id;
    const { email, telegram, whatsapp, phone, other_contacts } = req.body;

    if (email !== undefined) {
      await prisma.user.update({
        where: { id: userId },
        data: { email: String(email).trim().toLowerCase() },
      });
    }

    const profile = await prisma.editorProfile.update({
      where: { userId },
      data: {
        ...(telegram !== undefined ? { telegram: String(telegram).trim() } : {}),
        ...(whatsapp !== undefined ? { whatsapp: String(whatsapp).trim() } : {}),
        ...(phone !== undefined ? { phone: String(phone).trim() } : {}),
        ...(other_contacts !== undefined ? { otherContacts: Array.isArray(other_contacts) ? other_contacts : [] } : {}),
      },
      include: {
        user: true,
        videos: {
          include: {
            publicLikes: true,
            publicRatings: true,
            downloadRequests: true,
            downloadGrants: true,
          },
        },
      },
    });

    res.json({
      ok: true,
      success: true,
      editor: formatEditor(profile, userId, req.viewerHash),
    });
  } catch (error: any) {
    res.status(400).json({ ok: false, error: error.message });
  }
});

profileRouter.post("/follow/:username/toggle/", requireAuth, async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  try {
    const followerProfile = await prisma.editorProfile.findUnique({
      where: { userId: req.user!.id },
    });
    const targetUser = await prisma.user.findUnique({
      where: { username: req.params.username },
      include: { editorProfile: true },
    });

    if (!followerProfile || !targetUser?.editorProfile) {
      res.status(404).json({ ok: false, error: "Profile not found." });
      return;
    }

    const followedId = targetUser.editorProfile.id;
    const existing = await prisma.followRelationship.findUnique({
      where: {
        unique_follow_relationship: {
          followerId: followerProfile.id,
          followedId,
        },
      },
    });

    let following = false;
    if (existing) {
      await prisma.followRelationship.delete({ where: { id: existing.id } });
      following = false;
    } else {
      await prisma.followRelationship.create({
        data: { followerId: followerProfile.id, followedId },
      });
      following = true;
    }

    res.json({ ok: true, following });
  } catch (error: any) {
    res.status(400).json({ ok: false, error: error.message });
  }
});

profileRouter.get("/profiles/:username/avatar/", async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  const user = await prisma.user.findUnique({
    where: { username: req.params.username },
    include: { editorProfile: true },
  });

  const avatar = user?.editorProfile?.avatarUrl || `https://picsum.photos/seed/${encodeURIComponent(req.params.username)}/200/200.jpg`;
  res.redirect(avatar);
});

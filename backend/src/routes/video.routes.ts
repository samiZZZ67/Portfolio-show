import { Router, Response } from "express";
import { prisma } from "../db/prisma.js";
import { requireAuth } from "../middleware/auth.js";
import {
  createVideo,
  updateVideo,
  deleteVideo,
  recordVideoPlay,
  toggleVideoLike,
  submitVideoRating,
} from "../services/video.service.js";
import { formatVideo, formatEditor } from "../services/bootstrap.service.js";
import { AuthenticatedRequest } from "../types/index.js";

export const videoRouter = Router();

videoRouter.get("/search/", async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  try {
    const q = String(req.query.q || "").trim();
    const category = String(req.query.category || "").trim();
    const type = String(req.query.type || "").trim();

    const whereClause: any = {};
    if (q) {
      whereClause.OR = [
        { title: { contains: q, mode: "insensitive" } },
        { profile: { cname: { contains: q, mode: "insensitive" } } },
        { profile: { user: { username: { contains: q, mode: "insensitive" } } } },
      ];
    }
    if (category && category !== "All") {
      whereClause.category = category;
    }
    if (type && type !== "all") {
      whereClause.contentType = type;
    }

    const videos = await prisma.portfolioVideo.findMany({
      where: whereClause,
      include: {
        profile: { include: { user: true } },
        publicLikes: true,
        publicRatings: true,
        downloadRequests: true,
        downloadGrants: true,
      },
      orderBy: { views: "desc" },
      take: 50,
    });

    res.json({
      ok: true,
      results: videos.map((v) => formatVideo(v, req.user?.id, req.viewerHash)),
    });
  } catch (error: any) {
    res.status(400).json({ ok: false, error: error.message });
  }
});

videoRouter.post("/videos/create/", requireAuth, async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  try {
    const { title, url, content_type, type, category, duration, thumbnail_url, platform, video_source } = req.body;

    const video = await createVideo({
      userId: req.user!.id,
      title,
      url,
      contentType: (content_type || type || "short") as "short" | "long",
      category,
      duration,
      thumbnailUrl: thumbnail_url,
      platform,
      videoSource: video_source,
    });

    res.json({ ok: true, success: true, video });
  } catch (error: any) {
    res.status(400).json({ ok: false, error: error.message });
  }
});

videoRouter.post("/videos/:id/update/", requireAuth, async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  try {
    const { title, url, content_type, type, category, duration, thumbnail_url } = req.body;

    const video = await updateVideo({
      userId: req.user!.id,
      videoId: req.params.id,
      title,
      url,
      contentType: (content_type || type) as "short" | "long" | undefined,
      category,
      duration,
      thumbnailUrl: thumbnail_url,
    });

    res.json({ ok: true, success: true, video });
  } catch (error: any) {
    res.status(400).json({ ok: false, error: error.message });
  }
});

videoRouter.post("/videos/:id/delete/", requireAuth, async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  try {
    const result = await deleteVideo(req.user!.id, req.params.id);
    res.json({ ok: true, ...result });
  } catch (error: any) {
    res.status(400).json({ ok: false, error: error.message });
  }
});

videoRouter.post("/videos/:id/move/", requireAuth, async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  try {
    const direction = req.body.direction; // "up" or "down"
    // Simple reorder acknowledge
    res.json({ ok: true, success: true });
  } catch (error: any) {
    res.status(400).json({ ok: false, error: error.message });
  }
});

videoRouter.post("/profiles/:username/videos/:id/play/", async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  try {
    const result = await recordVideoPlay(req.params.id);
    res.json({ ok: true, ...result });
  } catch (error: any) {
    res.status(400).json({ ok: false, error: error.message });
  }
});

videoRouter.post("/profiles/:username/videos/:id/like/", async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  try {
    const result = await toggleVideoLike(
      req.params.id,
      req.viewerHash || "anonymous",
      req.user?.id,
      req.ip,
      req.headers["user-agent"]
    );
    res.json({ ok: true, ...result });
  } catch (error: any) {
    res.status(400).json({ ok: false, error: error.message });
  }
});

videoRouter.post("/profiles/:username/videos/:id/react/", async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  try {
    const result = await toggleVideoLike(
      req.params.id,
      req.viewerHash || "anonymous",
      req.user?.id,
      req.ip,
      req.headers["user-agent"]
    );
    res.json({ ok: true, ...result });
  } catch (error: any) {
    res.status(400).json({ ok: false, error: error.message });
  }
});

videoRouter.post("/profiles/:username/videos/:id/rate/", async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  try {
    const score = parseInt(req.body.rating || req.body.score, 10);
    const result = await submitVideoRating(
      req.params.id,
      score,
      req.viewerHash || "anonymous",
      req.user?.id,
      req.ip,
      req.headers["user-agent"]
    );
    res.json({ ok: true, ...result });
  } catch (error: any) {
    res.status(400).json({ ok: false, error: error.message });
  }
});

videoRouter.get("/profiles/:username/videos/:id/download/", async (req: AuthenticatedRequest, res: Response): Promise<void> => {
  try {
    const video = await prisma.portfolioVideo.findUnique({
      where: { id: req.params.id },
    });
    if (!video) {
      res.status(404).send("Video not found");
      return;
    }
    const targetUrl = video.uploadedFile || video.url;
    if (!targetUrl) {
      res.status(404).send("No downloadable media available");
      return;
    }
    res.redirect(targetUrl);
  } catch (error: any) {
    res.status(400).send("Download error");
  }
});

import { Router, Response } from "express";
import multer from "multer";
import { prisma } from "../db/prisma.js";
import { requireAuth, requireAdmin } from "../middleware/auth.js";
import { createDownloadRequest, reviewDownloadRequest } from "../services/download.service.js";
import { uploadBufferToCloudinary } from "../config/cloudinary.js";
import { createVideo } from "../services/video.service.js";
import { AuthenticatedRequest } from "../types/index.js";

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 100 * 1024 * 1024 }, // 100 MB max
});

export const secureRouter = Router();

// Secure video file upload
secureRouter.post(
  "/videos/upload/",
  requireAuth,
  upload.single("file"),
  async (req: AuthenticatedRequest, res: Response): Promise<void> => {
    try {
      if (!req.file) {
        res.status(400).json({ ok: false, error: "No video file uploaded." });
        return;
      }

      const { title, content_type, type, category, duration } = req.body;
      const uploadedMedia = await uploadBufferToCloudinary(req.file.buffer, {
        resource_type: "video",
        folder: "portfolio_videos",
      });

      const video = await createVideo({
        userId: req.user!.id,
        title: title || req.file.originalname,
        contentType: (content_type || type || "short") as "short" | "long",
        category: category || "Commercial / Ads",
        duration: duration || "0:30",
        uploadedFile: uploadedMedia.secure_url,
        storagePublicId: uploadedMedia.public_id,
        videoSource: "upload",
        thumbnailUrl: uploadedMedia.secure_url.replace(/\.[^/.]+$/, ".jpg"),
      });

      res.json({ ok: true, success: true, video });
    } catch (error: any) {
      res.status(400).json({ ok: false, error: error.message || "Upload failed." });
    }
  }
);

// Download requests
secureRouter.post(
  "/videos/:id/download-request/",
  requireAuth,
  async (req: AuthenticatedRequest, res: Response): Promise<void> => {
    try {
      const result = await createDownloadRequest({
        requesterId: req.user!.id,
        videoId: req.params.id,
        message: req.body.message,
      });
      res.json({ ok: true, ...result });
    } catch (error: any) {
      res.status(400).json({ ok: false, error: error.message });
    }
  }
);

secureRouter.get(
  "/download-requests/",
  requireAuth,
  async (req: AuthenticatedRequest, res: Response): Promise<void> => {
    try {
      const requests = await prisma.videoDownloadRequest.findMany({
        where: { video: { profile: { userId: req.user!.id } } },
        include: {
          requester: true,
          video: true,
        },
        orderBy: { requestedAt: "desc" },
      });

      const formatted = requests.map((r) => ({
        id: r.id,
        video_id: r.videoId,
        video_title: r.video.title,
        video_preview_url: r.video.thumbnailUrl,
        requester_username: r.requester.username,
        requester_email: r.requester.email,
        status: r.status,
        message: r.requestMessage,
        response_message: r.ownerResponseMessage,
        requested_at: r.requestedAt,
        reviewed_at: r.reviewedAt,
      }));

      res.json({ ok: true, requests: formatted });
    } catch (error: any) {
      res.status(400).json({ ok: false, error: error.message });
    }
  }
);

secureRouter.post(
  "/download-requests/:id/review/",
  requireAuth,
  async (req: AuthenticatedRequest, res: Response): Promise<void> => {
    try {
      const result = await reviewDownloadRequest({
        reviewerId: req.user!.id,
        requestId: parseInt(req.params.id, 10),
        action: req.body.action || (req.body.approved ? "approve" : "reject"),
        responseMessage: req.body.response_message || req.body.message,
      });
      res.json({ ok: true, ...result });
    } catch (error: any) {
      res.status(400).json({ ok: false, error: error.message });
    }
  }
);

// Notifications
secureRouter.get(
  "/notifications/",
  requireAuth,
  async (req: AuthenticatedRequest, res: Response): Promise<void> => {
    try {
      const notifications = await prisma.ownerNotification.findMany({
        where: { ownerId: req.user!.id },
        orderBy: { createdAt: "desc" },
        take: 30,
      });
      res.json({ ok: true, notifications });
    } catch (error: any) {
      res.status(400).json({ ok: false, error: error.message });
    }
  }
);

secureRouter.post(
  "/notifications/:id/read/",
  requireAuth,
  async (req: AuthenticatedRequest, res: Response): Promise<void> => {
    try {
      await prisma.ownerNotification.update({
        where: { id: parseInt(req.params.id, 10) },
        data: { isRead: true, readAt: new Date() },
      });
      res.json({ ok: true, success: true });
    } catch (error: any) {
      res.status(400).json({ ok: false, error: error.message });
    }
  }
);

// Admin dashboard overview
secureRouter.get(
  "/admin/overview/",
  requireAdmin,
  async (req: AuthenticatedRequest, res: Response): Promise<void> => {
    try {
      const totalUsers = await prisma.user.count();
      const totalVideos = await prisma.portfolioVideo.count();
      const totalRequests = await prisma.videoDownloadRequest.count();
      const profiles = await prisma.editorProfile.findMany({
        include: { user: true, videos: true },
        orderBy: { createdAt: "desc" },
      });

      res.json({
        ok: true,
        stats: {
          total_users: totalUsers,
          total_videos: totalVideos,
          total_requests: totalRequests,
        },
        users: profiles.map((p) => ({
          id: p.userId,
          username: p.user.username,
          email: p.user.email,
          role: p.role,
          video_count: p.videos.length,
          created_at: p.createdAt,
        })),
      });
    } catch (error: any) {
      res.status(400).json({ ok: false, error: error.message });
    }
  }
);

secureRouter.post(
  "/admin/profiles/:username/role/",
  requireAdmin,
  async (req: AuthenticatedRequest, res: Response): Promise<void> => {
    try {
      const { role } = req.body;
      const targetUser = await prisma.user.findUnique({
        where: { username: req.params.username },
      });
      if (!targetUser) {
        res.status(404).json({ ok: false, error: "User not found." });
        return;
      }

      await prisma.editorProfile.update({
        where: { userId: targetUser.id },
        data: { role },
      });

      if (role === "admin") {
        await prisma.user.update({
          where: { id: targetUser.id },
          data: { isStaff: true },
        });
      }

      res.json({ ok: true, success: true, role });
    } catch (error: any) {
      res.status(400).json({ ok: false, error: error.message });
    }
  }
);

import { prisma } from "../db/prisma.js";
import { formatVideo } from "./bootstrap.service.js";

export async function createVideo(params: {
  userId: number;
  title: string;
  url?: string;
  contentType: "short" | "long";
  category: string;
  duration?: string;
  thumbnailUrl?: string;
  platform?: string;
  videoSource?: string;
  uploadedFile?: string;
  storagePublicId?: string;
}) {
  const profile = await prisma.editorProfile.findUnique({
    where: { userId: params.userId },
  });
  if (!profile) {
    throw new Error("Editor profile not found.");
  }

  const count = await prisma.portfolioVideo.count({
    where: { profileId: profile.id },
  });

  const duration = params.duration?.trim() || (params.contentType === "short" ? "0:30" : "5:00");
  const fallbackThumb = `https://picsum.photos/seed/${Math.random().toString(36).substring(7)}/${params.contentType === "short" ? "300/530" : "400/225"}.jpg`;
  const thumbnailUrl = params.thumbnailUrl?.trim() || fallbackThumb;

  const video = await prisma.portfolioVideo.create({
    data: {
      profileId: profile.id,
      title: params.title.trim(),
      url: (params.url || "").trim(),
      contentType: params.contentType,
      category: params.category || "Commercial / Ads",
      duration,
      thumbnailUrl,
      platform: params.platform || "other",
      videoSource: params.videoSource || (params.uploadedFile ? "upload" : "link"),
      uploadedFile: params.uploadedFile || "",
      storagePublicId: params.storagePublicId || "",
      sortOrder: count,
    },
    include: {
      profile: { include: { user: true } },
      publicLikes: true,
      publicRatings: true,
      downloadRequests: true,
      downloadGrants: true,
    },
  });

  return formatVideo(video, params.userId);
}

export async function updateVideo(params: {
  userId: number;
  videoId: string;
  title?: string;
  url?: string;
  contentType?: "short" | "long";
  category?: string;
  duration?: string;
  thumbnailUrl?: string;
}) {
  const video = await prisma.portfolioVideo.findUnique({
    where: { id: params.videoId },
    include: { profile: true },
  });

  if (!video) {
    throw new Error("Video not found.");
  }
  if (video.profile.userId !== params.userId) {
    throw new Error("You do not have permission to edit this video.");
  }

  const updated = await prisma.portfolioVideo.update({
    where: { id: params.videoId },
    data: {
      ...(params.title ? { title: params.title.trim() } : {}),
      ...(params.url !== undefined ? { url: params.url.trim() } : {}),
      ...(params.contentType ? { contentType: params.contentType } : {}),
      ...(params.category ? { category: params.category } : {}),
      ...(params.duration !== undefined ? { duration: params.duration.trim() } : {}),
      ...(params.thumbnailUrl !== undefined ? { thumbnailUrl: params.thumbnailUrl.trim() } : {}),
    },
    include: {
      profile: { include: { user: true } },
      publicLikes: true,
      publicRatings: true,
      downloadRequests: true,
      downloadGrants: true,
    },
  });

  return formatVideo(updated, params.userId);
}

export async function deleteVideo(userId: number, videoId: string) {
  const video = await prisma.portfolioVideo.findUnique({
    where: { id: videoId },
    include: { profile: true },
  });

  if (!video) {
    throw new Error("Video not found.");
  }
  if (video.profile.userId !== userId) {
    throw new Error("You do not have permission to delete this video.");
  }

  await prisma.portfolioVideo.delete({
    where: { id: videoId },
  });

  return { success: true, message: "Video deleted successfully." };
}

export async function recordVideoPlay(videoId: string) {
  const video = await prisma.portfolioVideo.update({
    where: { id: videoId },
    data: { views: { increment: 1 } },
    select: { views: true },
  });
  return { views: Number(video.views) };
}

export async function toggleVideoLike(videoId: string, viewerHash: string, userId?: number, ip?: string, userAgent?: string) {
  const existing = await prisma.videoLike.findUnique({
    where: {
      unique_public_video_like: {
        videoId,
        viewerHash,
      },
    },
  });

  let isActive = true;
  if (existing) {
    isActive = !existing.isActive;
    await prisma.videoLike.update({
      where: { id: existing.id },
      data: { isActive },
    });
  } else {
    await prisma.videoLike.create({
      data: {
        videoId,
        viewerHash,
        userId: userId || null,
        ipAddress: ip || null,
        userAgent: userAgent || "",
        isActive: true,
      },
    });
  }

  const activeCount = await prisma.videoLike.count({
    where: { videoId, isActive: true },
  });

  return {
    viewer_has_liked: isActive,
    likes_count: activeCount,
  };
}

export async function submitVideoRating(videoId: string, score: number, viewerHash: string, userId?: number, ip?: string, userAgent?: string) {
  if (score < 1 || score > 5) {
    throw new Error("Rating score must be between 1 and 5.");
  }

  await prisma.videoRating.upsert({
    where: {
      unique_public_video_rating: {
        videoId,
        viewerHash,
      },
    },
    update: {
      score,
      userId: userId || null,
      ipAddress: ip || null,
      userAgent: userAgent || "",
    },
    create: {
      videoId,
      score,
      viewerHash,
      userId: userId || null,
      ipAddress: ip || null,
      userAgent: userAgent || "",
    },
  });

  const ratings = await prisma.videoRating.findMany({
    where: { videoId },
    select: { score: true },
  });

  const totalScore = ratings.reduce((sum, r) => sum + r.score, 0);
  const count = ratings.length;
  const average = count > 0 ? parseFloat((totalScore / count).toFixed(1)) : 0;

  return {
    viewer_rating: score,
    ratings_count: count,
    average_rating: average,
  };
}

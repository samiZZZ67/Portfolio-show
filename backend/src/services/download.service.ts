import { prisma } from "../db/prisma.js";
import { notifyTelegramDownloadRequest } from "./telegram.service.js";

export async function createDownloadRequest(params: {
  requesterId: number;
  videoId: string;
  message?: string;
}) {
  const video = await prisma.portfolioVideo.findUnique({
    where: { id: params.videoId },
    include: { profile: { include: { user: true } } },
  });

  if (!video) {
    throw new Error("Video not found.");
  }

  // Owner doesn't need to request
  if (video.profile.userId === params.requesterId) {
    return {
      status: "approved",
      message: "You are the owner of this video.",
      download_url: video.uploadedFile || video.url,
    };
  }

  const requester = await prisma.user.findUnique({
    where: { id: params.requesterId },
  });
  if (!requester) {
    throw new Error("User not found.");
  }

  // Check if an active grant already exists
  const existingGrant = await prisma.videoDownloadGrant.findFirst({
    where: {
      userId: params.requesterId,
      videoId: params.videoId,
      isActive: true,
    },
  });
  if (existingGrant) {
    return {
      status: "approved",
      message: "You already have access to download this video.",
      download_url: video.uploadedFile || video.url,
    };
  }

  // Create or update the download request
  const request = await prisma.videoDownloadRequest.upsert({
    where: {
      unique_video_download_request_per_user: {
        requesterId: params.requesterId,
        videoId: params.videoId,
      },
    },
    update: {
      status: "pending",
      requestMessage: params.message?.trim() || "",
      videoTitleSnapshot: video.title,
      videoPreviewUrlSnapshot: video.thumbnailUrl,
      requestedAt: new Date(),
    },
    create: {
      requesterId: params.requesterId,
      videoId: params.videoId,
      status: "pending",
      requestMessage: params.message?.trim() || "",
      videoTitleSnapshot: video.title,
      videoPreviewUrlSnapshot: video.thumbnailUrl,
    },
  });

  // Create Owner Notification
  await prisma.ownerNotification.create({
    data: {
      ownerId: video.profile.userId,
      notificationType: "download_request",
      videoId: video.id,
      downloadRequestId: request.id,
      title: "New Download Access Request",
      message: `@${requester.username} requested download access for "${video.title}"`,
      payload: {
        requester_username: requester.username,
        video_title: video.title,
        request_id: request.id,
      },
    },
  });

  // Send Telegram notification if editor has telegram configured
  if (video.profile.telegramChatId || video.profile.telegram) {
    try {
      await notifyTelegramDownloadRequest({
        chatId: video.profile.telegramChatId || video.profile.telegram,
        editorUsername: video.profile.user.username,
        requesterUsername: requester.username,
        videoTitle: video.title,
        requestId: request.id,
      });
    } catch (e) {
      console.warn("[Telegram] notification failed:", e);
    }
  }

  return {
    status: "pending",
    message: "Download request submitted. The editor has been notified.",
    request_id: request.id,
  };
}

export async function reviewDownloadRequest(params: {
  reviewerId: number;
  requestId: number;
  action: "approve" | "reject";
  responseMessage?: string;
}) {
  const request = await prisma.videoDownloadRequest.findUnique({
    where: { id: params.requestId },
    include: {
      video: { include: { profile: true } },
      requester: true,
    },
  });

  if (!request) {
    throw new Error("Download request not found.");
  }

  const isOwner = request.video.profile.userId === params.reviewerId;
  const reviewer = await prisma.user.findUnique({ where: { id: params.reviewerId } });
  const isAdmin = Boolean(reviewer?.isStaff);

  if (!isOwner && !isAdmin) {
    throw new Error("You do not have permission to review this request.");
  }

  const now = new Date();
  const isApproved = params.action === "approve";

  const updatedRequest = await prisma.videoDownloadRequest.update({
    where: { id: params.requestId },
    data: {
      status: isApproved ? "approved" : "rejected",
      reviewedById: params.reviewerId,
      reviewedAt: now,
      approvedAt: isApproved ? now : null,
      ownerResponseMessage: params.responseMessage?.trim() || "",
    },
  });

  if (isApproved) {
    await prisma.videoDownloadGrant.upsert({
      where: { sourceRequestId: request.id },
      update: { isActive: true, revokedAt: null },
      create: {
        userId: request.requesterId,
        videoId: request.videoId,
        grantedById: params.reviewerId,
        sourceRequestId: request.id,
        isActive: true,
      },
    });
  } else {
    await prisma.videoDownloadGrant.updateMany({
      where: { userId: request.requesterId, videoId: request.videoId },
      data: { isActive: false, revokedAt: now },
    });
  }

  return {
    success: true,
    status: updatedRequest.status,
    message: isApproved ? "Request approved. Client now has download access." : "Request rejected.",
  };
}

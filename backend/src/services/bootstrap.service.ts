import { prisma } from "../db/prisma.js";
import { env } from "../config/env.js";
import { AuthenticatedRequest } from "../types/index.js";

export function formatVideo(video: any, viewerUserId?: number, viewerHash?: string) {
  const isOwner = viewerUserId && video.profile?.userId === viewerUserId;
  const publicLikes = video.publicLikes || [];
  const publicRatings = video.publicRatings || [];

  const likesCount = publicLikes.filter((l: any) => l.isActive).length;
  const ratingsCount = publicRatings.length;
  const totalScore = publicRatings.reduce((sum: number, r: any) => sum + r.score, 0);
  const averageRating = ratingsCount > 0 ? parseFloat((totalScore / ratingsCount).toFixed(1)) : 0;

  const viewerHasLiked = viewerHash
    ? publicLikes.some((l: any) => l.viewerHash === viewerHash && l.isActive)
    : false;

  const viewerRatingObj = viewerHash
    ? publicRatings.find((r: any) => r.viewerHash === viewerHash)
    : null;
  const viewerRating = viewerRatingObj ? viewerRatingObj.score : 0;

  // Determine download access state
  let downloadAccessState = "none";
  if (!video.uploadedFile && !video.storagePublicId) {
    downloadAccessState = "hidden";
  } else if (isOwner) {
    downloadAccessState = "owner";
  } else if (viewerUserId) {
    const grants = video.downloadGrants || [];
    const activeGrant = grants.find((g: any) => g.userId === viewerUserId && g.isActive);
    if (activeGrant) {
      downloadAccessState = "approved";
    } else {
      const requests = video.downloadRequests || [];
      const userRequest = requests.find((r: any) => r.requesterId === viewerUserId);
      if (userRequest) {
        downloadAccessState = userRequest.status === "approved" ? "approved" : userRequest.status === "rejected" ? "rejected" : "pending";
      }
    }
  }

  const username = video.profile?.user?.username || "";
  const directDownloadUrl = video.uploadedFile || `/api/profiles/${encodeURIComponent(username)}/videos/${video.id}/download/`;

  return {
    id: video.id,
    title: video.title,
    url: video.url || "",
    video_source: video.videoSource || "link",
    platform: video.platform || "other",
    thumbnail: video.thumbnailUrl || `https://picsum.photos/seed/${video.id}/400/225.jpg`,
    thumb: video.thumbnailUrl || `https://picsum.photos/seed/${video.id}/400/225.jpg`,
    type: video.contentType,
    category: video.category,
    duration: video.duration || "0:30",
    views: Number(video.views || 0),
    sort_order: video.sortOrder,
    has_uploaded_file: Boolean(video.uploadedFile || video.storagePublicId),
    likes_count: likesCount,
    ratings_count: ratingsCount,
    average_rating: averageRating,
    viewer_has_liked: viewerHasLiked,
    viewer_rating: viewerRating,
    download_access_state: downloadAccessState,
    download_url: directDownloadUrl,
    secure_download_url: `/api/secure/videos/${video.id}/download/`,
    created_at: video.createdAt,
  };
}

export function formatEditor(profile: any, viewerUserId?: number, viewerHash?: string) {
  const user = profile.user || {};
  const videos = (profile.videos || []).map((v: any) => ({
    ...v,
    profile: { ...profile, user },
  }));

  const formattedVideos = videos.map((v: any) => formatVideo(v, viewerUserId, viewerHash));
  const totalViews = formattedVideos.reduce((sum: number, v: any) => sum + (v.views || 0), 0);
  const shortCount = formattedVideos.filter((v: any) => v.type === "short").length;
  const longCount = formattedVideos.filter((v: any) => v.type === "long").length;

  const role = profile.role || "editor";
  const roleLabel = role === "admin" ? "Admin" : role === "editor" ? "Editor" : "Client";

  const defaultAvatar = `https://picsum.photos/seed/${encodeURIComponent(user.username || "editor")}/200/200.jpg`;
  const avatar = profile.avatarFile || profile.avatarUrl || defaultAvatar;

  const hasContact = Boolean(
    user.email || profile.telegram || profile.whatsapp || profile.phone || (profile.otherContacts && (profile.otherContacts as any[]).length > 0)
  );
  const isPublic = role === "editor" || (role === "client" && hasContact);

  return {
    username: user.username || "",
    display_name: profile.cname || user.username || "",
    cname: profile.cname || "",
    bio: profile.bio || "",
    avatar,
    avatar_url: avatar,
    role,
    role_label: roleLabel,
    email: user.email || "",
    telegram: profile.telegram || "",
    telegram_chat_id: profile.telegramChatId || "",
    whatsapp: profile.whatsapp || "",
    phone: profile.phone || "",
    other_contacts: profile.otherContacts || [],
    clients_served: profile.clientsServed || 0,
    completed_projects: profile.completedProjects || 0,
    is_public: isPublic,
    stats: {
      video_count: formattedVideos.length,
      total_views: totalViews,
      short_count: shortCount,
      long_count: longCount,
    },
    videos: formattedVideos,
  };
}

export async function buildBootstrapPayload(req: AuthenticatedRequest) {
  const viewerUserId = req.user?.id;
  const viewerHash = req.viewerHash;

  const profiles = await prisma.editorProfile.findMany({
    include: {
      user: true,
      videos: {
        orderBy: [{ sortOrder: "asc" }, { createdAt: "desc" }],
        include: {
          publicLikes: true,
          publicRatings: true,
          downloadRequests: true,
          downloadGrants: true,
        },
      },
    },
    orderBy: { createdAt: "asc" },
  });

  const formattedEditors = profiles.map((p) => formatEditor(p, viewerUserId, viewerHash));

  const currentUser = req.user ? req.user.username : null;
  const currentUserRole = req.user ? req.user.role : null;
  const canAccessAdmin = Boolean(req.user && (req.user.role === "admin" || req.user.isStaff));

  return {
    current_user: currentUser,
    current_user_role: currentUserRole,
    current_user_can_access_admin: canAccessAdmin,
    current_user_can_access_django_admin: canAccessAdmin,
    admin_panel_url: "/admin/",
    django_admin_url: "/admin/",
    groq_enabled: Boolean(env.GROQ_API_KEY),
    groq_model: env.GROQ_MODEL,
    gemini_enabled: Boolean(env.GEMINI_API_KEY),
    gemini_model: env.GEMINI_MODEL,
    google_auth_available: Boolean(env.GOOGLE_OAUTH_CLIENT_ID && env.GOOGLE_OAUTH_CLIENT_SECRET),
    google_auth_url: "/auth/google/",
    google_auth_message: env.GOOGLE_OAUTH_CLIENT_ID ? "" : "Google OAuth credentials not configured.",
    editors: formattedEditors,
  };
}

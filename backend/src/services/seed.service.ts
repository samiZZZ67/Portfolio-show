import { prisma } from "../db/prisma.js";
import { hashPassword } from "./auth.service.js";

export async function seedInitialPortfoliosIfNeeded() {
  const userCount = await prisma.user.count();
  if (userCount > 0) return;

  const defaultPasswordHash = await hashPassword("demo123");

  const sampleEditors = [
    {
      username: "CineMaster_Pro",
      email: "cinemaster@example.com",
      cname: "CineMaster Pro",
      bio: "Award-winning editor specializing in cinematic commercials and brand films. 8+ years of experience with top agencies worldwide.",
      avatarUrl: "https://picsum.photos/seed/cinemaster/200/200.jpg",
      telegram: "@CineMaster_Pro",
      whatsapp: "+1234567890",
      phone: "+1234567890",
      videos: [
        {
          title: 'Nike "Beyond Limits" Campaign',
          url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
          contentType: "long",
          category: "Commercial / Ads",
          duration: "2:30",
          views: 12400n,
          thumbnailUrl: "https://picsum.photos/seed/nike1/400/225.jpg",
        },
        {
          title: "Coca-Cola Summer Vibes",
          url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
          contentType: "short",
          category: "Commercial / Ads",
          duration: "0:30",
          views: 34200n,
          thumbnailUrl: "https://picsum.photos/seed/coke1/400/225.jpg",
        },
        {
          title: "BMW The Ultimate Drive",
          url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
          contentType: "long",
          category: "Commercial / Ads",
          duration: "1:45",
          views: 8900n,
          thumbnailUrl: "https://picsum.photos/seed/bmw1/400/225.jpg",
        },
      ],
    },
    {
      username: "CutCraft_Sam",
      email: "cutcraft@example.com",
      cname: "CutCraft Studio",
      bio: "Short-form content machine. 500M+ organic views generated for TikTok and Instagram creators. Fast turnaround and high retention pacing.",
      avatarUrl: "https://picsum.photos/seed/cutcraft/200/200.jpg",
      telegram: "@cutcraft_sam",
      whatsapp: "+1987654321",
      phone: "+1987654321",
      videos: [
        {
          title: "Viral TikTok Transition Hook",
          url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
          contentType: "short",
          category: "Social Media",
          duration: "0:15",
          views: 145000n,
          thumbnailUrl: "https://picsum.photos/seed/tiktok1/300/530.jpg",
        },
        {
          title: "Podcast Teaser That Hooked 1M",
          url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
          contentType: "short",
          category: "Social Media",
          duration: "0:25",
          views: 89000n,
          thumbnailUrl: "https://picsum.photos/seed/pod1/300/530.jpg",
        },
      ],
    },
    {
      username: "Ela_Admin",
      email: "admin@example.com",
      cname: "Platform Administrator",
      bio: "System administrator and curator for Editor's Space.",
      avatarUrl: "https://picsum.photos/seed/elaadmin/200/200.jpg",
      role: "admin",
      isStaff: true,
      videos: [],
    },
  ];

  for (const editor of sampleEditors) {
    await prisma.user.create({
      data: {
        username: editor.username,
        email: editor.email,
        passwordHash: defaultPasswordHash,
        isStaff: Boolean(editor.isStaff),
        editorProfile: {
          create: {
            role: editor.role || "editor",
            cname: editor.cname || editor.username,
            bio: editor.bio,
            avatarUrl: editor.avatarUrl,
            telegram: editor.telegram || "",
            whatsapp: editor.whatsapp || "",
            phone: editor.phone || "",
            videos: {
              create: editor.videos.map((v, index) => ({
                title: v.title,
                url: v.url,
                contentType: v.contentType,
                category: v.category,
                duration: v.duration,
                views: v.views,
                thumbnailUrl: v.thumbnailUrl,
                sortOrder: index,
              })),
            },
          },
        },
      },
    });
  }
}

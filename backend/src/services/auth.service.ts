import bcrypt from "bcryptjs";
import { prisma } from "../db/prisma.js";
import { SessionUser, AccountRole } from "../types/index.js";

export async function hashPassword(password: string): Promise<string> {
  const salt = await bcrypt.genSalt(10);
  return bcrypt.hash(password, salt);
}

export async function verifyPassword(password: string, hash: string): Promise<boolean> {
  if (!hash) return false;
  // Support standard bcrypt hash
  if (hash.startsWith("$2a$") || hash.startsWith("$2b$") || hash.startsWith("$2y$")) {
    return bcrypt.compare(password, hash);
  }
  // Fallback for simple demo/plain passwords during migration
  return password === hash;
}

export async function registerUser(params: {
  username: string;
  password: string;
  email?: string;
  bio?: string;
  role?: AccountRole;
}): Promise<{ user: SessionUser; profile: any }> {
  const normalizedUsername = params.username.trim();
  if (!normalizedUsername) {
    throw new Error("Username is required.");
  }
  if (params.password.length < 6) {
    throw new Error("Password must be at least 6 characters.");
  }

  const existing = await prisma.user.findUnique({
    where: { username: normalizedUsername },
  });
  if (existing) {
    throw new Error("This username is already taken. Please choose another one.");
  }

  const passwordHash = await hashPassword(params.password);
  const user = await prisma.user.create({
    data: {
      username: normalizedUsername,
      email: (params.email || "").trim().toLowerCase(),
      passwordHash,
      editorProfile: {
        create: {
          role: params.role || "editor",
          bio: params.bio?.trim() || "Video editor on Ela-sam Portfolio Show.",
        },
      },
    },
    include: {
      editorProfile: true,
    },
  });

  const sessionUser: SessionUser = {
    id: user.id,
    username: user.username,
    email: user.email,
    isStaff: user.isStaff,
    role: (user.editorProfile?.role as AccountRole) || "editor",
  };

  return { user: sessionUser, profile: user.editorProfile };
}

export async function authenticateUser(
  usernameOrEmail: string,
  password: string
): Promise<{ user: SessionUser; profile: any } | null> {
  const lookup = usernameOrEmail.trim();
  if (!lookup || !password) return null;

  const user = await prisma.user.findFirst({
    where: {
      OR: [
        { username: lookup },
        { email: lookup.toLowerCase() },
      ],
    },
    include: { editorProfile: true },
  });

  if (!user || !user.isActive) return null;

  const isMatch = await verifyPassword(password, user.passwordHash);
  if (!isMatch) return null;

  const sessionUser: SessionUser = {
    id: user.id,
    username: user.username,
    email: user.email,
    isStaff: user.isStaff || user.editorProfile?.role === "admin",
    role: (user.editorProfile?.role as AccountRole) || "editor",
  };

  return { user: sessionUser, profile: user.editorProfile };
}

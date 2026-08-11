import { Request } from "express";

export type AccountRole = "admin" | "editor" | "client";
export type VideoContentType = "short" | "long";
export type VideoCategory =
  | "Commercial / Ads"
  | "Wedding"
  | "YouTube Content"
  | "Documentary"
  | "Music Video"
  | "Social Media"
  | "Corporate";

export type DownloadRequestStatus = "pending" | "approved" | "rejected";

export interface ContactMethod {
  label: string;
  value: string;
}

export interface SessionUser {
  id: number;
  username: string;
  email: string;
  isStaff: boolean;
  role: AccountRole;
}

declare module "express-session" {
  interface SessionData {
    userId?: number;
    username?: string;
  }
}

export interface AuthenticatedRequest extends Request {
  user?: SessionUser;
  viewerHash?: string;
}

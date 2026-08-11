import { env } from "../config/env.js";

export async function notifyTelegramDownloadRequest(params: {
  chatId: string;
  editorUsername: string;
  requesterUsername: string;
  videoTitle: string;
  requestId: number;
}): Promise<boolean> {
  if (!env.TELEGRAM_BOT_TOKEN || !params.chatId) {
    return false;
  }

  const cleanChatId = params.chatId.replace("@", "").trim();
  const text = `🎬 *New Download Request*\n\n` +
    `Client: @${params.requesterUsername}\n` +
    `Video: *${params.videoTitle}*\n\n` +
    `Log in to your Editor's Space dashboard to review and approve access.`;

  try {
    const url = `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`;
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: cleanChatId,
        text,
        parse_mode: "Markdown",
      }),
    });
    return res.ok;
  } catch (error) {
    console.warn("[Telegram] sendMessage error:", error);
    return false;
  }
}

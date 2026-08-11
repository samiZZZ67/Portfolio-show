import { Groq } from "groq-sdk";
import { GoogleGenerativeAI } from "@google/generative-ai";
import { env } from "../config/env.js";

const SYSTEM_PROMPT = `You are an expert creative assistant for video editors and their clients on the Editor's Space portfolio platform.
Help users craft sharp client briefs, improve portfolio bios, optimize video titles, and plan engaging editing projects. Keep your answers concise, practical, and highly actionable.`;

export async function generateGroqResponse(userPrompt: string): Promise<string> {
  if (!env.GROQ_API_KEY) {
    throw new Error("Groq API key is not configured on the server.");
  }

  const groq = new Groq({ apiKey: env.GROQ_API_KEY });
  const completion = await groq.chat.completions.create({
    messages: [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: userPrompt.trim() },
    ],
    model: env.GROQ_MODEL,
    temperature: 0.7,
    max_tokens: 1024,
  });

  return completion.choices[0]?.message?.content || "No response generated.";
}

export async function generateGeminiResponse(userPrompt: string): Promise<string> {
  if (!env.GEMINI_API_KEY) {
    throw new Error("Gemini API key is not configured on the server.");
  }

  const genAI = new GoogleGenerativeAI(env.GEMINI_API_KEY);
  const model = genAI.getGenerativeModel({
    model: env.GEMINI_MODEL,
    systemInstruction: SYSTEM_PROMPT,
  });

  const result = await model.generateContent(userPrompt.trim());
  const response = await result.response;
  return response.text() || "No response generated.";
}

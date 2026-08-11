import { Router, Request, Response } from "express";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export const pagesRouter = Router();

pagesRouter.get("/robots.txt", (req: Request, res: Response): void => {
  res.type("text/plain").send("User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n");
});

pagesRouter.get("/sitemap.xml", (req: Request, res: Response): void => {
  const host = req.get("host") || "localhost:8000";
  const protocol = req.protocol || "https";
  const baseUrl = `${protocol}://${host}`;

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>${baseUrl}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>
  <url><loc>${baseUrl}/discover/</loc><changefreq>daily</changefreq><priority>0.8</priority></url>
  <url><loc>${baseUrl}/about/</loc><changefreq>weekly</changefreq><priority>0.5</priority></url>
</urlset>`;

  res.type("application/xml").send(xml);
});

pagesRouter.get("/about/", (req: Request, res: Response): void => {
  const aboutFile = path.resolve(__dirname, "../../templates/portfolio/about.html");
  if (fs.existsSync(aboutFile)) {
    res.sendFile(aboutFile);
  } else {
    res.send("<h1>About Portfolio Show</h1><p>Platform for video editors.</p>");
  }
});

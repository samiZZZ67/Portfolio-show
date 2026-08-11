# Portfolio Show — Backend (Node.js & TypeScript)

Independent REST API backend for **Portfolio Show / Editor's Space**, built with **Node.js (v24), TypeScript, Express, and Prisma ORM** connecting to **Neon PostgreSQL**.

---

## Tech Stack

- **Runtime**: Node.js v24+
- **Language**: TypeScript
- **Web Framework**: Express.js
- **ORM & Database**: Prisma ORM with Neon PostgreSQL (SSL connection pooling)
- **Authentication**: `express-session` with cross-origin cookie support (`SameSite: none`, `Secure: true`)
- **Password Security**: `bcryptjs`
- **Media Uploads**: Multer + Cloudinary SDK
- **AI Integrations**: Groq SDK (`groq-sdk`) + Google GenAI (`@google/generative-ai`)
- **Notifications**: Telegram Bot API Webhook & Push Notifications

---

## Local Setup

### 1. Install Dependencies
```bash
npm install
```

### 2. Configure Environment
Copy `.env.example` to `.env` and fill in your values:
```bash
copy .env.example .env
```

### 3. Initialize Prisma & Database
```bash
npx prisma generate
npx prisma db push
```

### 4. Start Development Server
```bash
npm run dev
```
The server will start on `http://localhost:8000`.

---

## Production Build
```bash
npm run build
npm start
```

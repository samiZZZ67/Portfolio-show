# Portfolio Show

A role-based video portfolio platform built with Django, allowing video editors to showcase their work, clients to browse and request downloads, and administrators to manage the system.

## Features

- **Role-Based Access Control**: Three user roles - Admin, Editor, and Client with appropriate permissions
- **Video Portfolio Management**: Editors can upload and manage their video portfolios
- **Secure Video Delivery**: Cloudinary integration for secure video streaming and downloads
- **Download Request System**: Clients can request downloads with approval workflow
- **Telegram Integration**: Notifications and approval/rejection via Telegram
- **Gemini AI Assistant**: Same-origin Django endpoint plus a home-page AI prompt box for briefs, bios, and editing guidance
- **REST API**: Full API for frontend integration
- **Responsive Frontend**: Integrated with existing HTML/JS frontend
- **Admin Dashboard**: Django admin for system management

## Tech Stack

- **Backend**: Django 5.2.13
- **API**: Django REST Framework
- *Database*: SQLite (development), PostgreSQL (production)
- **Media Storage**: Cloudinary
- **Deployment**: Render
- **Frontend**: HTML, CSS, JavaScript (existing index.html)

## Project Statistics

- **Main project source** (excluding Django migrations): `11,506` lines across `32` files
- **Full repo source** (including migrations): `12,223` lines across `44` files

**Main source breakdown:**
- Python: `6,423` lines
- JavaScript: `2,492` lines
- HTML/templates: `2,447` lines
- CSS: `144` lines

## Main Page

![Portfolio Image](https://github.com/samiZZZ67/Assets/blob/main/ela%20sam/Home%20page.png)

<details>
<summary>Toggle List</summary>
<ul>

<li>## Discover Page</li>
![Portfolio Image](https://github.com/samiZZZ67/Assets/blob/main/ela%20sam/Discover%20page.png)
<li>## About me</li>
![Portfolio Image](https://github.com/samiZZZ67/Assets/blob/main/ela%20sam/About%20me.png)
<li>## Add Video </li>
![Portfolio Image](https://github.com/samiZZZ67/Assets/blob/main/ela%20sam/add%20video.png)

</ul>
</details>

## Telegram Integration

The platform includes Telegram notifications for download requests. When a client requests to download a video, the video owner receives a notification via Telegram.

### User-Level Configuration

For video owners to receive Telegram notifications:

1. **Telegram Username**: Set during signup or profile update (optional for editors)
2. **Telegram Chat ID**: Must be configured for notifications to work
   - This is the unique identifier for the user's Telegram chat with your bot
   - Obtained when the user starts a conversation with your Telegram bot

### System-Level Configuration

For Telegram integration to work, the following environment variables must be set:

### Bot Setup

To set up Telegram notifications:

1. Create a Telegram bot via [@BotFather](https://t.me/botfather)
2. Get the bot token
3. Set `TELEGRAM_BOT_TOKEN` in your environment
4. Generate a secure webhook secret and set `TELEGRAM_WEBHOOK_SECRET`
5. Set the webhook URL: `https://yourdomain.com/api/telegram/webhook/YOUR_SECRET/`
6. Users need to start a chat with your bot to get their `chat_id`

### Setting Up the Webhook

1. **Generate a webhook secret** (use a random string):

2. **Set the webhook URL** with Telegram:

3. **Remove webhook** (if needed):

3. **Test the webhook**:

### User Onboarding

Users connect their Telegram by:

1. Setting their Telegram username in their profile
2. Starting a chat with your bot by sending `/start`
3. The bot automatically captures their `chat_id` and links it to their account
4. Users receive a confirmation message with their chat ID

### Commands Supported

- `/start` - Connect account and get chat ID
- `/help` - Show help information

### Troubleshooting

- **Bot not responding**: Check `TELEGRAM_BOT_TOKEN` is correct
- **Webhook not working**: Verify webhook URL is accessible and secret matches
- **Users not getting notifications**: Ensure they have set their Telegram username in profile and chatted with bot
- **Messages failing**: Check Telegram API limits and bot permissions

## Installation

### Prerequisites

- Python 3.8+
- pip
- Virtual environment (recommended)

### Setup

1. Clone the repository:
   
2. Create and activate virtual environment:
   
3. Install dependencies:
   
4. Set up environment variables:
   Create a `.env` file or set environment variables:
   
5. Run migrations:
   
6. Create superuser:
   
7. Collect static files:
   
8. Run the development server:
   
Visit `http://localhost:8000` to access the application.

## Usage

### User Roles

- **Admin**: Full system access, user management, approval workflows
- **Editor**: Upload and manage video portfolios, respond to download requests
- **Client**: Browse portfolios, request video downloads

### Key Workflows

1. **Editor Registration**: Sign up as an editor and create profile
2. **Video Upload**: Editors upload videos with metadata
3. **Client Browsing**: Clients view editor portfolios
4. **Download Requests**: Clients request downloads, editors approve/reject
5. **Secure Delivery**: Approved downloads via signed URLs

## API Endpoints

### Authentication
- `POST /auth/signup/` - User registration
- `POST /auth/login/` - User login
- `POST /auth/logout/` - User logout

### Profile Management
- `GET /api/bootstrap/` - Get user data
- `POST /api/profile/` - Update profile
- `POST /api/contacts/` - Update contacts

### Video Management
- `POST /api/videos/create/` - Upload new video
- `POST /api/videos/<uuid>/update/` - Update video
- `POST /api/videos/<uuid>/delete/` - Delete video
- `POST /api/videos/<uuid>/move/` - Move video

### Video Access
- `POST /api/profiles/<username>/videos/<uuid>/play/` - Stream video

### Telegram Integration
- `/api/telegram/webhook/<secret>/` - Telegram webhook

## Deployment

The application is configured for deployment on Render:

1. Set environment variables in Render dashboard
2. Use PostgreSQL database
3. Enable Cloudinary for media storage
4. Configure Telegram webhook URL

## Configuration

### Environment Variables

Create a `.env` file in your project root:

- `GEMINI_API_KEY` enables the home-page AI assistant.
- `GEMINI_MODEL` defaults to `gemini-2.5-flash` and can be changed if you want a different Gemini text model.

### Database

Development uses SQLite, production uses PostgreSQL via `dj-database-url`.

## Development

### Running Tests

### Code Style

Follow Django coding standards and use Black for formatting.

### Frontend Integration

The backend serves the existing `index.html` as a shell, injecting Django data via `backend_bridge.js`.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes and add tests
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please contact the development team or create an issue in the repository.

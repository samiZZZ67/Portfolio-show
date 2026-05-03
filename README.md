# Portfolio Show

A role-based video portfolio platform built with Django, allowing video editors to showcase their work, clients to browse and request downloads, and administrators to manage the system.

## Features

- **Role-Based Access Control**: Three user roles - Admin, Editor, and Client with appropriate permissions
- **Video Portfolio Management**: Editors can upload and manage their video portfolios
- **Secure Video Delivery**: Cloudinary integration for secure video streaming and downloads
- **Download Request System**: Clients can request downloads with approval workflow
- **Telegram Integration**: Notifications and approval/rejection via Telegram
- **REST API**: Full API for frontend integration
- **Responsive Frontend**: Integrated with existing HTML/JS frontend
- **Admin Dashboard**: Django admin for system management

## Tech Stack

- **Backend**: Django 5.2.13
- **API**: Django REST Framework
- **Database**: SQLite (development), PostgreSQL (production)
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

## Image Upload Component

Here's a professional image upload button with a toggle bar for different processing options:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Professional Image Upload with Toggle Bar</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f4f4f4;
        }
        .upload-container {
            max-width: 500px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .upload-button {
            display: inline-block;
            padding: 10px 20px;
            background-color: #007bff;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            transition: background-color 0.3s;
            margin-bottom: 20px;
        }
        .upload-button:hover {
            background-color: #0056b3;
        }
        .upload-button:disabled {
            background-color: #ccc;
            cursor: not-allowed;
        }
        .toggle-bar {
            display: flex;
            background-color: #e9ecef;
            border-radius: 5px;
            overflow: hidden;
            margin-bottom: 20px;
        }
        .toggle-option {
            flex: 1;
            padding: 10px;
            text-align: center;
            cursor: pointer;
            transition: background-color 0.3s, color 0.3s;
            border: none;
            background: transparent;
        }
        .toggle-option.active {
            background-color: #007bff;
            color: white;
        }
        .toggle-option:hover:not(.active) {
            background-color: #d6d8db;
        }
        .file-input {
            display: none;
        }
        .preview {
            margin-top: 20px;
            max-width: 100%;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="upload-container">
        <h2>Professional Image Upload</h2>
        <input type="file" id="imageInput" class="file-input" accept="image/*">
        <button class="upload-button" onclick="document.getElementById('imageInput').click()">Choose Image</button>
        
        <div class="toggle-bar" id="uploadModeBar">
            <button class="toggle-option active" data-mode="standard">Standard</button>
            <button class="toggle-option" data-mode="compressed">Compressed</button>
            <button class="toggle-option" data-mode="watermarked">Watermarked</button>
        </div>
        
        <img id="preview" class="preview" style="display: none;" alt="Image Preview">
    </div>

    <script>
        const imageInput = document.getElementById('imageInput');
        const preview = document.getElementById('preview');
        const uploadButton = document.querySelector('.upload-button');
        const toggleBar = document.getElementById('uploadModeBar');
        const toggleOptions = toggleBar.querySelectorAll('.toggle-option');
        let selectedMode = 'standard';

        toggleOptions.forEach(option => {
            option.addEventListener('click', function() {
                toggleOptions.forEach(opt => opt.classList.remove('active'));
                this.classList.add('active');
                selectedMode = this.dataset.mode;
            });
        });

        imageInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    preview.src = e.target.result;
                    preview.style.display = 'block';
                    uploadButton.textContent = 'Upload Image';
                    uploadButton.disabled = false;
                };
                reader.readAsDataURL(file);
            }
        });

        uploadButton.addEventListener('click', function() {
            if (imageInput.files.length > 0) {
                // Here you would typically send the file to your server
                // For demo purposes, we'll just show an alert
                alert(`Uploading image in ${selectedMode} mode`);
                
                // Reset after upload
                uploadButton.textContent = 'Choose Image';
                uploadButton.disabled = true;
                preview.style.display = 'none';
                imageInput.value = '';
            }
        });
    </script>
</body>
</html>
```

## How to Implement Image Upload in Django

Your project already has image upload functionality implemented for user avatars. Here's how it works and how you can implement similar uploads:

### 1. Model Setup
In your `models.py`, define a field for file uploads:

```python
from django.db import models

class YourModel(models.Model):
    image = models.ImageField(upload_to='images/', blank=True, null=True)
    # or for files
    file = models.FileField(upload_to='files/', blank=True, null=True)
```

Your project uses Cloudinary for media storage, so files are uploaded to the cloud.

### 2. Form Setup
In your `forms.py`, create a form with file input:

```python
from django import forms
from django.core.validators import FileExtensionValidator

class ImageUploadForm(forms.Form):
    image = forms.FileField(
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'gif'])]
    )
```

Your `ProfileForm` already includes `avatar_file` with validation.

### 3. View Setup
Handle file uploads in your view:

```python
from django.shortcuts import render
from django.http import JsonResponse

def upload_image(request):
    if request.method == 'POST':
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Process the uploaded file
            uploaded_file = request.FILES['image']
            # Save to model or handle as needed
            return JsonResponse({'message': 'Upload successful'})
    else:
        form = ImageUploadForm()
    return render(request, 'upload.html', {'form': form})
```

Your `profile_update_view` handles avatar uploads using `ProfileForm(request.POST, request.FILES)`.

### 4. Template Setup
Create a template with proper form encoding:

```html
<form method="post" enctype="multipart/form-data">
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit">Upload</button>
</form>
```

### 5. URL Configuration
Add the view to your `urls.py`:

```python
from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_image, name='upload_image'),
]
```

### 6. Settings Configuration
Ensure your `settings.py` has media settings:

```python
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

For Cloudinary (as in your project), configure the storage in settings.

### 7. Frontend Integration
For AJAX uploads, use JavaScript:

```javascript
const formData = new FormData();
formData.append('image', fileInput.files[0]);

fetch('/upload/', {
    method: 'POST',
    body: formData,
    headers: {
        'X-CSRFToken': getCookie('csrftoken')
    }
});
```

Your project uses this pattern in the frontend integration with `backend_bridge.js`.

### Key Points for Your Project
- Avatar uploads are handled in `profile_update_view` via `POST /api/profile/`
- Uses `ProfileForm` with `avatar_file` field
- Files are stored via Cloudinary
- Frontend sends files via AJAX with proper CSRF tokens

## Installation

### Prerequisites

- Python 3.8+
- pip
- Virtual environment (recommended)

### Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd portfolio-show
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   Create a `.env` file or set environment variables:
   ```bash
   SECRET_KEY=your-secret-key
   DEBUG=True
   DATABASE_URL=sqlite:///db.sqlite3
   CLOUDINARY_CLOUD_NAME=your-cloud-name
   CLOUDINARY_API_KEY=your-api-key
   CLOUDINARY_API_SECRET=your-api-secret
   ```

5. Run migrations:
   ```bash
   python manage.py migrate
   ```

6. Create superuser:
   ```bash
   python manage.py createsuperuser
   ```

7. Collect static files:
   ```bash
   python manage.py collectstatic
   ```

8. Run the development server:
   ```bash
   python manage.py runserver
   ```

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

- `SECRET_KEY`: Django secret key
- `DEBUG`: Debug mode (False for production)
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts
- `DATABASE_URL`: Database connection URL
- `CLOUDINARY_CLOUD_NAME`: Cloudinary cloud name
- `CLOUDINARY_API_KEY`: Cloudinary API key
- `CLOUDINARY_API_SECRET`: Cloudinary API secret
- `TELEGRAM_BOT_TOKEN`: Telegram bot token (if used)

### Database

Development uses SQLite, production uses PostgreSQL via `dj-database-url`.

## Development

### Running Tests

```bash
python manage.py test
```

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
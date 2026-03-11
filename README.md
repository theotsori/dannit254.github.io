# Dannit Media Studios — Portfolio Website

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the App
```bash
python app.py
```

Open http://localhost:5000

### 3. Admin Panel
Go to http://localhost:5000/admin/login

**Default Credentials:**
- Username: `admin`
- Password: `*******`

⚠️ **IMPORTANT:** Change the default password immediately after first login!

---

## 📁 Project Structure

```
dannit-media/
├── app.py                    # Flask app (routes, DB, auth)
├── requirements.txt
├── instance/
│   └── dannit.db             # SQLite database (auto-created)
├── static/
│   └── uploads/              # Uploaded photos
│       ├── studio/
│       ├── outdoor/
│       └── events/
└── templates/
    ├── base.html             # Main layout (nav, footer, lightbox)
    ├── index.html            # Homepage
    ├── portfolio.html        # Portfolio overview
    ├── gallery.html          # Category gallery page
    └── admin/
        ├── base.html         # Admin layout
        ├── login.html
        ├── dashboard.html
        ├── upload.html
        ├── photos.html
        ├── edit_photo.html
        ├── bookings.html
        └── settings.html
```

---

## 🎯 Admin Features

| Feature | Description |
|---------|-------------|
| Dashboard | Stats overview, recent uploads & bookings |
| Upload Photos | Drag & drop multi-upload with live preview |
| Photo Library | Visual grid, filter by category, quick feature toggle |
| Edit Photo | Change category, subcategory, caption, featured status |
| Delete Photo | Removes file from disk + database |
| Bookings | View all contact form submissions |
| Settings | Update site name, contact info, social links |
| Change Password | Secure password update |

---

## 🖼️ Portfolio Categories

### Studio Portraits
- Birthday Shoots
- Couple Shoots
- Family Shoots
- Baby Bump Shoots
- Wrap Photoshoots
- Graduation Shoots

### Outdoor Portraits
- Engagement Shoots
- Nature Portraits
- Urban Portraits

### Events
- Weddings
- Pre-Weddings
- Corporate Events
- Team Building

---

## 🌐 Deployment (Production)

### Using Gunicorn (recommended)
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

### Environment Variables
```bash
export SECRET_KEY="your-very-secure-random-key-here"
```

### Nginx Config (example)
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    client_max_body_size 25M;

    location /static/uploads/ {
        alias /path/to/dannit-media/static/uploads/;
        expires 30d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### GitHub Pages Note
This is a Flask (Python) app and **cannot** be deployed to GitHub Pages (static only).
Recommended free hosts:
- **Render.com** — Free tier, supports Flask
- **Railway.app** — Easy Flask deployment
- **PythonAnywhere** — Beginner-friendly Python hosting

---

## 🔒 Security Checklist Before Going Live
- [ ] Enable HTTPS (SSL certificate)
- [ ] Consider Cloudflare for CDN + DDoS protection

---

## 📱 Features
- ✅ Custom gold cursor animation
- ✅ Cinematic hero with parallax
- ✅ Masonry photo gallery
- ✅ Lightbox with keyboard navigation
- ✅ Portfolio categories + subcategory filters
- ✅ Contact form with AJAX (no page reload)
- ✅ WhatsApp floating button
- ✅ Scroll reveal animations
- ✅ Fully responsive mobile design
- ✅ Admin dashboard with secure login
- ✅ Drag & drop multi-photo upload
- ✅ Featured photos system (homepage)
- ✅ SEO meta tags

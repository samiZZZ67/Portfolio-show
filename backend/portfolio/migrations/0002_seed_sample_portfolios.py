from django.contrib.auth.hashers import make_password
from django.db import migrations

SAMPLE_EDITORS = [
    {
        "username": "CineMaster_Pro",
        "bio": "Award-winning editor specializing in cinematic commercials and brand films. 8+ years of experience with top agencies worldwide.",
        "email": "cinemaster@example.com",
        "telegram": "@CineMaster_Pro",
        "whatsapp": "",
        "phone": "",
        "videos": [
            {"title": 'Nike "Beyond Limits" Campaign', "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/nike1/400/225.jpg", "type": "long", "category": "Commercial / Ads", "duration": "2:30", "views": 12400},
            {"title": "Coca-Cola Summer Vibes", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/coke1/400/225.jpg", "type": "short", "category": "Commercial / Ads", "duration": "0:30", "views": 34200},
            {"title": "BMW The Ultimate Drive", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/bmw1/400/225.jpg", "type": "long", "category": "Commercial / Ads", "duration": "1:45", "views": 8900},
            {"title": "Adidas Reel - Quick Cuts", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/adidas1/300/530.jpg", "type": "short", "category": "Commercial / Ads", "duration": "0:15", "views": 56800},
            {"title": "Tech Product Launch", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/tech1/400/225.jpg", "type": "long", "category": "Corporate", "duration": "4:20", "views": 4200},
        ],
    },
    {
        "username": "WeddingFrames",
        "bio": "Capturing love stories through beautiful editing. Every wedding deserves a cinematic touch that families will treasure forever.",
        "email": "weddingframes@example.com",
        "telegram": "",
        "whatsapp": "+1-555-0123",
        "phone": "+1-555-0456",
        "videos": [
            {"title": "Sarah & James - Lake Tahoe Wedding", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/wed2/400/225.jpg", "type": "long", "category": "Wedding", "duration": "8:30", "views": 6700},
            {"title": "Beach Ceremony Highlights", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/wed3/300/530.jpg", "type": "short", "category": "Wedding", "duration": "0:45", "views": 23100},
            {"title": "Garden Wedding - Emma & Carlos", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/wed4/400/225.jpg", "type": "long", "category": "Wedding", "duration": "6:15", "views": 5400},
            {"title": "First Dance Reel", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/wed5/300/530.jpg", "type": "short", "category": "Wedding", "duration": "0:30", "views": 19800},
        ],
    },
    {
        "username": "DocuLens",
        "bio": "Documentary editor with a passion for storytelling. From environmental docs to human interest stories, I bring narratives to life.",
        "email": "doculens@example.com",
        "telegram": "@DocuLens",
        "whatsapp": "",
        "phone": "",
        "videos": [
            {"title": "Ocean Depths - Marine Life Documentary", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/doc1/400/225.jpg", "type": "long", "category": "Documentary", "duration": "22:00", "views": 156000},
            {"title": "Behind the Lens - Filmmaker Story", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/doc2/400/225.jpg", "type": "long", "category": "Documentary", "duration": "15:30", "views": 89000},
            {"title": "Urban Wildlife Reel", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/doc3/300/530.jpg", "type": "short", "category": "Documentary", "duration": "0:60", "views": 42000},
        ],
    },
    {
        "username": "YouTubEdit",
        "bio": "Full-time YouTube editor for creators with 100K-10M subscribers. Fast turnaround, engaging pacing, and clean visual style.",
        "email": "ytedit@example.com",
        "telegram": "@YouTubEdit",
        "whatsapp": "+1-555-0789",
        "phone": "",
        "videos": [
            {"title": "Travel Vlog - Japan Edition", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/yt1/400/225.jpg", "type": "long", "category": "YouTube Content", "duration": "18:45", "views": 234000},
            {"title": "Tech Review - iPhone 16", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/yt2/400/225.jpg", "type": "long", "category": "YouTube Content", "duration": "12:20", "views": 567000},
            {"title": "Cooking Short - 60s Recipe", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/yt3/300/530.jpg", "type": "short", "category": "YouTube Content", "duration": "0:60", "views": 890000},
            {"title": "Day in My Life Reel", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/yt4/300/530.jpg", "type": "short", "category": "Social Media", "duration": "0:30", "views": 1200000},
        ],
    },
    {
        "username": "BeatCutter",
        "bio": "Music video editor and visual artist. I sync every beat, every drop, every emotion to create unforgettable visual experiences.",
        "email": "beatcutter@example.com",
        "telegram": "",
        "whatsapp": "",
        "phone": "+1-555-0321",
        "videos": [
            {"title": "Neon Nights - EDM Music Video", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/mv1/400/225.jpg", "type": "long", "category": "Music Video", "duration": "3:45", "views": 78000},
            {"title": "Hip Hop Visualizer", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/mv2/300/530.jpg", "type": "short", "category": "Music Video", "duration": "0:30", "views": 156000},
            {"title": "Acoustic Session - Live Edit", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/mv3/400/225.jpg", "type": "long", "category": "Music Video", "duration": "4:10", "views": 45000},
            {"title": "Beat Drop Reel", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/mv4/300/530.jpg", "type": "short", "category": "Music Video", "duration": "0:15", "views": 234000},
        ],
    },
    {
        "username": "SocialBuzz",
        "bio": "Creating viral social media content for brands and influencers. Reels, TikToks, Shorts - I know what stops the scroll.",
        "email": "socialbuzz@example.com",
        "telegram": "@SocialBuzz_Edits",
        "whatsapp": "+1-555-0654",
        "phone": "",
        "videos": [
            {"title": "Fashion Brand Reel", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/sc1/300/530.jpg", "type": "short", "category": "Social Media", "duration": "0:30", "views": 450000},
            {"title": "Fitness Transformation Reel", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/sc2/300/530.jpg", "type": "short", "category": "Social Media", "duration": "0:45", "views": 678000},
            {"title": "Food Brand TikTok Series", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/sc3/300/530.jpg", "type": "short", "category": "Social Media", "duration": "0:20", "views": 890000},
            {"title": "Travel Short - Bali Vibes", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "thumb": "https://picsum.photos/seed/sc4/300/530.jpg", "type": "short", "category": "Social Media", "duration": "0:35", "views": 567000},
        ],
    },
]


def seed_sample_portfolios(apps, schema_editor):
    User = apps.get_model("auth", "User")
    EditorProfile = apps.get_model("portfolio", "EditorProfile")
    PortfolioVideo = apps.get_model("portfolio", "PortfolioVideo")

    for editor in SAMPLE_EDITORS:
        user, created = User.objects.get_or_create(
            username=editor["username"],
            defaults={
                "email": editor["email"],
                "password": make_password(None),
            },
        )
        if not created:
            continue

        profile = EditorProfile.objects.create(
            user=user,
            bio=editor["bio"],
            telegram=editor["telegram"],
            whatsapp=editor["whatsapp"],
            phone=editor["phone"],
        )

        for index, video in enumerate(editor["videos"]):
            PortfolioVideo.objects.create(
                profile=profile,
                title=video["title"],
                url=video["url"],
                thumbnail_url=video["thumb"],
                content_type=video["type"],
                category=video["category"],
                duration=video["duration"],
                views=video["views"],
                sort_order=index,
            )


def remove_sample_portfolios(apps, schema_editor):
    User = apps.get_model("auth", "User")
    usernames = [editor["username"] for editor in SAMPLE_EDITORS]
    User.objects.filter(username__in=usernames).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_sample_portfolios, remove_sample_portfolios),
    ]

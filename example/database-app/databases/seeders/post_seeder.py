from fastapi_startkit.masoniteorm.seeders import Seeder

from app.models import Post, User, Tag, PostTag


class PostSeeder(Seeder):
    async def run(self):
        user = await User.first()
        if not user:
            return

        # Create tags
        tag_laravel = await Tag.first_or_create({"name": "laravel"})
        tag_fastapi = await Tag.first_or_create({"name": "fastapi"})
        tag_database = await Tag.first_or_create({"name": "database"})

        # Create First Blog Post
        post1 = await Post.create({
            "user_id": user.id,
            "title": "Laravel and Databases",
            "content": "This is a post about Laravel framework and its database capabilities."
        })

        # Attach tags to first post
        await PostTag.first_or_create({"post_id": post1.id, "tag_id": tag_laravel.id})
        await PostTag.first_or_create({"post_id": post1.id, "tag_id": tag_database.id})

        # Create Second Blog Post
        post2 = await Post.create({
            "user_id": user.id,
            "title": "FastAPI and Databases",
            "content": "This is a post about FastAPI performance and database handling."
        })

        # Attach tags to second post
        await PostTag.first_or_create({"post_id": post2.id, "tag_id": tag_fastapi.id})
        await PostTag.first_or_create({"post_id": post2.id, "tag_id": tag_database.id})

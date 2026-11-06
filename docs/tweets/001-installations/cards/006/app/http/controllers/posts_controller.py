from app.Post import Post


class PostsController:
    async def index(self):
        posts = await Post.all()
        return posts.serialize()

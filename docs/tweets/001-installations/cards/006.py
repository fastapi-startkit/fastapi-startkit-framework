class Post(Model):
    id: int
    title: str
    body: str

class PostsController:
    async def index(self):
        posts = await Post.all()
        return posts.serialize()

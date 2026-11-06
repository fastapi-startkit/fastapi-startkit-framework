# Tweet 6/10

Need a database? `artisan db:install` adds the provider for you. Models and migrations come from the CLI, and every query is async ⚡

Card: `app/Post.py` + `posts_controller.py`

```python
class Post(Model):
    id: int
    title: str
    body: str

class PostsController:
    async def index(self):
        posts = await Post.all()
        return posts.serialize()
```

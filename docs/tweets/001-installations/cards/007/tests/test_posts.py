class TestPosts(HttpTestCase, RefreshDatabase):
    def get_application(self):
        from bootstrap.application import app
        return app

    async def test_lists_posts(self):
        await Post.create({"title": "Hello", "body": "From tests"})
        response = await self.get("/posts")
        response.assert_ok()

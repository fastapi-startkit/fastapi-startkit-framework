import os
import uuid

from ..file import File
from ...utils.filesystem import get_extension


class S3Driver:
    def __init__(self, application):
        self.application = application
        self.options = {}
        self.connection = None

    def set_options(self, options):
        self.options = options
        return self

    def get_connection(self):
        try:
            import boto3
        except ImportError:
            raise ModuleNotFoundError("Could not find the 'boto3' library. Run 'pip install boto3' to fix this.")

        if not self.connection:
            self.connection = boto3.Session(
                aws_access_key_id=self.options.get("key") or self.options.get("client"),
                aws_secret_access_key=self.options.get("secret"),
                region_name=self.options.get("region"),
            )

        return self.connection

    def get_client(self):
        import botocore.config

        config = botocore.config.Config(
            s3={"addressing_style": "path" if self.options.get("use_path_style_endpoint") else "auto"}
        )
        return self.get_connection().client("s3", endpoint_url=self.options.get("endpoint"), config=config)

    def get_resource(self):
        import botocore.config

        config = botocore.config.Config(
            s3={"addressing_style": "path" if self.options.get("use_path_style_endpoint") else "auto"}
        )
        return self.get_connection().resource("s3", endpoint_url=self.options.get("endpoint"), config=config)

    def get_bucket(self):
        return self.options.get("bucket")

    def get_name(self, path, alias):
        extension = get_extension(path)
        return f"{alias}{extension}"

    def put(self, file_path, content):
        self.get_resource().Bucket(self.get_bucket()).put_object(Key=file_path, Body=content)
        return content

    def put_file(self, file_path, content, name=None):
        file_name = self.get_name(content.name, name or str(uuid.uuid4()))

        if hasattr(content, "get_content"):
            content = content.get_content()

        self.get_resource().Bucket(self.get_bucket()).put_object(Key=os.path.join(file_path, file_name), Body=content)
        return os.path.join(file_path, file_name)

    def get(self, file_path):
        try:
            return (
                self.get_resource().Bucket(self.get_bucket()).Object(file_path).get().get("Body").read().decode("utf-8")
            )
        except self.missing_file_exceptions():
            pass

    def missing_file_exceptions(self):
        import botocore

        return (botocore.exceptions.ClientError,)

    def exists(self, file_path):
        try:
            self.get_resource().Bucket(self.get_bucket()).Object(file_path).load()
            return True
        except self.missing_file_exceptions():
            return False

    def missing(self, file_path):
        return not self.exists(file_path)

    def stream(self, file_path):
        import mimetypes
        from fastapi import HTTPException
        from fastapi.responses import StreamingResponse

        try:
            obj = self.get_client().get_object(
                Bucket=self.get_bucket(),
                Key=file_path,
            )
        except self.missing_file_exceptions():
            raise HTTPException(status_code=404, detail="File not found.")

        media_type, _ = mimetypes.guess_type(file_path)
        # No Content-Length header — avoids the BaseHTTPMiddleware streaming
        # conflict that occurs when Content-Length is set on a streamed response.
        return StreamingResponse(
            obj["Body"].iter_chunks(chunk_size=65536),
            media_type=media_type or "application/octet-stream",
        )

    def copy(self, from_file_path, to_file_path):
        copy_source = {"Bucket": self.get_bucket(), "Key": from_file_path}
        self.get_resource().meta.client.copy(copy_source, self.get_bucket(), to_file_path)

    def move(self, from_file_path, to_file_path):
        self.copy(from_file_path, to_file_path)
        self.delete(from_file_path)

    def prepend(self, file_path, content):
        value = self.get(file_path)
        content = content + value
        self.put(file_path, content)
        return content

    def append(self, file_path, content):
        value = self.get(file_path) or ""
        value += content
        self.put(file_path, content)

    def delete(self, file_path):
        return self.get_resource().Object(self.get_bucket(), file_path).delete()

    def store(self, file, name=None):
        full_path = name or file.hash_path_name()
        self.get_resource().Bucket(self.get_bucket()).put_object(Key=full_path, Body=file.stream())
        return full_path

    def make_file_path_if_not_exists(self, file_path):
        if not os.path.isfile(file_path):
            if not os.path.exists(os.path.dirname(file_path)):
                # Create the path to the model if it does not exist
                os.makedirs(os.path.dirname(file_path))

            return True

        return False

    def get_files(self, directory=None):
        bucket = self.get_resource().Bucket(self.get_bucket())

        if directory:
            objects = bucket.objects.all().filter(Prefix=directory)
        else:
            objects = bucket.objects.all()

        files = []
        for my_bucket_object in objects.all():
            if "/" not in my_bucket_object.key:
                files.append(File(my_bucket_object, my_bucket_object.key))

        return files

    def download(self, file_path, name=None, force=False):
        url = self.get_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": self.get_bucket(), "Key": file_path},
            ExpiresIn=3600,
        )
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url)

    def url(self, file_path):
        return f"{self.options.get('url')}/{file_path}"

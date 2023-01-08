from cachetools import cached
from google.cloud import storage
from google.oauth2 import service_account
from pyramid.threadlocal import get_current_registry


settings = get_current_registry().settings


class StorageClient:
    def __init__(self):
        credentials = service_account.Credentials.from_service_account_file(
            settings["gcloud_service_account_key"]
        )
        self.client = storage.Client(credentials=credentials)
        self.bucket = self.client.get_bucket(settings["gcloud_bucket"])

    def upload(self, local: str, remote: str):
        self.bucket.blob(remote).upload_from_filename(local)
    
    def delete(self, remote: str):
        self.bucket.delete_blob(remote)

    def exists(self, remote: str):
        return self.bucket.blob(remote).exists()


@cached(cache={}, key=lambda: "🕉")
def get_storage_client():
    return StorageClient()

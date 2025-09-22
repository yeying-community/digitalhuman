import io
import json
from typing import Any, Dict
from minio import Minio
from minio.error import S3Error

class MinioAdapter:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, secure: bool, bucket: str):
        self.client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        self.bucket = bucket

    def get_json(self, object_name: str) -> Dict[str, Any]:
        try:
            resp = self.client.get_object(self.bucket, object_name)
            data = resp.read()
            resp.close()
            resp.release_conn()
            return json.loads(data.decode("utf-8"))
        except S3Error as e:
            raise FileNotFoundError(f"[MinIO] get_json failed {self.bucket}/{object_name}: {e}")

    def put_json(self, object_name: str, data: Dict[str, Any]) -> None:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        stream = io.BytesIO(payload)
        self.client.put_object(
            self.bucket,
            object_name,
            stream,
            length=len(payload),
            content_type="application/json",
        )

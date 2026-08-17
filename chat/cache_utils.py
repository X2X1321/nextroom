import json
import logging
import os

logger = logging.getLogger(__name__)

# Initialize Upstash REST Client if configured in environment
_upstash_client = None

try:
    from upstash_redis import Redis
    url = (
        os.environ.get('UPSTASH_REDIS_REST_URL')
        or os.environ.get('KV_REST_API_URL')
        or os.environ.get('REDIS_REST_API_URL')
    )
    token = (
        os.environ.get('UPSTASH_REDIS_REST_TOKEN')
        or os.environ.get('KV_REST_API_TOKEN')
        or os.environ.get('REDIS_REST_API_TOKEN')
    )
    if url and token:
        _upstash_client = Redis(url=url, token=token)
    else:
        try:
            _upstash_client = Redis.from_env()
        except Exception:
            _upstash_client = None
except Exception as exc:
    logger.debug("Upstash Redis not initialized from env: %s", exc)
    _upstash_client = None


def get_cache(key, default=None):
    """Retrieve value from Upstash REST Redis or Django Cache fallback."""
    if _upstash_client:
        try:
            val = _upstash_client.get(key)
            if val is not None:
                if isinstance(val, (int, float, bool)):
                    return val
                try:
                    return json.loads(val)
                except (ValueError, TypeError):
                    return val
        except Exception as exc:
            logger.warning("Upstash get error for key %s: %s", key, exc)

    # Fallback to Django cache
    try:
        from django.core.cache import cache
        return cache.get(key, default)
    except Exception:
        return default


def set_cache(key, value, timeout=60):
    """Store value in Upstash REST Redis or Django Cache fallback."""
    if _upstash_client:
        try:
            serialized = value if isinstance(value, (str, int, float, bool)) else json.dumps(value)
            _upstash_client.set(key, serialized, ex=timeout)
            return True
        except Exception as exc:
            logger.warning("Upstash set error for key %s: %s", key, exc)

    # Fallback to Django cache
    try:
        from django.core.cache import cache
        cache.set(key, value, timeout)
        return True
    except Exception:
        return False


def delete_cache(key):
    """Delete value from Upstash REST Redis or Django Cache fallback."""
    if _upstash_client:
        try:
            _upstash_client.delete(key)
        except Exception as exc:
            logger.warning("Upstash delete error for key %s: %s", key, exc)

    # Fallback to Django cache
    try:
        from django.core.cache import cache
        cache.delete(key)
        return True
    except Exception:
        return False


def get_user_avatar(user_id):
    """Get cached user avatar URL from Redis to avoid database queries in chat."""
    if not user_id:
        return None
    key = f"user_avatar_{user_id}"
    return get_cache(key, None)


def set_user_avatar(user_id, avatar_url, timeout=86400):
    """Cache user avatar URL in Redis for 24 hours."""
    if not user_id or not avatar_url:
        return False
    key = f"user_avatar_{user_id}"
    return set_cache(key, avatar_url, timeout=timeout)


def invalidate_user_avatar(user_id):
    """Invalidate cached user avatar URL."""
    if not user_id:
        return False
    key = f"user_avatar_{user_id}"
    return delete_cache(key)


def upload_file_to_yandex_s3(folder, filename, file_bytes, content_type='application/octet-stream'):
    """
    Directly upload any file bytes (images, voices, generated images, exports) to Yandex Cloud Object Storage.
    Returns the public direct S3 URL or None if S3 is not configured / fallback needed.
    """
    from django.conf import settings
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    s3_key = getattr(settings, 'AWS_ACCESS_KEY_ID', None)
    s3_secret = getattr(settings, 'AWS_SECRET_ACCESS_KEY', None)
    s3_bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)

    file_key = f"{folder.strip('/')}/{filename.lstrip('/')}"

    if s3_key and s3_secret and s3_bucket:
        try:
            import boto3
            endpoint = getattr(settings, 'AWS_S3_ENDPOINT_URL', 'https://storage.yandexcloud.net')
            region = getattr(settings, 'AWS_S3_REGION_NAME', 'ru-central1')

            s3 = boto3.client(
                's3',
                aws_access_key_id=s3_key,
                aws_secret_access_key=s3_secret,
                endpoint_url=endpoint,
                region_name=region
            )

            s3.put_object(
                Bucket=s3_bucket,
                Key=file_key,
                Body=file_bytes,
                ContentType=content_type,
                ACL='public-read',
                CacheControl='max-age=31536000, public'
            )

            custom_domain = getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', None)
            if custom_domain:
                return f"https://{custom_domain}/{file_key}"
            clean_endpoint = endpoint.rstrip('/')
            return f"{clean_endpoint}/{s3_bucket}/{file_key}"
        except Exception as exc:
            logger.warning("Boto3 direct upload to Yandex S3 failed for %s: %s", file_key, exc)

    try:
        saved_path = default_storage.save(file_key, ContentFile(file_bytes))
        return default_storage.url(saved_path)
    except Exception as exc:
        logger.warning("default_storage save failed for %s: %s", file_key, exc)
        return None


def upload_avatar_to_yandex_s3(username, image_bytes, ext='jpg', content_type='image/jpeg'):
    """Upload processed avatar to Yandex Cloud Object Storage."""
    import uuid
    filename = f"{username}_{uuid.uuid4().hex[:8]}.{ext}"
    return upload_file_to_yandex_s3('avatars', filename, image_bytes, content_type=content_type)


def get_room_messages_cache(slug):
    """Retrieve cached recent messages for room."""
    return get_cache(f"room_msgs_{slug}", None)


def set_room_messages_cache(slug, messages_data, timeout=30):
    """Cache recent messages for room in Redis."""
    return set_cache(f"room_msgs_{slug}", messages_data, timeout=timeout)


def invalidate_room_messages_cache(slug):
    """Invalidate cached recent messages for room."""
    delete_cache(f"room_msgs_{slug}")
    delete_cache(f"room_stats_{slug}")
    delete_cache('dashboard_total_messages')
    delete_cache('landing_page_stats')


def get_room_stats_cache(slug):
    """Retrieve cached room statistics."""
    return get_cache(f"room_stats_{slug}", None)


def set_room_stats_cache(slug, stats_data, timeout=60):
    """Cache room statistics."""
    return set_cache(f"room_stats_{slug}", stats_data, timeout=timeout)


def invalidate_dashboard_stats():
    """Invalidate all dashboard and landing statistics caches."""
    delete_cache('dashboard_total_rooms')
    delete_cache('dashboard_total_messages')
    delete_cache('landing_page_stats')

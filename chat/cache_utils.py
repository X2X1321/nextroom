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

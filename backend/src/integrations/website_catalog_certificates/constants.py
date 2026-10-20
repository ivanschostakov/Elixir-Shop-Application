import re


MAX_CERTIFICATE_SIZE_BYTES = 100 * 1024 * 1024
_SAFE_EXTENSION = re.compile(r"^\.[a-z0-9]{1,10}$")
_CONTENT_TYPE_EXTENSIONS = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
_PUBLIC_PATH_PREFIX = "/media/product-certificates/"
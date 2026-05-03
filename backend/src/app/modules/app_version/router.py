from fastapi import APIRouter
from starlette import status

from config import (
    ANDROID_LATEST_JS_BUNDLE_VERSION,
    ANDROID_LATEST_VERSION_CODE,
    ANDROID_MINIMUM_JS_BUNDLE_VERSION,
    ANDROID_MINIMUM_VERSION_CODE,
    ANDROID_STORE_URL,
    IOS_LATEST_BUILD,
    IOS_LATEST_JS_BUNDLE_VERSION,
    IOS_MINIMUM_BUILD,
    IOS_MINIMUM_JS_BUNDLE_VERSION,
    IOS_STORE_URL,
)
from .schemas import AppVersionPolicyRead

app_version_router = APIRouter(prefix="/app-version", tags=["app_version"])


@app_version_router.get("", response_model=AppVersionPolicyRead, status_code=status.HTTP_200_OK)
async def get_app_version_policy() -> AppVersionPolicyRead:
    return AppVersionPolicyRead(
        ios={
            "minimumBuild": IOS_MINIMUM_BUILD,
            "latestBuild": IOS_LATEST_BUILD,
            "minimumJsBundleVersion": IOS_MINIMUM_JS_BUNDLE_VERSION,
            "latestJsBundleVersion": IOS_LATEST_JS_BUNDLE_VERSION,
            "storeUrl": IOS_STORE_URL or "",
        },
        android={
            "minimumVersionCode": ANDROID_MINIMUM_VERSION_CODE,
            "latestVersionCode": ANDROID_LATEST_VERSION_CODE,
            "minimumJsBundleVersion": ANDROID_MINIMUM_JS_BUNDLE_VERSION,
            "latestJsBundleVersion": ANDROID_LATEST_JS_BUNDLE_VERSION,
            "storeUrl": ANDROID_STORE_URL or "",
        },
    )

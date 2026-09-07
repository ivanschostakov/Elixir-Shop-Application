from pydantic import BaseModel, Field


class IosAppVersionPolicyRead(BaseModel):
    minimumBuild: int = Field(ge=1)
    latestBuild: int = Field(ge=1)
    minimumJsBundleVersion: int = Field(ge=1)
    latestJsBundleVersion: int = Field(ge=1)
    storeUrl: str


class AndroidAppVersionPolicyRead(BaseModel):
    minimumVersionCode: int = Field(ge=1)
    latestVersionCode: int = Field(ge=1)
    minimumJsBundleVersion: int = Field(ge=1)
    latestJsBundleVersion: int = Field(ge=1)
    storeUrl: str


class AppVersionPolicyRead(BaseModel):
    ios: IosAppVersionPolicyRead
    android: AndroidAppVersionPolicyRead

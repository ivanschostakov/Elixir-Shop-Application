from fastapi.testclient import TestClient


def test_app_version_policy_returns_defaults(client: TestClient):
    response = client.get("/api/v1/app-version")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload == {
        "ios": {
            "minimumBuild": 1,
            "latestBuild": 1,
            "minimumJsBundleVersion": 1,
            "latestJsBundleVersion": 1,
            "storeUrl": "",
        },
        "android": {
            "minimumVersionCode": 1,
            "latestVersionCode": 1,
            "minimumJsBundleVersion": 1,
            "latestJsBundleVersion": 1,
            "storeUrl": "",
        },
    }


def test_app_version_policy_uses_parsed_config_values(client: TestClient, monkeypatch):
    import src.app.modules.app_version.router as app_version_router_module

    monkeypatch.setattr(app_version_router_module, "IOS_MINIMUM_BUILD", 12)
    monkeypatch.setattr(app_version_router_module, "IOS_LATEST_BUILD", 15)
    monkeypatch.setattr(app_version_router_module, "IOS_MINIMUM_JS_BUNDLE_VERSION", 4)
    monkeypatch.setattr(app_version_router_module, "IOS_LATEST_JS_BUNDLE_VERSION", 5)
    monkeypatch.setattr(app_version_router_module, "IOS_STORE_URL", "https://apps.apple.com/app/example")
    monkeypatch.setattr(app_version_router_module, "ANDROID_MINIMUM_VERSION_CODE", 20)
    monkeypatch.setattr(app_version_router_module, "ANDROID_LATEST_VERSION_CODE", 23)
    monkeypatch.setattr(app_version_router_module, "ANDROID_MINIMUM_JS_BUNDLE_VERSION", 6)
    monkeypatch.setattr(app_version_router_module, "ANDROID_LATEST_JS_BUNDLE_VERSION", 7)
    monkeypatch.setattr(app_version_router_module, "ANDROID_STORE_URL", "https://play.google.com/store/apps/details?id=example")

    response = client.get("/api/v1/app-version")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ios"]["minimumBuild"] == 12
    assert payload["ios"]["latestBuild"] == 15
    assert payload["ios"]["minimumJsBundleVersion"] == 4
    assert payload["ios"]["latestJsBundleVersion"] == 5
    assert payload["ios"]["storeUrl"] == "https://apps.apple.com/app/example"
    assert payload["android"]["minimumVersionCode"] == 20
    assert payload["android"]["latestVersionCode"] == 23
    assert payload["android"]["minimumJsBundleVersion"] == 6
    assert payload["android"]["latestJsBundleVersion"] == 7
    assert payload["android"]["storeUrl"] == "https://play.google.com/store/apps/details?id=example"

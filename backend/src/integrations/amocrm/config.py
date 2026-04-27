class AmoCRMConfig(BaseModel):

    model_config = ConfigDict(arbitrary_types_allowed=True)

    base_domain: str = Field(default=AMOCRM_BASE_DOMAIN or "")

    client_id: str | None = AMOCRM_CLIENT_ID

    client_secret: str | None = AMOCRM_CLIENT_SECRET

    redirect_uri: str | None = AMOCRM_REDIRECT_URI

    access_token: str | None = AMOCRM_ACCESS_TOKEN

    refresh_token: str | None = AMOCRM_REFRESH_TOKEN

    auth_code: str | None = AMOCRM_AUTH_CODE

    login_email: str | None = AMOCRM_LOGIN_EMAIL

    login_password: str | None = AMOCRM_LOGIN_PASSWORD

    account_id: str | None = AMOCRM_ACCOUNT_ID

    playwright_headless: bool = AMOCRM_PLAYWRIGHT_HEADLESS

    env_path: Path = WORKING_DIR / ".env"

    @property

    def normalized_base_domain(self) -> str:

        return self.base_domain.strip()

    @property

    def normalized_auth_code(self) -> str | None:

        return (self.auth_code or "").strip() or None

    @property

    def normalized_login_email(self) -> str | None:

        return (self.login_email or "").strip() or None

    @property

    def normalized_account_id(self) -> str | None:

        return (self.account_id or "").strip() or None
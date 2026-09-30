from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.database.mixins import IdPkMixin, TimestampMixin


class CommunityAuthorBlock(Base, IdPkMixin, TimestampMixin):
    __tablename__ = "community_author_blocks"
    __table_args__ = (UniqueConstraint("user_id", "author_id", name="uq_community_author_blocks_user_author"),)

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("community_authors.id", ondelete="CASCADE"), index=True)

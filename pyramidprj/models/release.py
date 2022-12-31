from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    JSON,
    Text,
)

from sqlalchemy.orm import (
    relationship,
)

from .meta import Base


class Release(Base):
    __tablename__ = 'release'
    id = Column(Integer, primary_key=True)
    catalog_no = Column(Text)
    release_dir = Column(Text)
    file = Column(Text)
    external_urls = Column(JSON)

    index_record_id = Column(Integer, ForeignKey("index_record.id"))
    index_record = relationship("IndexRecord", back_populates="releases")

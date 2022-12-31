import codecs

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    JSON,
    Table,
    Text,
)

from sqlalchemy.orm import (
    relationship,
)

from .meta import Base


index_record_releases = Table(
    "index_record_releases",
    Base.metadata,
    Column("left_id", ForeignKey("index_record.id"), primary_key=True),
    Column("right_id", ForeignKey("release.id"), primary_key=True),
)


class IndexRecord(Base):
    __tablename__ = 'index_record'
    id = Column(Integer, primary_key=True)
    date = Column(Text)
    body = Column(Text)
    explicit_height = Column(Integer)
    custom_date_section = Column(Text)

    releases = relationship("Release", secondary=index_record_releases, back_populates="index_records")


class Release(Base):
    __tablename__ = 'release'
    id = Column(Integer, primary_key=True)
    catalog_no = Column(Text)
    release_dir = Column(Text)
    file = Column(Text)
    external_urls = Column(JSON)

    index_records = relationship("IndexRecord", secondary=index_record_releases, back_populates="releases")

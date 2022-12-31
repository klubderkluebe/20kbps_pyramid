from sqlalchemy import (
    Column,
    Integer,
    Text,
)

from sqlalchemy.orm import (
    relationship,
)

from .meta import Base


class IndexRecord(Base):
    __tablename__ = 'index_record'
    id = Column(Integer, primary_key=True)
    date = Column(Text)
    body = Column(Text)
    explicit_height = Column(Integer)
    custom_date_section = Column(Text)

    releases = relationship("Release", back_populates="index_record")

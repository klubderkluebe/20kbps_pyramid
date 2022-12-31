from sqlalchemy import (
    Column,
    Integer,
    Text,
)

from .meta import Base


class IndexRecord(Base):
    __tablename__ = 'index_record'
    id = Column(Integer, primary_key=True)
    date = Column(Text)
    body = Column(Text)
    explicit_height = Column(Integer)
    custom_date_section = Column(Text)

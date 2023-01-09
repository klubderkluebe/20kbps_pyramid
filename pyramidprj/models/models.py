import typing as t

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

from bs4 import BeautifulSoup


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
    release_data = Column(JSON)

    index_records = relationship("IndexRecord", secondary=index_record_releases, back_populates="releases")
    release_page = relationship("ReleasePage", back_populates="release", uselist=False)


class ReleasePage(Base):
    __tablename__ = "release_page"
    id = Column(Integer, primary_key=True)

    content = Column(Text,
        comment="Page content to be embedded in layout. Imported from pr-text.inc.php."
    )

    custom_body = Column(Text,
        comment="Full page content for the release pages that have an index.html."
    )

    release_id = Column(Integer, ForeignKey("release.id"))
    release = relationship("Release", back_populates="release_page")

    player_files = relationship("PlayerFile", back_populates="release_page")

    custom_tracklist = Column(Text,
        comment="Some releases have a list.inc.php file."
    )

    @property
    def content_text(self):
        html = t.cast(str, self.content or self.custom_body)
        soup = BeautifulSoup(html, "html5lib")
        return soup.text


class PlayerFile(Base):
    __tablename__ = "player_file"
    id = Column(Integer, primary_key=True)
    file = Column(Text)
    number = Column(Integer)
    title = Column(Text)
    duration_secs = Column(Integer)

    release_page_id = Column(Integer, ForeignKey("release_page.id"))
    release_page = relationship("ReleasePage", back_populates="player_files")

    @property
    def _duration_tuple(self):
        if self.duration_secs is None:
            return None

        secs = t.cast(int, self.duration_secs)
        h = secs // 3600
        m = (secs - 3600 * h) // 60
        s = secs - 3600 * h - 60 * m
        return [h, m, s]

    @property
    def duration_iso8601(self) -> str:
        hms = self._duration_tuple
        if hms is None:
            return ""

        ifst = 0 if hms[0] else 1
        return "PT" + "".join(f"{x}{c}" for x, c in zip(hms[ifst:], ["H", "M", "S"][ifst:]))

    @property
    def duration(self) -> str:
        hms = self._duration_tuple
        if hms is None:
            return ""

        ifst = 0 if hms[0] else 1
        return ":".join(f"{x:02}" for x in hms[ifst:])

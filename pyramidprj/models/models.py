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
    """An IndexRecord corresponds to an entry on the index page (index2.htm).

    The relation to the `Release` table is 1:N because some legacy entries refer to multiple releases.
    The admin interface enforces that an IndexRecord is associated with only one release though.

    :param date: Date field. Arbitrary text to accommodate inconsistencies in legacy data.
    :param body: HTML content to be displayed for this record
    :param explicit_height: When set, the element's height is set explicitly using a `height` attribute.
    :param custom_date_section: To allow for arbitrary HTML in the date field. Overrides `date` when present.
    """
    __tablename__ = 'index_record'
    id = Column(Integer, primary_key=True)
    date = Column(Text)
    body = Column(Text)
    explicit_height = Column(Integer)
    custom_date_section = Column(Text)

    releases = relationship("Release", secondary=index_record_releases, back_populates="index_records")

    @property
    def body_text(self):
        """Get the body as plain text. Used in the admin interface only.
        """
        html = t.cast(str, self.body)
        return BeautifulSoup(html, "html5lib").text


class Release(Base):
    """A release with a catalog number, a downloadable zip file, and metadata.

    :param catalog_no: '20kxxx'. Arbitrary text to accommodate inconsistencies in legacy data.

    :param release_dir: The release directory relative to `Releases/`. Can be nested, e.g.
        `matri-oxar/tiholaz-playing-the-piano-for-five-minutes`. The release directory
        contains the individual audio files and the cover.

    :param file: The name of the downloadable zip file. Without path, as these are all directly
        under `Releases/`.

    :param release_data: Arbitrary JSON metadata. There are some keys that originate from legacy 20kbps
        and are expected to be present. These are: `relname`, `artist`, `cat-no`, `description`, `list`, `date`.
        Sample release data:
            {
                "relname": "morrisx",
                "artist": "The Hardliner",
                "cat-no": "20k376",
                "description": "The Hardliner - morrisx (20k376)",
                "list": "ol",
                "date": "2023-06-21",
                "archive": "https://archive.org/details/20k376",
                "discogs": "https://www.discogs.com/release/27448467-The-Hardliner-morrisx"
            }
        The `list` key controls which HTML tag is used to render the track list (`ol` or `ul`).
        When creating a release using the admin interface, `release_data` is pre-filled with sane values.

    :param release_page: A release is associated with a release page, i.e. the detail page that displays the
        cover, description, and HTML player elements. Many legacy releases do not have a release page (so the
        only place where they can be seen is index2.htm). The admin interface enforces that a release page is
        created, so any new release will have a release page.
    """
    __tablename__ = 'release'
    id = Column(Integer, primary_key=True)
    catalog_no = Column(Text)
    release_dir = Column(Text)
    file = Column(Text)
    release_data = Column(JSON)

    index_records = relationship("IndexRecord", secondary=index_record_releases, back_populates="releases")
    release_page = relationship("ReleasePage", back_populates="release", uselist=False)


class ReleasePage(Base):
    """A detail page that displays a release's cover, description, and HTML player elements.

    :param custom_tracklist: Under normal circumstances, the tracklist is rendered from the associated
        `player_files`. Some legacy releases have a `list.inc.php` file that is displayed instead of the
        dynamic tracklist. This concerns legacy releases only and is not used with new releases.
    """
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
        """Get the page content as plain text. This is used in the description field when uploading the release
        to archive.org.
        """
        html = t.cast(str, self.custom_body or self.content)
        return BeautifulSoup(html, "html5lib").text


class PlayerFile(Base):
    """An individual audio file associated with a release.

    :param file: Name of the audio file inside the release directory (=`self.release_page.release.release_dir`)
    :param number: Track number in tracklist
    """
    __tablename__ = "player_file"
    id = Column(Integer, primary_key=True)
    file = Column(Text)
    number = Column(Integer)
    title = Column(Text)
    duration_secs = Column(Integer)

    release_page_id = Column(Integer, ForeignKey("release_page.id"))
    release_page = relationship("ReleasePage", back_populates="player_files")

    @staticmethod
    def _get_duration_tuple(secs: int) -> t.List[int]:
        h = secs // 3600
        m = (secs - 3600 * h) // 60
        s = secs - 3600 * h - 60 * m
        return [h, m, s]

    @staticmethod
    def show_duration_iso8601(secs: int) -> str:
        hms = PlayerFile._get_duration_tuple(secs)
        ifst = 0 if hms[0] else 1
        return "PT" + "".join(f"{x}{c}" for x, c in zip(hms[ifst:], ["H", "M", "S"][ifst:]))

    @staticmethod
    def show_duration(secs: int) -> str:
        hms = PlayerFile._get_duration_tuple(secs)
        ifst = 0 if hms[0] else 1
        return ":".join(f"{x:02}" for x in hms[ifst:])

    @property
    def _duration_tuple(self):
        if self.duration_secs is None:
            return None
        return PlayerFile._get_duration_tuple(t.cast(int, self.duration_secs))

    @property
    def duration_iso8601(self) -> str:
        """Get duration as ISO 8601 time string. Used in the `datetime` attribute of the `time` HTML tag
        when rendering the tracklist.
        """
        if self.duration_secs is None:
            return ""
        return PlayerFile.show_duration_iso8601(t.cast(int, self.duration_secs))

    @property
    def duration(self) -> str:
        """Get duration in `HH:MM:SS` format. The `HH` part is omitted when duration is below one hour.
        The `MM` part is always shown, even when duration is below one minute."""
        if self.duration_secs is None:
            return ""
        return PlayerFile.show_duration(t.cast(int, self.duration_secs))

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Any, Protocol

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .config import Settings
from .constants import SHEET_HEADERS


class Store(Protocol):
    def all(self, sheet: str) -> list[dict[str, str]]: ...
    def append(self, sheet: str, record: dict[str, Any]) -> None: ...
    def append_many(self, sheet: str, records: list[dict[str, Any]]) -> None: ...
    def update(self, sheet: str, key: str, value: str, changes: dict[str, Any]) -> bool: ...
    def find(self, sheet: str, key: str, value: str) -> dict[str, str] | None: ...


@dataclass
class GoogleSheetStore:
    settings: Settings

    def __post_init__(self) -> None:
        # google-api-python-client's httplib2 transport is not thread-safe.
        # FastAPI serves requests concurrently, so all calls through this
        # shared client must be serialised.
        self.operation_lock = RLock()
        self._cache: dict[str, tuple[float, list[dict[str, str]]]] = {}
        self._cache_seconds = 8.0
        credentials = Credentials(
            token=None,
            refresh_token=self.settings.google_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.settings.google_client_id,
            client_secret=self.settings.google_client_secret,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        self.service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        self.sheet_id = self.settings.google_spreadsheet_id

    def all(self, sheet: str) -> list[dict[str, str]]:
        with self.operation_lock:
            cached = self._cache.get(sheet)
            if cached and monotonic() - cached[0] < self._cache_seconds:
                return [row.copy() for row in cached[1]]
            headers = SHEET_HEADERS[sheet]
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id, range=f"'{sheet}'!A2:{_column(len(headers))}"
            ).execute(num_retries=2)
            rows = [
                dict(zip(headers, [str(v) for v in row] + [""] * (len(headers) - len(row))))
                for row in result.get("values", [])
                if any(str(v).strip() for v in row)
            ]
            self._cache[sheet] = (monotonic(), rows)
            return [row.copy() for row in rows]

    def find(self, sheet: str, key: str, value: str) -> dict[str, str] | None:
        wanted = value.casefold() if key == "email" else value
        for record in self.all(sheet):
            current = record.get(key, "")
            if (current.casefold() if key == "email" else current) == wanted:
                return record
        return None

    def append(self, sheet: str, record: dict[str, Any]) -> None:
        self.append_many(sheet, [record])

    def append_many(self, sheet: str, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        headers = SHEET_HEADERS[sheet]
        rows = [[_cell(record.get(header, "")) for header in headers] for record in records]
        with self.operation_lock:
            self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range=f"'{sheet}'!A:{_column(len(headers))}",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": rows},
            ).execute(num_retries=2)
            self._cache.pop(sheet, None)

    def update(self, sheet: str, key: str, value: str, changes: dict[str, Any]) -> bool:
        with self.operation_lock:
            headers = SHEET_HEADERS[sheet]
            if key not in headers:
                raise KeyError(key)
            rows = self.all(sheet)
            wanted = value.casefold() if key == "email" else value
            for index, record in enumerate(rows, start=2):
                current = record.get(key, "")
                if (current.casefold() if key == "email" else current) != wanted:
                    continue
                record.update({name: _cell(item) for name, item in changes.items() if name in headers})
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.sheet_id,
                    range=f"'{sheet}'!A{index}:{_column(len(headers))}{index}",
                    valueInputOption="RAW",
                    body={"values": [[record.get(header, "") for header in headers]]},
                ).execute(num_retries=2)
                self._cache.pop(sheet, None)
                return True
            return False

    def set_result_hyperlinks(self, submission_id: str, urls: list[str]) -> None:
        with self.operation_lock:
            headers = SHEET_HEADERS["Results"]
            rows = self.all("Results")
            row_number = next((i for i, row in enumerate(rows, 2)
                               if row.get("submission_id") == submission_id), None)
            if row_number is None:
                return
            data=[]
            for number, url in enumerate(urls, 1):
                column = _column(headers.index(f"audio_{number}_play") + 1)
                safe = url.replace('"', '""')
                data.append({"range": f"'Results'!{column}{row_number}",
                             "values": [[f'=HYPERLINK("{safe}","Play answer {number}")']]})
            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.sheet_id,
                body={"valueInputOption": "USER_ENTERED", "data": data},
            ).execute(num_retries=2)
            self._cache.pop("Results", None)


class MemoryStore:
    """Test/local store. Production refuses to start without Google configuration."""

    def __init__(self) -> None:
        self.operation_lock = RLock()
        self.data = {name: [] for name in SHEET_HEADERS}

    def all(self, sheet: str) -> list[dict[str, str]]:
        return [row.copy() for row in self.data[sheet]]

    def find(self, sheet: str, key: str, value: str) -> dict[str, str] | None:
        wanted = value.casefold() if key == "email" else value
        for row in self.data[sheet]:
            current = row.get(key, "")
            if (current.casefold() if key == "email" else current) == wanted:
                return row.copy()
        return None

    def append(self, sheet: str, record: dict[str, Any]) -> None:
        self.data[sheet].append({h: _cell(record.get(h, "")) for h in SHEET_HEADERS[sheet]})

    def append_many(self, sheet: str, records: list[dict[str, Any]]) -> None:
        for record in records:
            self.append(sheet, record)

    def update(self, sheet: str, key: str, value: str, changes: dict[str, Any]) -> bool:
        wanted = value.casefold() if key == "email" else value
        for row in self.data[sheet]:
            current = row.get(key, "")
            if (current.casefold() if key == "email" else current) == wanted:
                row.update({k: _cell(v) for k, v in changes.items() if k in SHEET_HEADERS[sheet]})
                return True
        return False


def _cell(value: Any) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return "" if value is None else str(value)


def _column(number: int) -> str:
    answer = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        answer = chr(65 + remainder) + answer
    return answer

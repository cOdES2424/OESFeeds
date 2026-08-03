import hashlib
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://apps.occ.ok.gov"
LOGIN_URL = f"{BASE_URL}/PSTPortal/Account/Login"
SEARCH_URL = f"{BASE_URL}/PSTPortal/PublicImaging/Home"
FEED_FILENAME = "violation_search_feed.xml"
STATUS_GUID = "occ-violation-search-no-results-status"
KEYWORDS = ("NOV", "NOCR", "SOR")

MAX_PAGES = 25
EMPTY_PAGE_RETRIES = 2
REQUEST_FAILURE_RETRIES = 3
MAX_CONSECUTIVE_EMPTY_PAGES = 3

TEST_DATE_RAW = os.getenv("TEST_DATE", "").strip()
TEST_MODE = bool(TEST_DATE_RAW)

STATS = {
    "pages_requested": 0,
    "valid_table_pages": 0,
    "rows_examined": 0,
    "matching_rows": 0,
    "duplicates_removed": 0,
    "request_retries": 0,
    "blank_page_retries": 0,
    "skipped_pages": 0,
}


def parse_search_date(value):
    """Accept MM/DD/YYYY or YYYY-MM-DD and return a date."""
    value = value.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(
        f"Invalid TEST_DATE {value!r}. Use MM/DD/YYYY or YYYY-MM-DD."
    )


def get_search_date():
    if TEST_MODE:
        return parse_search_date(TEST_DATE_RAW)
    return datetime.now().date() - timedelta(days=14)


def login(session):
    login_page = session.get(LOGIN_URL, timeout=(20, 90))
    login_page.raise_for_status()
    soup = BeautifulSoup(login_page.content, "html.parser")

    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")
    if not username or not password:
        raise ValueError("USERNAME and PASSWORD environment variables are required.")

    login_data = {
        "UserName": username,
        "Password": password,
    }

    for hidden_input in soup.find_all("input", type="hidden"):
        name = hidden_input.get("name")
        if name:
            login_data[name] = hidden_input.get("value", "")

    print(f"Submitting OCC login for user: {username!r}", flush=True)
    response = session.post(LOGIN_URL, data=login_data, timeout=(20, 90))
    response.raise_for_status()

    response_soup = BeautifulSoup(response.content, "html.parser")
    password_field = response_soup.find("input", {"type": "password"})
    still_on_login_url = "/Account/Login" in response.url
    if still_on_login_url or password_field is not None:
        validation = response_soup.select_one(
            ".validation-summary-errors, .text-danger"
        )
        detail = (
            validation.get_text(" ", strip=True)
            if validation
            else "The login form was returned."
        )
        raise ValueError(f"Login failed: {detail}")

    print(f"Logged in successfully; redirected to {response.url}", flush=True)
    return session


def build_search_url(search_date, page_number):
    formatted_date = search_date.strftime("%m/%d/%Y")
    encoded_date = urllib.parse.quote(formatted_date)
    return (
        f"{SEARCH_URL}?indexName=DateRange"
        f"&DateRangeFrom={encoded_date}&DateRangeTo={encoded_date}"
        f"&btnSubmitDateSearch=Search+by+Date+Range"
        f"&pageNumber={page_number}"
    )


def request_search_page(session, search_date, page_number, attempt):
    url = build_search_url(search_date, page_number)
    STATS["pages_requested"] += 1
    print(f"Navigating to page {page_number} (attempt {attempt})", flush=True)

    try:
        response = session.get(url, timeout=(20, 90))
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
        print(
            f"Page {page_number} request failed on attempt {attempt}: "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )
        return None

    response_soup = BeautifulSoup(response.content, "html.parser")
    login_form = response_soup.find(
        "form", action=lambda value: value and "/Account/Login" in value
    )
    if "/Account/Login" in response.url or login_form is not None:
        print("Session expired; logging in again...", flush=True)
        login(session)
        try:
            response = session.get(url, timeout=(20, 90))
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            print(
                f"Page {page_number} request failed after re-login: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
            return None

    if response.status_code != 200:
        print(
            f"Page {page_number} returned HTTP {response.status_code}.",
            flush=True,
        )
        return None

    print(
        f"Navigated to page {page_number}; received "
        f"{len(response.content):,} bytes",
        flush=True,
    )
    return response


def parse_search_page(response, page_number):
    soup = BeautifulSoup(response.content, "html.parser")
    table = soup.find("table", {"id": "tablePublicImagingSearchResults"})
    print(f"Table found on page {page_number}: {table is not None}", flush=True)

    if table is None:
        return [], None

    STATS["valid_table_pages"] += 1
    tbody = table.find("tbody")
    rows = tbody.find_all("tr", recursive=False) if tbody else []
    row_count = len(rows)
    STATS["rows_examined"] += row_count
    print(f"Rows returned on page {page_number}: {row_count}", flush=True)

    results = []
    for row in rows:
        columns = row.find_all("td", recursive=False)
        if len(columns) < 6:
            print(
                f"Skipping unexpected row with {len(columns)} columns.",
                flush=True,
            )
            continue

        description = columns[3].get_text(" ", strip=True)
        if not any(keyword in description.upper() for keyword in KEYWORDS):
            continue

        details_anchor = columns[0].find("a", href=True)
        details_url = (
            urljoin(response.url, details_anchor["href"])
            if details_anchor
            else response.url
        )

        results.append(
            {
                "id": columns[1].get_text(" ", strip=True),
                "facility_id": columns[2].get_text(" ", strip=True),
                "description": description,
                "date": columns[5].get_text(" ", strip=True),
                "link": details_url,
            }
        )

    STATS["matching_rows"] += len(results)
    return results, row_count


def scrape_all_pages(session, search_date):
    all_results = []
    seen_ids = set()
    consecutive_empty_pages = 0

    for page in range(MAX_PAGES):
        page_results = []
        row_count = None
        blank_attempts = 0
        request_failures = 0
        attempt = 0

        while True:
            attempt += 1
            response = request_search_page(session, search_date, page, attempt)

            if response is None:
                request_failures += 1
                if request_failures > REQUEST_FAILURE_RETRIES:
                    STATS["skipped_pages"] += 1
                    print(
                        f"Page {page} could not be retrieved after "
                        f"{REQUEST_FAILURE_RETRIES + 1} attempts; skipping it "
                        "without counting it as blank.",
                        flush=True,
                    )
                    break

                STATS["request_retries"] += 1
                delay = min(10 * request_failures, 30)
                print(
                    f"Waiting {delay} seconds before retrying page {page} "
                    f"after a request failure "
                    f"({request_failures}/{REQUEST_FAILURE_RETRIES}).",
                    flush=True,
                )
                time.sleep(delay)
                continue

            page_results, row_count = parse_search_page(response, page)

            if row_count is None:
                request_failures += 1
                if request_failures > REQUEST_FAILURE_RETRIES:
                    STATS["skipped_pages"] += 1
                    print(
                        f"Page {page} never returned a recognizable results table; "
                        "skipping it without counting it as blank.",
                        flush=True,
                    )
                    break

                STATS["request_retries"] += 1
                delay = min(10 * request_failures, 30)
                print(
                    f"Waiting {delay} seconds before retrying page {page} "
                    "because the results table was missing.",
                    flush=True,
                )
                time.sleep(delay)
                continue

            if row_count > 0:
                break

            blank_attempts += 1
            if blank_attempts > EMPTY_PAGE_RETRIES:
                break

            STATS["blank_page_retries"] += 1
            print(
                f"Page {page} was blank; waiting and retrying "
                f"({blank_attempts}/{EMPTY_PAGE_RETRIES}).",
                flush=True,
            )
            time.sleep(4)

        for entry in page_results:
            if entry["id"] in seen_ids:
                STATS["duplicates_removed"] += 1
                continue
            seen_ids.add(entry["id"])
            all_results.append(entry)

        if row_count is None:
            print(
                f"Page {page} was skipped; blank-page counter remains at "
                f"{consecutive_empty_pages}.",
                flush=True,
            )
        elif row_count == 0:
            consecutive_empty_pages += 1
            print(
                f"Page {page} remained blank after retries. Consecutive blank "
                f"pages: {consecutive_empty_pages}/"
                f"{MAX_CONSECUTIVE_EMPTY_PAGES}",
                flush=True,
            )
            if consecutive_empty_pages >= MAX_CONSECUTIVE_EMPTY_PAGES:
                print("Blank-page threshold reached; stopping pagination.", flush=True)
                break
        else:
            consecutive_empty_pages = 0

        time.sleep(2)

    return all_results


def parse_entry_date(value):
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    print(
        f"Warning: could not parse document date {value!r}; using current time.",
        flush=True,
    )
    return datetime.now(timezone.utc)


def read_previous_status_dates(feed_path):
    if not os.path.exists(feed_path):
        return set()

    try:
        root = ET.parse(feed_path).getroot()
    except (ET.ParseError, OSError) as exc:
        print(f"Could not read prior RSS status: {exc}", flush=True)
        return set()

    for item in root.findall("./channel/item"):
        guid = item.findtext("guid", default="").strip()
        if guid != STATUS_GUID:
            continue

        description = item.findtext("description", default="")
        return {
            datetime.strptime(value, "%Y-%m-%d").date()
            for value in re.findall(r"\b\d{4}-\d{2}-\d{2}\b", description)
        }

    return set()


def format_date_ranges(dates):
    ordered = sorted(dates)
    if not ordered:
        return ""

    ranges = []
    start = previous = ordered[0]

    for current in ordered[1:]:
        if current == previous + timedelta(days=1):
            previous = current
            continue
        ranges.append((start, previous))
        start = previous = current

    ranges.append((start, previous))

    formatted = []
    for range_start, range_end in ranges:
        if range_start == range_end:
            formatted.append(range_start.strftime("%B %-d, %Y"))
        elif range_start.year == range_end.year and range_start.month == range_end.month:
            formatted.append(
                f"{range_start.strftime('%B')} {range_start.day}–"
                f"{range_end.day}, {range_end.year}"
            )
        else:
            formatted.append(
                f"{range_start.strftime('%B %-d, %Y')}–"
                f"{range_end.strftime('%B %-d, %Y')}"
            )
    return "; ".join(formatted)


def add_result_item(channel, entry):
    item = ET.SubElement(channel, "item")
    text = f"{entry['id']} - {entry['description']} - {entry['date']}"
    ET.SubElement(item, "title").text = text
    ET.SubElement(item, "link").text = entry["link"]
    ET.SubElement(item, "description").text = text
    guid = hashlib.md5(text.encode()).hexdigest()
    ET.SubElement(item, "guid", isPermaLink="false").text = guid
    ET.SubElement(item, "pubDate").text = parse_entry_date(entry["date"]).strftime(
        "%a, %d %b %Y %H:%M:%S %z"
    )


def add_status_item(channel, checked_dates):
    date_ranges = format_date_ranges(checked_dates)
    iso_dates = ", ".join(value.isoformat() for value in sorted(checked_dates))

    item = ET.SubElement(channel, "item")
    ET.SubElement(item, "title").text = (
        "Status: OCC database accessed successfully — no new violation records"
    )
    ET.SubElement(item, "link").text = SEARCH_URL
    ET.SubElement(item, "description").text = (
        "The OCC database was successfully accessed, but no NOV, NOCR, or SOR "
        f"records were found for: {date_ranges}.\n\n"
        f"Checked dates: {iso_dates}"
    )
    ET.SubElement(item, "guid", isPermaLink="false").text = STATUS_GUID
    ET.SubElement(item, "pubDate").text = datetime.now(timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S %z"
    )


def write_feed(feed_path, results, search_date):
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Violation Search Feed"
    ET.SubElement(channel, "link").text = SEARCH_URL
    ET.SubElement(channel, "description").text = (
        "Feed of violations from the Oklahoma Corporation Commission"
    )
    ET.SubElement(channel, "language").text = "en-US"
    ET.SubElement(channel, "lastBuildDate").text = datetime.now(
        timezone.utc
    ).strftime("%a, %d %b %Y %H:%M:%S %z")

    if results:
        for entry in results:
            add_result_item(channel, entry)
    else:
        checked_dates = read_previous_status_dates(feed_path)
        checked_dates.add(search_date)
        add_status_item(channel, checked_dates)

    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")
    tree.write(feed_path, encoding="utf-8", xml_declaration=True)
    print(f"RSS feed generated successfully at {feed_path}", flush=True)


def print_test_results(results, search_date):
    print("\n" + "=" * 64, flush=True)
    print("TEST MODE — RSS FILE WILL NOT BE MODIFIED", flush=True)
    print(f"Date searched: {search_date.strftime('%m/%d/%Y')}", flush=True)
    print(f"Matching records found: {len(results)}", flush=True)

    if results:
        for entry in results:
            print("-" * 64, flush=True)
            print(f"Image ID:     {entry['id']}", flush=True)
            print(f"Facility ID:  {entry['facility_id']}", flush=True)
            print(f"Description:  {entry['description']}", flush=True)
            print(f"Image date:   {entry['date']}", flush=True)
            print(f"Details link: {entry['link']}", flush=True)
    else:
        print("No matching NOV, NOCR, or SOR records were found.", flush=True)

    print("=" * 64 + "\n", flush=True)


def print_summary(results, search_date, elapsed_seconds):
    print("\n" + "=" * 48, flush=True)
    print("RUN SUMMARY", flush=True)
    print(f"Mode:                 {'TEST' if TEST_MODE else 'PRODUCTION'}", flush=True)
    print(f"Date searched:        {search_date.strftime('%m/%d/%Y')}", flush=True)
    print(f"Page requests:        {STATS['pages_requested']}", flush=True)
    print(f"Valid table pages:    {STATS['valid_table_pages']}", flush=True)
    print(f"Rows examined:        {STATS['rows_examined']}", flush=True)
    print(f"Matching rows:        {STATS['matching_rows']}", flush=True)
    print(f"Duplicates removed:   {STATS['duplicates_removed']}", flush=True)
    print(f"Request retries:      {STATS['request_retries']}", flush=True)
    print(f"Blank-page retries:   {STATS['blank_page_retries']}", flush=True)
    print(f"Pages skipped:        {STATS['skipped_pages']}", flush=True)
    print(f"Unique feed results:  {len(results)}", flush=True)
    print(f"Elapsed seconds:      {elapsed_seconds:.1f}", flush=True)
    print("=" * 48, flush=True)


def main():
    started = time.monotonic()
    search_date = get_search_date()

    print(
        f"Starting {'test' if TEST_MODE else 'production'} search for "
        f"{search_date.strftime('%m/%d/%Y')}",
        flush=True,
    )

    session = requests.Session()
    login(session)
    results = scrape_all_pages(session, search_date)

    # A no-results statement is only trustworthy if the portal returned at
    # least one recognizable results table during the run.
    if STATS["valid_table_pages"] == 0:
        raise RuntimeError(
            "The OCC portal never returned a recognizable results table. "
            "The RSS feed was not modified."
        )

    if TEST_MODE:
        print_test_results(results, search_date)
    else:
        feed_path = os.path.join(os.path.dirname(__file__), FEED_FILENAME)
        write_feed(feed_path, results, search_date)

    print_summary(results, search_date, time.monotonic() - started)


if __name__ == "__main__":
    main()

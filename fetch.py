"""
WordPress RSS monitoring for K2 Quality routines
Parses RSS feed and sends email notifications for new routines
"""

import traceback
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus
from sendMail import sendMail, ChangeClientSecret
import os
from babel.dates import format_date
import re
import feedparser
import logging

# Constants
NORWEGIAN_TIMEZONE_OFFSET_HOURS = 2
NEW_ROUTINE_THRESHOLD_HOURS = 7 * 24  # 7 days
EXPIRATION_WARNING_3_WEEKS_MIN = 420   # 2.5 weeks in hours
EXPIRATION_WARNING_3_WEEKS_MAX = 588   # 3.5 weeks in hours
EXPIRATION_WARNING_2_WEEKS_MIN = 252   # 1.5 weeks in hours
EXPIRATION_WARNING_CRITICAL = 252      # Under 1.5 weeks

# Characters to keep: letters, numbers, spaces, Norwegian chars (æøåÆØÅ), and slash (/)
ALLOWED_CHARS = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 æøåÆØÅ/')


def sanitize_for_search(text):
    """
    Sanitize text for use in search URL by removing special characters.
    Keeps letters, numbers, spaces, Norwegian characters, and slash.
    """
    result = ''.join(char for char in text if char in ALLOWED_CHARS)
    # Remove multiple spaces and trim
    result = ' '.join(result.split())
    return result


def format_course_data(entry):
    """
    Format RSS entry into structured routine data.
    Extracts title, Norwegian time (+2 hours), and creates proper search URL.
    """
    title = entry.title.strip()
    entry_id = entry.id

    # Extract numeric ID from the end of the URL
    match = re.search(r'p=(\d+)$', entry_id)
    numeric_id = match.group(1) if match else None
    logging.info(f"  → Formatting routine: {title} (ID: {numeric_id})")

    # Parse published date and convert to Norwegian time
    published_date_utc = None
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        published_date_utc = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    elif hasattr(entry, 'published'):
        try:
            published_date_utc = datetime.fromisoformat(entry.published.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            published_date_utc = datetime.now(timezone.utc)
    else:
        published_date_utc = datetime.now(timezone.utc)

    current_norwegian_time = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=NORWEGIAN_TIMEZONE_OFFSET_HOURS)
    logging.info(f"Current Norwegian time: {current_norwegian_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Convert to Norwegian time
    norwegian_time = published_date_utc + timedelta(hours=NORWEGIAN_TIMEZONE_OFFSET_HOURS)

    # Create the search URL with sanitized and encoded title
    sanitized_title = sanitize_for_search(title)
    encoded_title = quote_plus(sanitized_title)
    search_url = f"https://quality.k2kompetanse.no/rutiner/?_kurs_sok={encoded_title}"

    date_part = format_date(norwegian_time, format='d. MMM yyyy', locale='nb')
    time_part = norwegian_time.strftime('%H:%M')
    formatted_date = f"{date_part}, kl {time_part}"

    routine_data = {
        'id': numeric_id,
        'title': title,
        'published_norwegian': norwegian_time.strftime('%Y-%m-%d %H:%M:%S'),
        'current_norwegian_time': current_norwegian_time.strftime('%Y-%m-%d %H:%M:%S'),
        'published_iso': norwegian_time.isoformat(),
        'search_url': search_url,
        'encoded_title': encoded_title,
        'formatted_date': formatted_date,
    }

    return routine_data


def is_new_routine(routine_data):
    """
    Check if this routine was posted in the last 7 days.
    """
    # Parse the routine's Norwegian publication time
    routine_published = datetime.fromisoformat(routine_data['published_iso'])

    # Remove timezone info for comparison (both are in Norwegian time)
    routine_published_naive = routine_published.replace(tzinfo=None)

    # Get current Norwegian time
    current_norwegian_time = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=NORWEGIAN_TIMEZONE_OFFSET_HOURS)

    # Calculate time difference
    time_diff = current_norwegian_time - routine_published_naive
    hours_since_published = time_diff.total_seconds() / 3600

    logging.info(f"  → Routine '{routine_data['title']}' published at {routine_published_naive}")
    logging.info(f"  → Current time: {current_norwegian_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info(f"  → Hours since published: {hours_since_published:.2f}")

    # Check if routine was published in the last 7 days
    if hours_since_published <= NEW_ROUTINE_THRESHOLD_HOURS:
        logging.info(f"  → This routine is NEW! (published {hours_since_published:.2f} hours ago)")
        logging.info(f"  → Search URL: {routine_data['search_url']}")
        return True
    else:
        logging.info(f"  → This routine is too old (published {hours_since_published:.2f} hours ago)")
        return False


def callMailFunction(routines):
    """
    Send all new routines in a single email.
    """
    try:
        logging.info(f"Sending {len(routines)} new routines to support mail...")
        result = sendMail(routines)
        if result:
            logging.info("Mail sent successfully!")
        else:
            logging.info("Failed to send mail")
    except Exception as e:
        logging.info(f"Error sending mail: {str(e)}")
        traceback.print_exc()


def test_rss_feed():
    """
    Main function to parse RSS feed and process routines.
    """
    logging.info("Testing WordPress RSS Feed Parsing")
    logging.info("=" * 50)

    rss_url = "https://quality.k2kompetanse.no/feed/?post_type=kurs"

    try:
        logging.info(f"Fetching RSS feed: {rss_url}")
        feed = feedparser.parse(rss_url)

        if feed.bozo:
            logging.info(f"RSS feed parsing warning: {feed.bozo_exception}")

        logging.info(f"Feed Information:")
        logging.info(f"  Title: {feed.feed.get('title', 'No title')}")
        logging.info(f"  Last updated: {feed.feed.get('lastbuilddate', 'Unknown')}")
        logging.info(f"  Total entries: {len(feed.entries)}")

        if len(feed.entries) == 0:
            logging.info("No entries found in the RSS feed")
            return

        logging.info(f"Processing {len(feed.entries)} routines:")
        logging.info("-" * 30)

        new_routines = []
        all_routines = []

        for i, entry in enumerate(feed.entries, 1):
            logging.info(f"{i}. Processing routine...")
            routine_data = format_course_data(entry)
            all_routines.append(routine_data)
            logging.info(f"  Title: {routine_data['title']}")
            logging.info(f"  Published: {routine_data['published_norwegian']}")
            logging.info(f"  URL: {routine_data['search_url']}")

            if is_new_routine(routine_data):
                new_routines.append(routine_data)
                logging.info("  This routine is NEW!")
            else:
                logging.info("  This routine is already processed, stopping process...")
                break

        logging.info(f"Summary:")
        logging.info(f"  Total routines Checked: {len(all_routines)}")
        logging.info(f"  New routines: {len(new_routines)}")

        if new_routines:
            logging.info(f"New routines found:")
            for routine in new_routines:
                logging.info(f"  - {routine['title']} ({routine['published_norwegian']})")
            logging.info(f"Sending all new routines in one mail")
            callMailFunction(new_routines)
        else:
            logging.info(f"No new routines to post")

        logging.info(f"Test completed successfully!")
    except Exception as e:
        logging.info(f"Error processing RSS feed: {str(e)}")
        traceback.print_exc()


def is_about_to_expire():
    """
    Check if the client secret is about to expire and send notification if needed.
    """
    try:
        expiration_date = os.getenv('CLIENT_SECRET_EXPIRATION_DATE')
        if not expiration_date:
            logging.info("CLIENT_SECRET_EXPIRATION_DATE not set in .env")
            return False

        # Remove quotes if present and parse with correct format
        expiration_date = expiration_date.strip('"')
        expiration_datetime = datetime.strptime(expiration_date, '%m/%d/%Y')
        current_datetime = datetime.now()

        time_diff = expiration_datetime - current_datetime
        hours_until_expiration = time_diff.total_seconds() / 3600
        logging.info(f"Client secret expires in {time_diff.days} days, {hours_until_expiration:.1f} hours")

        should_notify = False

        # 2.5 weeks to 3.5 weeks warning window
        if EXPIRATION_WARNING_3_WEEKS_MIN <= hours_until_expiration <= EXPIRATION_WARNING_3_WEEKS_MAX:
            should_notify = True
            logging.info(f"3 week expiration warning triggered ({time_diff.days} days remaining)")

        # 1.5 weeks to 2.5 weeks warning window
        elif EXPIRATION_WARNING_2_WEEKS_MIN <= hours_until_expiration <= EXPIRATION_WARNING_3_WEEKS_MIN:
            should_notify = True
            logging.info(f"2 week expiration warning triggered ({time_diff.days} days remaining)")

        # Under 1.5 weeks - critical warning
        elif hours_until_expiration < EXPIRATION_WARNING_CRITICAL:
            should_notify = True
            logging.info(f"Under 1.5 week expiration warning triggered ({hours_until_expiration:.1f} hours remaining)")

        if should_notify:
            if ChangeClientSecret():
                logging.info("Request for client secret change successfully sent")
        return should_notify

    except Exception as e:
        logging.info(f"Error checking client secret expiration: {str(e)}")
        return False

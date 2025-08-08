"""
Local test script for WordPress RSS monitoring
Tests RSS parsing and data formatting, then sends new routines to support mail
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


def format_course_data(entry):
    """
    Format RSS entry into structured routine data
    Extracts: title, Norwegian time (+2 hours), and creates proper search URL
    """
    
    # Extract title
    title = entry.title.strip()
    id = entry.id
    # Extract numeric ID from the end of the URL
    match = re.search(r'p=(\d+)$', id)
    numeric_id = match.group(1) if match else None
    logging.info(f"  → Formatting routine: {title} (ID: {numeric_id})")
    
    # Parse published date and convert to Norwegian time (+2 hours)
    published_date_utc = None
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        published_date_utc = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    elif hasattr(entry, 'published'):
        try:
            published_date_utc = datetime.fromisoformat(entry.published.replace('Z', '+00:00'))
        except:
            published_date_utc = datetime.now(timezone.utc)
    else:
        published_date_utc = datetime.now(timezone.utc)
    current_norwegian_time = datetime.utcnow() + timedelta(hours=2)
        
    logging.info(f"\n⏰ Current Norwegian time: {current_norwegian_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Convert to Norwegian time (+2 hours)
    norwegian_time = published_date_utc + timedelta(hours=2)
    
    # Create the search URL with properly encoded title
    # Example: "AL tester" becomes "AL%20tester"
    encoded_title = quote_plus(title)
    search_url = f"https://quality.k2kompetanse.no/rutiner/?_kurs_sok={encoded_title}"

    date_part = format_date(norwegian_time, format='d. MMM yyyy', locale='nb')
    time_part = norwegian_time.strftime('%H:%M')
    formatted_date = f"{date_part}, kl {time_part}"
    
    routine_data = {
        'id': numeric_id,
        'title': title,
        'published_norwegian': norwegian_time.strftime('%Y-%m-%d %H:%M:%S'),
        current_norwegian_time: current_norwegian_time.strftime('%Y-%m-%d %H:%M:%S'),
        'published_iso': norwegian_time.isoformat(),
        'search_url': search_url,
        'encoded_title': encoded_title,
        'formatted_date': formatted_date,

    }
    
    return routine_data


def is_new_routine(routine_data):
    """
    Check if this routine was posted in the last 6 hours
    """
    
    # Parse the routine's Norwegian publication time
    routine_published = datetime.fromisoformat(routine_data['published_iso'])
    
    # Remove timezone info for comparison (both are in Norwegian time)
    routine_published_naive = routine_published.replace(tzinfo=None)
    
    # Get current Norwegian time
    current_norwegian_time = datetime.utcnow() + timedelta(hours=2)
    
    # Calculate time difference
    time_diff = current_norwegian_time - routine_published_naive
    hours_since_published = time_diff.total_seconds() / 3600
    
    logging.info(f"  → Routine '{routine_data['title']}' published at {routine_published_naive}")
    logging.info(f"  → Current time: {current_norwegian_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info(f"  → Hours since published: {hours_since_published:.2f}")
    
    # Check if routine was published in the last 6 hours
    if hours_since_published <= 6:
        logging.info(f"  → This routine is NEW! (published {hours_since_published:.2f} hours ago)")
        logging.info(f"  → Search URL: {routine_data['search_url']}")
        return True
    else:
        logging.info(f"  → This routine is too old (published {hours_since_published:.2f} hours ago)")
        return False


def test_rss_feed():
    """
    Test the RSS feed parsing and formatting
    """


    logging.info("🔍 Testing WordPress RSS Feed Parsing")
    logging.info("=" * 50)
    
    # RSS feed URL for your WordPress kurs custom post type
    rss_url = "https://quality.k2kompetanse.no/feed/?post_type=kurs"
    
    try:
        logging.info(f"📡 Fetching RSS feed: {rss_url}")
        
        # Parse the RSS feed
        feed = feedparser.parse(rss_url)
        
        if feed.bozo:
            logging.info(f"⚠️  RSS feed parsing warning: {feed.bozo_exception}")
        
        # Feed info
        logging.info(f"\n📋 Feed Information:")
        logging.info(f"  Title: {feed.feed.get('title', 'No title')}")
        logging.info(f"  Last updated: {feed.feed.get('lastbuilddate', 'Unknown')}")
        logging.info(f"  Total entries: {len(feed.entries)}")
        
        if len(feed.entries) == 0:
            logging.info("\n❌ No entries found in the RSS feed")
            return
        
        # Process each entry in the feed
        logging.info(f"\n📚 Processing {len(feed.entries)} routines:")
        logging.info("-" * 30)
        
        new_routines = []
        all_routines = []
        
        for i, entry in enumerate(feed.entries, 1):
            logging.info(f"\n{i}. Processing routine...")
            
            routine_data = format_course_data(entry)
            all_routines.append(routine_data)
            
            logging.info(f"  📖 Title: {routine_data['title']}")
            logging.info(f"  📅 Published: {routine_data['published_norwegian']}")
            logging.info(f"  🔗 URL: {routine_data['search_url']}")
            
            # Check if this routine is new (not in the last 10 processed)
            if is_new_routine(routine_data):
                new_routines.append(routine_data)
                logging.info(f"  ✅ This routine is NEW!")
                callMailFunction(routine_data)
                
            else:
                logging.info(f"  ⏸️  This routine is already processed, stopping process...")
                break

        # Summary
        logging.info(f"\n📊 Summary:")
        logging.info(f"  Total routines Checked: {len(all_routines)}")
        logging.info(f"  New routines: {len(new_routines)}")
        
        if new_routines:
            logging.info(f"\n🆕 New routines found:")
            for routine in new_routines:
                logging.info(f"  - {routine['title']} ({routine['published_norwegian']})")

            logging.info(f"\n📤 {len(new_routines)} new routines were sent to support mail")
        else:
            logging.info(f"\n😴 No new routines to post")
        
        logging.info(f"\n✅ Test completed successfully!")
    except Exception as e:
        logging.info(f"❌ Error processing RSS feed: {str(e)}")
        traceback.print_exc()


def callMailFunction(routine_data):
    """
    Send data and call function in sendMail.py
    """
    try:
        logging.info(f"📧 Sending routine data to support mail...")
        result = sendMail(routine_data)
        if result:
            logging.info(f"  ✅ Mail sent successfully!")
        else:
            logging.info(f"  ❌ Failed to send mail")

    except Exception as e:
        logging.info(f"❌ Error sending mail: {str(e)}")
        traceback.print_exc()



def is_about_to_expire():
    """
    Check if the client secret is about to expire
    """


    try:
        expiration_date = os.getenv('CLIENT_SECRET_EXPIRATION_DATE')
        if not expiration_date:
            logging.info("❌ CLIENT_SECRET_EXPIRATION_DATE not set in .env")
            return False
        
        # Remove quotes if present and parse with correct format
        expiration_date = expiration_date.strip('"')
        expiration_datetime = datetime.strptime(expiration_date, '%m/%d/%Y')
        current_datetime = datetime.now()
        
        time_diff = expiration_datetime - current_datetime
        hours_until_expiration = time_diff.total_seconds() / 3600
        logging.info(f"⏳ Client secret expires in {time_diff.days} days, {hours_until_expiration:.1f} hours")
        
                  
        should_notify = False
        
        if 72 <= hours_until_expiration <= 75:
            should_notify = True
            logging.info(f"🔔 3 day expiration warning triggered ({time_diff.days} days remaining)")
        
        elif 24 <= hours_until_expiration <= 27:
            should_notify = True
            logging.info(f"🔔 1 day expiration warning triggered ({time_diff.days} days remaining)")
        
        elif 21 <= hours_until_expiration <= 24:
            should_notify = True
            logging.info(f"🔔 Under 24-hour expiration warning triggered ({hours_until_expiration:.1f} hours remaining)")
        
        # Save updated notifications
        if should_notify:
            if ChangeClientSecret():
                logging.info("✅ Request for client secret change successfully sent")
        return should_notify
        
    except Exception as e:
        logging.info(f"❌ Error checking client secret expiration: {str(e)}")
        return False
    
if __name__ == "__main__":
    logging.info("🔍 Starting WordPress RSS Monitoring Test")
    logging.info("=" * 50)
    
    # Check if client secret is about to expire
    is_about_to_expire()

    # Run the RSS feed test
    test_rss_feed()
    
    logging.info("\n✅ Test completed successfully!")
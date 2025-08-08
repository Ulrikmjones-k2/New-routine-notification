"""
Local test script for WordPress RSS monitoring
Tests RSS parsing and data formatting, then sends new routines to support mail
"""

import json
import traceback
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus
from sendMail import sendMail, ChangeClientSecret
import os
from babel.dates import format_date
import re
import feedparser
import logging


is_first_routine = True
first_routine_id = None
cache_updated = False
cache_file =  'cache.json'
sentNotifications_file =  'sentNotifications.json'



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
        'published_iso': norwegian_time.isoformat(),
        'search_url': search_url,
        'encoded_title': encoded_title,
        'formatted_date': formatted_date,

    }
    
    return routine_data

def lastroutine():
    """
    Get the last routine ID from the JSON file
    """
    global cache_file
    with open(cache_file, "r") as file:
        data = json.load(file)
        ids = data.get('ids', [])
        logging.info(f"  → Last routine IDs from cache: {ids}")
    return ids




def is_new_routine(routine_data):
    """
    Check if this routine is newer than any of the last processed routines
    """
    
    # Parse the routine's Norwegian publication time
    routine_published = datetime.fromisoformat(routine_data['published_iso'])
    
    # Remove timezone info for comparison (both are in Norwegian time)
    routine_published_naive = routine_published.replace(tzinfo=None)
    
    # Get list of cached routine IDs
    cached_ids = lastroutine()
    
    logging.info(f"  → Routine '{routine_data['title']}' published at {routine_published_naive}")
    logging.info(f"  → Checking against cached IDs: {cached_ids}")
    
    # Check if this routine ID is already in the cache
    if routine_data['id'] in cached_ids:
        logging.info(f"  → This routine is already processed (ID: {routine_data['id']})")
        return False

    logging.info(f"  → This routine is NEW! (ID: {routine_data['id']})")
    logging.info(f"  → Search URL: {routine_data['search_url']}")
    return True


def test_rss_feed():
    """
    Test the RSS feed parsing and formatting
    """

    global is_first_routine, first_routine_id, cache_updated, cache_file

    # Create cache file if it does not exist
    if not os.path.exists(cache_file):
        logging.info(f"📁 Creating {cache_file} - file not found")
        with open(cache_file, "w") as f:
            json.dump({"ids": []}, f, indent=2)
    else:
        logging.info(f"📁 Cache file {cache_file} already exists, using existing data")

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
        
        # Get current time in Norwegian timezone for comparison
        current_norwegian_time = datetime.utcnow() + timedelta(hours=2)
        
        logging.info(f"\n⏰ Current Norwegian time: {current_norwegian_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
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
                
                # Update cache with this new routine ID
                updatecahche(routine_data['id'])
            else:
                logging.info(f"  ⏸️  This routine is already processed, continuing to next...")
                # Continue processing all routines instead of breaking

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
        if new_routines:
            logging.info(f"  📦 Cache was updated with {len(new_routines)} new routine IDs")
        else:
            logging.info(f"  📦 Cache was NOT updated, no new routines found")
    except Exception as e:
        logging.info(f"❌ Error processing RSS feed: {str(e)}")
        traceback.print_exc()

def updatecahche(new_id):
    """
    Update the cache with the latest routine ID, keeping only the 10 newest
    """
    global cache_updated, cache_file
    try:
        # Get current cached IDs
        cached_ids = lastroutine()
        
        # Add new ID to the beginning of the list
        if new_id not in cached_ids:
            cached_ids.insert(0, new_id)
        
        # Keep only the 10 newest IDs
        cached_ids = cached_ids[:10]
        
        # Save updated cache
        with open(cache_file, "w") as file:
            json.dump({"ids": cached_ids}, file, indent=2)
            logging.info(f"📦 Cache updated with new routine ID: {new_id}")
            logging.info(f"📦 Current cached IDs: {cached_ids}")
            cache_updated = True
    except Exception as e:
        logging.info(f"❌ Error updating cache: {str(e)}")


def callMailFunction(routine_data):
    """
    Send data and call function in sendMail.py
    """
    global is_first_routine, first_routine_id
    try:
        id = routine_data['id']
        logging.info(f"📧 Sending routine data to support mail...")
        result = sendMail(routine_data)
        if result:
            logging.info(f"  ✅ Mail sent successfully!")
            if is_first_routine:
                first_routine_id = id
                is_first_routine = False
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
        
        global sentNotifications_file
        
        sent_notifications = {}
        if not os.path.exists(sentNotifications_file):
            logging.info(f"📁 Creating {sentNotifications_file} - file not found")
            with open(sentNotifications_file, "w") as f:
                json.dump(sent_notifications, f, indent=2)
        else:
            logging.info(f"📁 Sent notifications file {sentNotifications_file} already exists, using existing data")
            with open(sentNotifications_file, 'r') as f:
                sent_notifications = json.load(f)
                

        exp_date_key = expiration_date

        # Clear cache if expiration date is recently updated
        # If more than 30 days (720 hours) until expiration and cache exists for this date
        if hours_until_expiration > 720 and exp_date_key in sent_notifications:
            logging.info("🧹 Clearing notification cache - new client secret detected (expiration > 150 days)")
            sent_notifications = {}
            with open(sentNotifications_file, 'w') as f:
                json.dump(sent_notifications, f, indent=2)
        
        if exp_date_key not in sent_notifications:
            sent_notifications[exp_date_key] = {}
        
        should_notify = False
        
        if 72 <= hours_until_expiration <= 96 and not sent_notifications[exp_date_key].get('3_days', False):
            should_notify = True
            sent_notifications[exp_date_key]['3_days'] = True
            logging.info(f"🔔 3-4 days expiration warning triggered ({time_diff.days} days remaining)")
        
        elif 24 <= hours_until_expiration <= 48 and not sent_notifications[exp_date_key].get('1_day', False):
            should_notify = True
            sent_notifications[exp_date_key]['1_day'] = True
            logging.info(f"🔔 1-2 days expiration warning triggered ({time_diff.days} days remaining)")
        
        elif 0 <= hours_until_expiration <= 24 and not sent_notifications[exp_date_key].get('3_hours', False):
            should_notify = True
            sent_notifications[exp_date_key]['3_hours'] = True
            logging.info(f"🔔 Under 24-hour expiration warning triggered ({hours_until_expiration:.1f} hours remaining)")
        
        # Save updated notifications
        if should_notify:
            with open(sentNotifications_file, 'w') as f:
                json.dump(sent_notifications, f, indent=2)
            

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
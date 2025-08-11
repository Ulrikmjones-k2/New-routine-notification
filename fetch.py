"""
Local test script for WordPress RSS monitoring
Tests RSS parsing and data formatting, then sends new routines to support mail
"""

import json
import traceback
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus
from sendMail import sendMail, ChangeClientSecret
from db_init import init_database, DATABASE_PATH  # Import the dynamic path
import os
from babel.dates import format_date
import re
import feedparser
import logging
import sqlite3


is_first_routine = True
first_routine_id = None
cache_updated = False
DATABASE_FILE =  'cache.db'



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
    print(f"  → Formatting routine: {title} (ID: {numeric_id})")
    
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
    Get the last routine IDs from the SQLite database
    """
    try:
        conn = sqlite3.connect(DATABASE_PATH)  # Use dynamic path
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT routine_id FROM routine_ids 
            ORDER BY created_at DESC 
        ''')
        
        ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return ids
    except Exception as e:
        logging.error(f"❌ Error getting routine IDs from database: {str(e)}")
        print(f"❌ Error getting routine IDs from database: {str(e)}")
        return []



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
    print(f"  → Routine '{routine_data['title']}' published at {routine_published_naive}")
    logging.info(f"  → Checking against cached IDs: {cached_ids}")
    print(f"  → Checking against cached IDs: {cached_ids}")
    
    # Check if this routine ID is already in the cache
    if routine_data['id'] in cached_ids:
        logging.info(f"  → This routine is already processed (ID: {routine_data['id']})")
        print(f"  → This routine is already processed (ID: {routine_data['id']})")
        return False
    else:
        logging.info(f"  → This routine is NEW! (ID: {routine_data['id']})")
        print(f"  → This routine is NEW! (ID: {routine_data['id']})")
        logging.info(f"  → Search URL: {routine_data['search_url']}")
        print(f"  → Search URL: {routine_data['search_url']}")
        return True


def test_rss_feed():
    """
    Test the RSS feed parsing and formatting
    """

    global is_first_routine, first_routine_id, cache_updated

    if not init_database():
        logging.error("❌ Failed to initialize database")
        print("❌ Failed to initialize database")
        return

    logging.info("🔍 Testing WordPress RSS Feed Parsing")
    print("🔍 Testing WordPress RSS Feed Parsing")
    logging.info("=" * 50)
    print("=" * 50)
    
    # RSS feed URL for your WordPress kurs custom post type
    rss_url = "https://quality.k2kompetanse.no/feed/?post_type=kurs"
    
    try:
        logging.info(f"📡 Fetching RSS feed: {rss_url}")
        print(f"📡 Fetching RSS feed: {rss_url}")
        
        # Parse the RSS feed
        feed = feedparser.parse(rss_url)
        
        if feed.bozo:
            logging.info(f"⚠️  RSS feed parsing warning: {feed.bozo_exception}")
            print(f"⚠️  RSS feed parsing warning: {feed.bozo_exception}")
        
        # Feed info
        logging.info(f"\n📋 Feed Information:")
        print(f"\n📋 Feed Information:")
        logging.info(f"  Title: {feed.feed.get('title', 'No title')}")
        print(f"  Title: {feed.feed.get('title', 'No title')}")
        logging.info(f"  Last updated: {feed.feed.get('lastbuilddate', 'Unknown')}")
        print(f"  Last updated: {feed.feed.get('lastbuilddate', 'Unknown')}")
        logging.info(f"  Total entries: {len(feed.entries)}")
        print(f"  Total entries: {len(feed.entries)}")
        
        if len(feed.entries) == 0:
            logging.info("\n❌ No entries found in the RSS feed")
            print("\n❌ No entries found in the RSS feed")
            return
        
        # Get current time in Norwegian timezone for comparison
        current_norwegian_time = datetime.utcnow() + timedelta(hours=2)
        
        logging.info(f"\n⏰ Current Norwegian time: {current_norwegian_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\n⏰ Current Norwegian time: {current_norwegian_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Process each entry in the feed
        logging.info(f"\n📚 Processing {len(feed.entries)} routines:")
        print(f"\n📚 Processing {len(feed.entries)} routines:")
        logging.info("-" * 30)
        print("-" * 30)
        
        new_routines = []
        all_routines = []
        
        for i, entry in enumerate(feed.entries, 1):
            logging.info(f"\n{i}. Processing routine...")
            print(f"\n{i}. Processing routine...")
            
            routine_data = format_course_data(entry)
            all_routines.append(routine_data)
            
            logging.info(f"  📖 Title: {routine_data['title']}")
            print(f"  📖 Title: {routine_data['title']}")
            logging.info(f"  📅 Published: {routine_data['published_norwegian']}")
            print(f"  📅 Published: {routine_data['published_norwegian']}")
            logging.info(f"  🔗 URL: {routine_data['search_url']}")
            print(f"  🔗 URL: {routine_data['search_url']}")
            
            # Add this debug line
            logging.info(f"🔍 ABOUT TO CHECK if routine {routine_data['id']} is new...")
            print(f"🔍 ABOUT TO CHECK if routine {routine_data['id']} is new...")
            
            # Check if this routine is new (not in the last 10 processed)
            if is_new_routine(routine_data):
                new_routines.append(routine_data)
                logging.info(f"  ✅ This routine is NEW!")
                print(f"  ✅ This routine is NEW!")
                
                # Add this debug line
                logging.info(f"📧 ABOUT TO CALL callMailFunction for routine {routine_data['id']}")
                print(f"📧 ABOUT TO CALL callMailFunction for routine {routine_data['id']}")
                
                callMailFunction(routine_data)
                
                # Update cache with this new routine ID
                updatecache(routine_data['id'])
            else:
                logging.info(f"  ⏸️  This routine is already processed, continuing to next...")
                print(f"  ⏸️  This routine is already processed, continuing to next...")
                
                # Add this debug line  
                logging.info(f"🚫 NOT calling callMailFunction for routine {routine_data['id']}")
                print(f"🚫 NOT calling callMailFunction for routine {routine_data['id']}")
                
        # Summary
        logging.info(f"\n📊 Summary:")
        print(f"\n📊 Summary:")
        logging.info(f"  Total routines Checked: {len(all_routines)}")
        print(f"  Total routines Checked: {len(all_routines)}")
        logging.info(f"  New routines: {len(new_routines)}")
        print(f"  New routines: {len(new_routines)}")
        
        if new_routines:
            logging.info(f"\n🆕 New routines found:")
            print(f"\n🆕 New routines found:")
            for routine in new_routines:
                logging.info(f"  - {routine['title']} ({routine['published_norwegian']})")
                print(f"  - {routine['title']} ({routine['published_norwegian']})")

            logging.info(f"\n📤 {len(new_routines)} new routines were sent to support mail")
            print(f"\n📤 {len(new_routines)} new routines were sent to support mail")
        else:
            logging.info(f"\n😴 No new routines to post")
            print(f"\n😴 No new routines to post")
        
        logging.info(f"\n✅ Test completed successfully!")
        print(f"\n✅ Test completed successfully!")
        if new_routines:
            logging.info(f"  📦 Database was updated with {len(new_routines)} new routine IDs")
            print(f"  📦 Database was updated with {len(new_routines)} new routine IDs")
        else:
            logging.info(f"  📦 Database was NOT updated, no new routines found")
            print(f"  📦 Database was NOT updated, no new routines found")
    except Exception as e:
        logging.info(f"❌ Error processing RSS feed: {str(e)}")
        print(f"❌ Error processing RSS feed: {str(e)}")
        traceback.print_exc()

def updatecache(new_id):
    """
    Update the database with the latest routine ID
    """
    global cache_updated

    logging.info(f"📦 Updating cache with new routine ID: {new_id}")
    print(f"📦 Updating cache with new routine ID: {new_id}")

    try:
        conn = sqlite3.connect(DATABASE_PATH)  # Use dynamic path
        cursor = conn.cursor()
        
        # Add new ID to database
        cursor.execute('''
            INSERT OR IGNORE INTO routine_ids (routine_id) 
            VALUES (?)
        ''', (new_id,))
        
        
        conn.commit()
        conn.close()

        # Get current cached IDs for logging
        cached_ids = lastroutine()
        
        logging.info(f"📦 Database updated with new routine ID: {new_id}")
        print(f"📦 Database updated with new routine ID: {new_id}")
        logging.info(f"📦 Current cached IDs: {cached_ids}")
        print(f"📦 Current cached IDs: {cached_ids}")
        cache_updated = True

    except Exception as e:
        logging.info(f"❌ Error updating cache: {str(e)}")
        print(f"❌ Error updating cache: {str(e)}")


def callMailFunction(routine_data):
    """
    Send data and call function in sendMail.py
    """
    global is_first_routine, first_routine_id
    try:
        id = routine_data['id']
        logging.info(f"📧 Sending routine data to support mail...")
        print(f"📧 Sending routine data to support mail...")
        result = sendMail(routine_data)
        if result:
            logging.info(f"  ✅ Mail sent successfully!")
            print(f"  ✅ Mail sent successfully!")
            if is_first_routine:
                first_routine_id = id
                is_first_routine = False
        else:
            logging.info(f"  ❌ Failed to send mail")
            print(f"  ❌ Failed to send mail")

    except Exception as e:
        logging.info(f"❌ Error sending mail: {str(e)}")
        print(f"❌ Error sending mail: {str(e)}")
        traceback.print_exc()



def is_about_to_expire():
    """
    Check if the client secret is about to expire
    """


    try:
        expiration_date = os.getenv('CLIENT_SECRET_EXPIRATION_DATE')
        if not expiration_date:
            logging.info("❌ CLIENT_SECRET_EXPIRATION_DATE not set in .env")
            print("❌ CLIENT_SECRET_EXPIRATION_DATE not set in .env")
            return False
        
        # Remove quotes if present and parse with correct format
        expiration_date = expiration_date.strip('"')
        expiration_datetime = datetime.strptime(expiration_date, '%m/%d/%Y')
        current_datetime = datetime.now()
        
        time_diff = expiration_datetime - current_datetime
        hours_until_expiration = time_diff.total_seconds() / 3600
        logging.info(f"⏳ Client secret expires in {time_diff.days} days, {hours_until_expiration:.1f} hours")
        print(f"⏳ Client secret expires in {time_diff.days} days, {hours_until_expiration:.1f} hours")
        
                  
        should_notify = False
        
        # 2.5 weeks = 420 hours, 3.5 weeks = 588 hours
        if 420 <= hours_until_expiration <= 588:
            should_notify = True
            logging.info(f"🔔 3 week expiration warning triggered ({time_diff.days} days remaining)")
            print(f"🔔 3 week expiration warning triggered ({time_diff.days} days remaining)")
        
        # 1.5 weeks = 252 hours, 2.5 weeks = 420 hours
        elif 252 <= hours_until_expiration <= 420:
            should_notify = True
            logging.info(f"🔔 2 week expiration warning triggered ({time_diff.days} days remaining)")
            print(f"🔔 2 week expiration warning triggered ({time_diff.days} days remaining)")
        
        # Under 1.5 weeks = under 252 hours
        elif hours_until_expiration < 252:
            should_notify = True
            logging.info(f"🔔 Under 1.5 week expiration warning triggered ({hours_until_expiration:.1f} hours remaining)")
            print(f"🔔 Under 1.5 week expiration warning triggered ({hours_until_expiration:.1f} hours remaining)")

        # Save updated notifications
        if should_notify:
            if ChangeClientSecret():
                logging.info("✅ Request for client secret change successfully sent")
                print("✅ Request for client secret change successfully sent")
        return should_notify
        
    except Exception as e:
        logging.info(f"❌ Error checking client secret expiration: {str(e)}")
        print(f"❌ Error checking client secret expiration: {str(e)}")
        return False
#!/usr/bin/env python3
"""
Local test script for WordPress RSS monitoring
Tests RSS parsing and data formatting, then sends new routines to support mail
"""

import feedparser
import json
import traceback
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus
from sendMail import sendMail
from sendMail import ChangeClientSecret
import os
from babel.dates import format_date
import re


is_first_routine = True
first_routine_id = None
cache_updated = False

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
    Get the last routine ID from the JSON file
    """
    with open("cache.json", "r") as file:
        data = json.load(file)
        return data['id']




def is_new_routine(routine_data):
    """
    Check if this routine is newer than the last processed routine
    """
    
    # Parse the routine's Norwegian publication time
    routine_published = datetime.fromisoformat(routine_data['published_iso'])
    
    # Remove timezone info for comparison (both are in Norwegian time)
    routine_published_naive = routine_published.replace(tzinfo=None)
    
    # Check if published within the last hour
    print(f"  → Routine '{routine_data['title']}' published at {routine_published_naive}")
    if routine_data['id'] == lastroutine():
        print(routine_data['id'])
        print(lastroutine())
        print(f"  → This routine is already processed (ID: {routine_data['id']})")
        return False

    print(f"  → Search URL: {routine_data['search_url']}")
    return True


def test_rss_feed():
    """
    Test the RSS feed parsing and formatting
    """

    global is_first_routine, first_routine_id
    
    print("🔍 Testing WordPress RSS Feed Parsing")
    print("=" * 50)
    
    # RSS feed URL for your WordPress kurs custom post type
    rss_url = "https://quality.k2kompetanse.no/feed/?post_type=kurs"
    
    try:
        print(f"📡 Fetching RSS feed: {rss_url}")
        
        # Parse the RSS feed
        feed = feedparser.parse(rss_url)
        
        if feed.bozo:
            print(f"⚠️  RSS feed parsing warning: {feed.bozo_exception}")
        
        # Feed info
        print(f"\n📋 Feed Information:")
        print(f"  Title: {feed.feed.get('title', 'No title')}")
        print(f"  Last updated: {feed.feed.get('lastbuilddate', 'Unknown')}")
        print(f"  Total entries: {len(feed.entries)}")
        
        if len(feed.entries) == 0:
            print("\n❌ No entries found in the RSS feed")
            return
        
        # Get current time in Norwegian timezone for comparison
        current_norwegian_time = datetime.utcnow() + timedelta(hours=2)
        
        print(f"\n⏰ Current Norwegian time: {current_norwegian_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Process each entry in the feed
        print(f"\n📚 Processing {len(feed.entries)} routines:")
        print("-" * 30)
        
        new_routines = []
        all_routines = []
        
        for i, entry in enumerate(feed.entries, 1):
            print(f"\n{i}. Processing routine...")
            
            routine_data = format_course_data(entry)
            all_routines.append(routine_data)
            
            print(f"  📖 Title: {routine_data['title']}")
            print(f"  📅 Published: {routine_data['published_norwegian']}")
            print(f"  🔗 URL: {routine_data['search_url']}")
            
            # Check if this routine was published in the last hour
            if is_new_routine(routine_data):
                new_routines.append(routine_data)
                print(f"  ✅ This routine is NEW!")
                callMailFunction(routine_data)
            else:
                print(f"  ⏸️  This routine is not new, stopping processing...")
                if is_first_routine:
                    break
                if first_routine_id is None:
                    first_routine_id = routine_data['id']
                updatecahche(first_routine_id)
                break

        # Summary
        print(f"\n📊 Summary:")
        print(f"  Total routines Checked: {len(all_routines)}")
        print(f"  New routines: {len(new_routines)}")
        
        if new_routines:
            print(f"\n🆕 New routines found:")
            for routine in new_routines:
                print(f"  - {routine['title']} ({routine['published_norwegian']})")

            # Send new routines to support mail
            print(f"\n📤 Sending {len(new_routines)} new routines to support mail...")
        else:
            print(f"\n😴 No new routines to post")
        
        print(f"\n✅ Test completed successfully!")
        if cache_updated:
            print(f"  📦 Cache was updated with new routine ID: {first_routine_id}")
        else:
            print(f"  📦 Cache was NOT updated, no new routines found")
    except Exception as e:
        print(f"❌ Error processing RSS feed: {str(e)}")
        traceback.print_exc()


def updatecahche(id):
    """
    Update the cache with the latest routine ID
    """
    global cache_updated
    try:
        with open("cache.json", "w") as file:
            json.dump({"id": id}, file)
            print(f"📦 Cache updated with new routine ID: {id}")
            cache_updated = True
    except Exception as e:
        print(f"❌ Error updating cache: {str(e)}")



def callMailFunction(routine_data):
    """
    Send data and call function in sendMail.py
    """
    global is_first_routine, first_routine_id
    try:
        id = routine_data['id']
        print(f"📧 Sending routine data to support mail...")
        result = sendMail(routine_data)
        if result:
            print(f"  ✅ Mail sent successfully!")
            if is_first_routine:
                first_routine_id = id
                is_first_routine = False
        else:
            print(f"  ❌ Failed to send mail")

    except Exception as e:
        print(f"❌ Error sending mail: {str(e)}")
        traceback.print_exc()













def is_about_to_expire():
    """
    Check if the client secret is about to expire
    """
    try:
        expiration_date = os.getenv('CLIENT_SECRET_EXPIRATION_DATE')
        if not expiration_date:
            print("❌ CLIENT_SECRET_EXPIRATION_DATE not set in .env")
            return False
        
        # Remove quotes if present and parse with correct format
        expiration_date = expiration_date.strip('"')
        expiration_datetime = datetime.strptime(expiration_date, '%m/%d/%Y')
        current_datetime = datetime.now()
        
        time_diff = expiration_datetime - current_datetime
        hours_until_expiration = time_diff.total_seconds() / 3600
        print(f"⏳ Client secret expires in {time_diff.days} days, {hours_until_expiration:.1f} hours")
        
        notifications_file = 'sentNotifications.json'
        
        sent_notifications = {}
        if os.path.exists(notifications_file):
            try:
                with open(notifications_file, 'r') as f:
                    sent_notifications = json.load(f)
            except:
                sent_notifications = {}

        exp_date_key = expiration_date

        # Clear cache if expiration date is recently updated
        # If more than 30 days (720 hours) until expiration and cache exists for this date
        if hours_until_expiration > 720 and exp_date_key in sent_notifications:
            print("🧹 Clearing notification cache - new client secret detected (expiration > 150 days)")
            sent_notifications = {}
            with open(notifications_file, 'w') as f:
                json.dump(sent_notifications, f, indent=2)
        
        if exp_date_key not in sent_notifications:
            sent_notifications[exp_date_key] = {}
        
        should_notify = False
        
        if 72 <= hours_until_expiration <= 96 and not sent_notifications[exp_date_key].get('3_days', False):
            should_notify = True
            sent_notifications[exp_date_key]['3_days'] = True
            print(f"🔔 3-4 days expiration warning triggered ({time_diff.days} days remaining)")
        
        elif 24 <= hours_until_expiration <= 48 and not sent_notifications[exp_date_key].get('1_day', False):
            should_notify = True
            sent_notifications[exp_date_key]['1_day'] = True
            print(f"🔔 1-2 days expiration warning triggered ({time_diff.days} days remaining)")
        
        elif 0 <= hours_until_expiration <= 24 and not sent_notifications[exp_date_key].get('3_hours', False):
            should_notify = True
            sent_notifications[exp_date_key]['3_hours'] = True
            print(f"🔔 Under 24-hour expiration warning triggered ({hours_until_expiration:.1f} hours remaining)")
        
        # Save updated notifications
        if should_notify:
            with open(notifications_file, 'w') as f:
                json.dump(sent_notifications, f, indent=2)
            

            if ChangeClientSecret():
                print("✅ Request for client secret change successfully sent")
        return should_notify
        
    except Exception as e:
        print(f"❌ Error checking client secret expiration: {str(e)}")
        return False



if __name__ == "__main__":
    test_rss_feed()
    is_about_to_expire()

    # test
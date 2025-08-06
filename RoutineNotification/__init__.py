import logging
import azure.functions as func
import datetime
from .fetch import test_rss_feed

def main(myTimer: func.TimerRequest) -> None:
    utc_timestamp = myTimer.schedule_status.last_updated.replace(
        tzinfo=datetime.timezone.utc).isoformat()

    if myTimer.schedule_status.last_updated is not None:
        logging.info('Python timer trigger function ran at %s', utc_timestamp)

    # Run your RSS feed processing
    test_rss_feed()
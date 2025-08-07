import logging
import azure.functions as func
import sys
import os

def main(myTimer: func.TimerRequest) -> None:
    logging.info('Function started')
    
    try:
        # Add the parent directory to the Python path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        logging.info('Importing modules...')
        import fetch
        logging.info('Modules imported successfully')
        
        logging.info('Checking client secret expiration...')
        fetch.is_about_to_expire()
        logging.info('Client secret check completed')
        
        logging.info('Starting RSS feed test...')
        fetch.test_rss_feed()
        logging.info('RSS feed test completed')
        
        logging.info('Function completed successfully')
        
    except Exception as e:
        logging.error(f'Error in function: {str(e)}')
        import traceback
        logging.error(f'Traceback: {traceback.format_exc()}')
        raise
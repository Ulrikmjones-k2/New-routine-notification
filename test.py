import os
import logging

def testcahce():
    """
    Test function to check if cache file exists and is readable
    """
    cache_file = 'test.json'
    try:
        if not os.path.exists(cache_file):
            logging.info(f"📁 Creating {cache_file} - file not found")
            with open(cache_file, "w") as f:
                f.write("{test: 'test'}")
        with open(cache_file, 'r') as f:
            data = f.read()
            logging.info("Cache file read successfully - data:", data)
            return data
    except FileNotFoundError:
        logging.info("Cache file not found")
        return None
    except Exception as e:
        logging.info(f"Error reading cache file: {str(e)}")
        return None

testcahce()
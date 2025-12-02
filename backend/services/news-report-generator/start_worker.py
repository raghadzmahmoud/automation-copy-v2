#!/usr/bin/env python3
"""
🔊 Background Worker - AUDIO ONLY MODE
Runs ONLY the audio generation job every 2 minutes
"""

import schedule
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_audio_generation():
    """Audio generation job - test mode"""
    logger.info("Audio Generation Job TRIGGERED...")
    
    try:
        from cron.audio_generation_job import generate_audio
        generate_audio()
    except Exception as e:
        logger.error(f"Audio Generation Job error: {e}")
        import traceback
        traceback.print_exc()

    logger.info("Audio Generation Job FINISHED.")


def main():
    logger.info("========================================")
    logger.info(" AUDIO GENERATION JOB - TEST MODE ONLY ")
    logger.info(" Running every 2 minutes ")
    logger.info("========================================")

    # Run immediately once
    logger.info("Running initial audio job...")
    run_audio_generation()

    # schedule audio job only
    schedule.every(2).minutes.do(run_audio_generation)

    while True:
        schedule.run_pending()
        time.sleep(5)   # faster loop for testing


if __name__ == "__main__":
    main()

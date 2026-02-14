#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
⏸️  Pause Publishing Script
═══════════════════════════════════════════════════════════════
إيقاف النشر على Facebook و Instagram لمدة محددة
═══════════════════════════════════════════════════════════════

Usage:
    python pause_publishing.py                    # إيقاف لمدة 12 ساعة (افتراضي)
    python pause_publishing.py 24                 # إيقاف لمدة 24 ساعة
    python pause_publishing.py clear              # إلغاء الإيقاف
    python pause_publishing.py status             # عرض حالة الإيقاف
"""

import sys
import os
import json
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.jobs.publishers_job import (
    set_publishing_pause, 
    clear_publishing_pause, 
    is_publishing_paused,
    PAUSE_FILE
)

def show_status():
    """عرض حالة الإيقاف الحالية"""
    print("\n" + "="*70)
    print("📊 Publishing Status")
    print("="*70)
    
    if not os.path.exists(PAUSE_FILE):
        print("✅ All platforms are active (no pauses)")
        return
    
    try:
        with open(PAUSE_FILE, 'r') as f:
            pauses = json.load(f)
        
        if not pauses:
            print("✅ All platforms are active (no pauses)")
            return
        
        now = datetime.now()
        
        for platform, pause_until_str in pauses.items():
            pause_until = datetime.fromisoformat(pause_until_str)
            
            if now < pause_until:
                remaining = pause_until - now
                hours = remaining.total_seconds() / 3600
                print(f"⏸️  {platform.upper()}: Paused for {hours:.1f} more hours")
                print(f"   Resumes at: {pause_until.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print(f"✅ {platform.upper()}: Pause expired, active now")
        
    except Exception as e:
        print(f"❌ Error reading pause status: {e}")
    
    print("="*70 + "\n")

def main():
    """Main function"""
    
    if len(sys.argv) == 1:
        # Default: pause for 12 hours
        print("\n⏸️  Pausing Facebook & Instagram publishing for 12 hours...")
        set_publishing_pause('facebook', 12)
        set_publishing_pause('instagram', 12)
        print("✅ Done! Telegram will continue publishing normally.")
        show_status()
        
    elif sys.argv[1] == 'clear':
        # Clear all pauses
        print("\n▶️  Clearing all publishing pauses...")
        clear_publishing_pause('all')
        print("✅ Done! All platforms are now active.")
        show_status()
        
    elif sys.argv[1] == 'status':
        # Show status
        show_status()
        
    else:
        # Pause for specified hours
        try:
            hours = int(sys.argv[1])
            print(f"\n⏸️  Pausing Facebook & Instagram publishing for {hours} hours...")
            set_publishing_pause('facebook', hours)
            set_publishing_pause('instagram', hours)
            print("✅ Done! Telegram will continue publishing normally.")
            show_status()
        except ValueError:
            print("❌ Invalid argument. Usage:")
            print("   python pause_publishing.py           # Pause for 12 hours")
            print("   python pause_publishing.py 24        # Pause for 24 hours")
            print("   python pause_publishing.py clear     # Clear pause")
            print("   python pause_publishing.py status    # Show status")
            sys.exit(1)

if __name__ == '__main__':
    main()

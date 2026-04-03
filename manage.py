#!/usr/bin/env python
import os
import sys
import warnings

def main():
    # Suppress pkg_resources deprecation warning from third-party libs (like razorpay)
    warnings.filterwarnings("ignore", category=UserWarning, module='razorpay')
    
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibely_backend.settings')
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()

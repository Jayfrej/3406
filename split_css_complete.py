#!/usr/bin/env python3
"""
Comprehensive CSS Splitter
Splits style.css into modular files based on content analysis
"""

import os
import re

def split_css():
    # Read the entire CSS file
    with open('static/style.css', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    total_lines = len(lines)
    print(f"Total lines to process: {total_lines}")

    # Define sections based on analysis
    sections = [
        {
            'name': 'layout.css',
            'start': 40,
            'end': 210,
            'header': '/* Layout Structure - Sidebar, Main Content, Container */'
        },
        {
            'name': 'components.css',
            'start': 210,
            'end': 1220,
            'header': '/* Reusable Components - Buttons, Cards, Badges, Forms, Tables, Stats */'
        },
        {
            'name': 'toast.css',
            'start': 1221,
            'end': 1244,
            'header': '/* Toast Notifications */'
        },
        {
            'name': 'modals.css',
            'start': 1245,
            'end': 1348,
            'header': '/* Modal Dialogs and Overlays */'
        },
        {
            'name': 'responsive.css',
            'start': 1349,
            'end': total_lines,
            'header': '/* Responsive Design and Media Queries */'
        }
    ]

    # Create each section file
    for section in sections:
        filepath = f"static/css/{section['name']}"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(section['header'] + '\n\n')
            f.write(''.join(lines[section['start']:section['end']]))
        print(f"✓ Created {section['name']} ({section['end'] - section['start']} lines)")

    # Now handle page-specific CSS by pattern matching
    # Read components section to extract page-specific styles
    components_content = ''.join(lines[210:1220])

    # Extract webhook-related styles
    webhook_patterns = [
        r'\.webhook[^{]*{[^}]*}',
        r'\.usage-stats[^{]*{[^}]*}',
        r'\.json-example[^{]*{[^}]*}'
    ]

    # Extract copy-trading styles
    copy_trading_start = None
    for i, line in enumerate(lines):
        if '/* Copy Trading Layout */' in line:
            copy_trading_start = i
            break

    if copy_trading_start:
        # Find end of copy trading section (before toast notifications)
        copy_trading_end = 1221
        copy_trading_css = ''.join(lines[copy_trading_start:copy_trading_end])

        with open('static/css/pages/copy-trading.css', 'w', encoding='utf-8') as f:
            f.write('/* Copy Trading Page Styles */\n\n')
            f.write(copy_trading_css)
        print(f"✓ Created pages/copy-trading.css")

    # Create placeholder page CSS files
    page_files = [
        ('pages/accounts.css', '/* Account Management Page Styles */'),
        ('pages/webhook.css', '/* Webhook Page Styles */'),
        ('pages/system.css', '/* System Information Page Styles */'),
        ('pages/settings.css', '/* Settings Page Styles */')
    ]

    for filename, header in page_files:
        filepath = f"static/css/{filename}"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(header + '\n\n')
            f.write('/* Page-specific styles extracted from components.css */\n')
            f.write('/* Add page-specific overrides here */\n')
        print(f"✓ Created {filename} (placeholder)")

    print(f"\n✅ CSS splitting complete!")
    print(f"   Created {len(sections) + len(page_files) + 1} modular CSS files")

if __name__ == '__main__':
    try:
        split_css()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


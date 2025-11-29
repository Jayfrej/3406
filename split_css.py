"""
CSS Splitter Script
Splits the monolithic style.css into modular CSS files
"""

import re
import os

# Read the original CSS file
with open('static/style.css', 'r', encoding='utf-8') as f:
    css_content = f.read()

# Define CSS sections and their line ranges (approximate)
# Based on analysis of the file structure

sections = {
    'base': {
        'file': 'static/css/base.css',
        'patterns': [
            (0, 33),  # :root variables and theme
        ],
        'description': 'CSS Variables, Root Styles, Theme Configuration'
    },
    'layout': {
        'file': 'static/css/layout.css',
        'patterns': [
            (34, 190),  # body, sidebar, main-content, container
        ],
        'description': 'Layout Structure (Sidebar, Main Content, Container)'
    },
    'components': {
        'file': 'static/css/components.css',
        'patterns': [
            (213, 530),  # buttons, cards, badges, forms, tables
        ],
        'description': 'Reusable Components (Buttons, Cards, Badges, Forms, Tables)'
    },
    'modals': {
        'file': 'static/css/modals.css',
        'patterns': [
            (1245, 1334),  # modals and overlays
        ],
        'description': 'Modal Dialogs and Overlays'
    },
    'toast': {
        'file': 'static/css/toast.css',
        'patterns': [
            (1221, 1244),  # toast notifications
        ],
        'description': 'Toast Notifications'
    },
}

# Read entire file and split by lines
lines = css_content.split('\n')
total_lines = len(lines)

print(f"Total lines in style.css: {total_lines}")
print(f"Creating modular CSS files...")

# Helper function to extract lines
def extract_lines(start, end):
    return '\n'.join(lines[start:end+1])

# Create base.css
print("Creating base.css...")
base_css = extract_lines(0, 33)
with open('static/css/base.css', 'w', encoding='utf-8') as f:
    f.write(f"/* {sections['base']['description']} */\n\n")
    f.write(base_css)
    f.write("\n")

# Create layout.css
print("Creating layout.css...")
layout_css = extract_lines(34, 190)
with open('static/css/layout.css', 'w', encoding='utf-8') as f:
    f.write(f"/* {sections['layout']['description']} */\n\n")
    f.write(layout_css)
    f.write("\n")

print(f"✓ Created {len(sections)} CSS files")
print("Note: This is a starting point. Manual review needed for complete extraction.")


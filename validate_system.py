"""
Full System Validation Script
Checks all aspects of the project for errors and completeness
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

print("="*80)
print("🔍 FULL SYSTEM VALIDATION")
print("="*80)
print()

# Track validation results
issues = []
warnings = []
success_count = 0

def log_success(message):
    global success_count
    success_count += 1
    print(f"✅ {message}")

def log_warning(message):
    warnings.append(message)
    print(f"⚠️  {message}")

def log_error(message):
    issues.append(message)
    print(f"❌ {message}")

# ============================================================================
# 1. CHECK REQUIRED FILES
# ============================================================================
print("\n📁 Checking Required Files...")
print("-" * 80)

required_files = [
    'server.py',
    'setup.py',
    'requirements.txt',
    'start.bat',
    '.env.template',
    'README.md',
]

for file in required_files:
    filepath = PROJECT_ROOT / file
    if filepath.exists():
        log_success(f"Found: {file}")
    else:
        log_error(f"Missing: {file}")

# ============================================================================
# 2. CHECK DIRECTORY STRUCTURE
# ============================================================================
print("\n📂 Checking Directory Structure...")
print("-" * 80)

required_dirs = [
    'app',
    'app/core',
    'app/modules',
    'app/services',
    'app/copy_trading',
    'templates',
    'templates/pages',
    'templates/partials',
    'templates/partials/components',
    'static',
    'static/css',
    'static/css/pages',
    'static/js',
    'static/js/core',
    'static/js/modules',
    'static/js/components',
    'data',
    'logs',
]

for dir_path in required_dirs:
    dirpath = PROJECT_ROOT / dir_path
    if dirpath.exists() and dirpath.is_dir():
        log_success(f"Found directory: {dir_path}")
    else:
        log_error(f"Missing directory: {dir_path}")

# ============================================================================
# 3. CHECK TEMPLATE FILES
# ============================================================================
print("\n📄 Checking Template Files...")
print("-" * 80)

template_files = [
    'templates/base.html',
    'templates/index.html',
    'templates/partials/sidebar.html',
    'templates/partials/sidebar-toggle.html',
    'templates/partials/header.html',
    'templates/partials/components/loading.html',
    'templates/partials/components/toast.html',
    'templates/partials/components/modals.html',
    'templates/pages/accounts.html',
    'templates/pages/webhook.html',
    'templates/pages/copy_trading.html',
    'templates/pages/system.html',
    'templates/pages/settings.html',
]

for template in template_files:
    filepath = PROJECT_ROOT / template
    if filepath.exists():
        log_success(f"Found template: {template}")
    else:
        log_error(f"Missing template: {template}")

# ============================================================================
# 4. CHECK STATIC FILES (CSS)
# ============================================================================
print("\n🎨 Checking CSS Files...")
print("-" * 80)

css_files = [
    'static/css/base.css',
    'static/css/layout.css',
    'static/css/components.css',
    'static/css/toast.css',
    'static/css/modals.css',
    'static/css/responsive.css',
    'static/css/pages/accounts.css',
    'static/css/pages/webhook.css',
    'static/css/pages/copy-trading.css',
    'static/css/pages/system.css',
    'static/css/pages/settings.css',
]

for css_file in css_files:
    filepath = PROJECT_ROOT / css_file
    if filepath.exists():
        log_success(f"Found CSS: {css_file}")
    else:
        log_error(f"Missing CSS: {css_file}")

# ============================================================================
# 5. CHECK STATIC FILES (JavaScript)
# ============================================================================
print("\n📜 Checking JavaScript Files...")
print("-" * 80)

js_files = [
    'static/js/core/utils.js',
    'static/js/core/api.js',
    'static/js/core/auth.js',
    'static/js/core/theme.js',
    'static/js/core/router.js',
    'static/js/components/toast.js',
    'static/js/components/modal.js',
    'static/js/components/loading.js',
    'static/js/modules/webhooks/webhooks.js',
    'static/js/modules/webhooks/webhook-ui.js',
    'static/js/modules/accounts/accounts.js',
    'static/js/modules/accounts/account-ui.js',
    'static/js/modules/copy-trading/copy-trading.js',
    'static/js/modules/copy-trading/copy-trading-ui.js',
    'static/js/modules/system/system.js',
    'static/js/modules/system/system-ui.js',
    'static/js/modules/settings/settings.js',
    'static/js/modules/settings/settings-ui.js',
    'static/js/compat-bridge.js',
    'static/js/main.js',
]

for js_file in js_files:
    filepath = PROJECT_ROOT / js_file
    if filepath.exists():
        log_success(f"Found JS: {js_file}")
    else:
        log_error(f"Missing JS: {js_file}")

# ============================================================================
# 6. CHECK PYTHON MODULES
# ============================================================================
print("\n🐍 Checking Python Modules...")
print("-" * 80)

python_modules = [
    'app/__init__.py',
    'app/core/email.py',
    'app/core/config.py',
    'app/services/accounts.py',
    'app/services/broker.py',
    'app/services/signals.py',
    'app/services/symbols.py',
    'app/services/balance.py',
    'app/modules/webhooks/__init__.py',
    'app/modules/webhooks/routes.py',
    'app/modules/webhooks/services.py',
    'app/modules/accounts/__init__.py',
    'app/modules/accounts/routes.py',
    'app/modules/system/__init__.py',
    'app/modules/system/routes.py',
    'app/copy_trading/__init__.py',
    'app/trades.py',
]

for module in python_modules:
    filepath = PROJECT_ROOT / module
    if filepath.exists():
        log_success(f"Found module: {module}")
    else:
        log_error(f"Missing module: {module}")

# ============================================================================
# 7. CHECK FOR LEGACY/UNUSED FILES
# ============================================================================
print("\n🧹 Checking for Legacy/Unused Files...")
print("-" * 80)

# Check for files that should NOT exist
legacy_files = [
    'mt5_instances',
    'static/index.html',
    'static/index.html.old',
    'static/style.css',
    'static/style.css.bak',
    'static/app.js',
]

for legacy in legacy_files:
    filepath = PROJECT_ROOT / legacy
    if filepath.exists():
        log_warning(f"Legacy file/folder exists: {legacy} (should be removed)")
    else:
        log_success(f"Confirmed removed: {legacy}")

# ============================================================================
# 8. VALIDATE .env.template
# ============================================================================
print("\n🔑 Validating .env.template...")
print("-" * 80)

env_template = PROJECT_ROOT / '.env.template'
if env_template.exists():
    with open(env_template, 'r') as f:
        content = f.read()

    # Check for required variables
    required_vars = [
        'BASIC_USER',
        'BASIC_PASS',
        'SECRET_KEY',
        'WEBHOOK_TOKEN',
        'EXTERNAL_BASE_URL',
        'PORT',
        'EMAIL_ENABLED',
        'SENDER_EMAIL',
    ]

    for var in required_vars:
        if var in content:
            log_success(f"Found env variable: {var}")
        else:
            log_error(f"Missing env variable: {var}")

    # Check for legacy MT5 variables (should NOT exist)
    legacy_vars = ['MT5_MAIN_PATH', 'MT5_INSTANCES_DIR', 'DELETE_INSTANCE_FILES']
    for var in legacy_vars:
        if var in content:
            log_warning(f"Legacy env variable found: {var} (should be removed)")
        else:
            log_success(f"Confirmed removed: {var}")

# ============================================================================
# 9. CHECK PYTHON SYNTAX
# ============================================================================
print("\n🔧 Checking Python Syntax...")
print("-" * 80)

critical_files = ['server.py', 'setup.py']
for pyfile in critical_files:
    filepath = PROJECT_ROOT / pyfile
    if filepath.exists():
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                compile(f.read(), filepath, 'exec')
            log_success(f"Python syntax OK: {pyfile}")
        except SyntaxError as e:
            log_error(f"Syntax error in {pyfile}: {e}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*80)
print("📊 VALIDATION SUMMARY")
print("="*80)
print(f"✅ Passed: {success_count}")
print(f"⚠️  Warnings: {len(warnings)}")
print(f"❌ Errors: {len(issues)}")
print()

if issues:
    print("❌ CRITICAL ISSUES FOUND:")
    for issue in issues:
        print(f"   - {issue}")
    print()

if warnings:
    print("⚠️  WARNINGS:")
    for warning in warnings:
        print(f"   - {warning}")
    print()

if not issues:
    print("✅ ALL CRITICAL CHECKS PASSED!")
    print()
    print("🎉 System validation complete - Project is ready!")
else:
    print("❌ VALIDATION FAILED - Please fix the issues above")
    sys.exit(1)

print("="*80)


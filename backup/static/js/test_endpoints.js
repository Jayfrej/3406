/**
 * @file test_endpoints.js
 * @description Endpoint verification script
 *
 * Usage:
 *   1. Open your browser console on the app page
 *   2. Copy-paste this script and run it
 *   3. Check the results table
 *
 * Or run from Node.js:
 *   node test_endpoints.js http://localhost:5000
 */

const ENDPOINTS = [
  // Account Endpoints
  { method: 'GET', path: '/accounts', description: 'Get all accounts' },
  { method: 'GET', path: '/webhook-url', description: 'Get webhook URL' },
  { method: 'GET', path: '/webhook-accounts', description: 'Get webhook accounts' },

  // Copy Trading Endpoints
  { method: 'GET', path: '/api/pairs', description: 'Get copy trading pairs' },
  { method: 'GET', path: '/api/copy/history?limit=10', description: 'Get copy history' },
  { method: 'GET', path: '/api/copy/master-accounts', description: 'Get master accounts' },
  { method: 'GET', path: '/api/copy/slave-accounts', description: 'Get slave accounts' },

  // Trades Endpoints
  { method: 'GET', path: '/trades?limit=10', description: 'Get trade history' },

  // Settings Endpoints
  { method: 'GET', path: '/api/settings', description: 'Get all settings' },
  { method: 'GET', path: '/api/settings/email', description: 'Get email settings' },
  { method: 'GET', path: '/settings/secret', description: 'Get global secret' },

  // System Endpoints
  { method: 'GET', path: '/api/system/logs?limit=10', description: 'Get system logs' },

  // SSE Endpoints (just check they exist)
  { method: 'HEAD', path: '/events/trades', description: 'Trade events SSE' },
  { method: 'HEAD', path: '/events/copy-trades', description: 'Copy events SSE' },
  { method: 'HEAD', path: '/events/system-logs', description: 'System logs SSE' }
];

async function testEndpoints(baseUrl = '') {
  console.log('🔍 MT5 Trading Bot - Endpoint Verification');
  console.log('='.repeat(60));

  const results = [];

  for (const endpoint of ENDPOINTS) {
    const url = `${baseUrl}${endpoint.path}`;

    try {
      const startTime = Date.now();
      const response = await fetch(url, {
        method: endpoint.method,
        credentials: 'include',
        headers: {
          'Accept': 'application/json'
        }
      });
      const latency = Date.now() - startTime;

      const result = {
        endpoint: endpoint.path,
        method: endpoint.method,
        description: endpoint.description,
        status: response.status,
        ok: response.ok || response.status === 401, // 401 means endpoint exists but needs auth
        latency: `${latency}ms`
      };

      results.push(result);

      const statusIcon = result.ok ? '✅' : '❌';
      console.log(`${statusIcon} ${endpoint.method} ${endpoint.path} - ${response.status} (${latency}ms)`);

    } catch (error) {
      const result = {
        endpoint: endpoint.path,
        method: endpoint.method,
        description: endpoint.description,
        status: 'ERROR',
        ok: false,
        latency: '-',
        error: error.message
      };

      results.push(result);
      console.log(`❌ ${endpoint.method} ${endpoint.path} - ERROR: ${error.message}`);
    }
  }

  console.log('\n' + '='.repeat(60));

  // Summary
  const passed = results.filter(r => r.ok).length;
  const failed = results.filter(r => !r.ok).length;

  console.log(`\n📊 SUMMARY: ${passed}/${results.length} endpoints OK`);

  if (failed > 0) {
    console.log('\n⚠️ FAILED ENDPOINTS:');
    results.filter(r => !r.ok).forEach(r => {
      console.log(`   - ${r.method} ${r.endpoint}: ${r.status} ${r.error || ''}`);
    });
  }

  // Return results for programmatic use
  return {
    total: results.length,
    passed,
    failed,
    results
  };
}

// For browser console usage
if (typeof window !== 'undefined') {
  window.testEndpoints = testEndpoints;
  console.log('💡 Run testEndpoints() to verify all API endpoints');
}

// For Node.js usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { testEndpoints, ENDPOINTS };

  // Auto-run if called directly
  if (require.main === module) {
    const baseUrl = process.argv[2] || 'http://localhost:5000';
    console.log(`Testing endpoints at: ${baseUrl}\n`);
    testEndpoints(baseUrl).then(results => {
      process.exit(results.failed > 0 ? 1 : 0);
    });
  }
}

// For ES module usage
export { testEndpoints, ENDPOINTS };


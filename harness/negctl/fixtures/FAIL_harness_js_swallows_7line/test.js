// quick smoke test
try {
  const result = require('./index.js');
  console.log('OK: ' + Object.keys(result).join(', '));
} catch (e) {
  console.error('FAIL:', e.message);
}

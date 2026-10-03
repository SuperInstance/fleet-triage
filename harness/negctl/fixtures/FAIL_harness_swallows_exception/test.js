try {
  const r = require('./index.js');
  console.log('OK: ' + Object.keys(r).join(', '));
} catch (e) {
  console.error('FAIL:', e.message);
}

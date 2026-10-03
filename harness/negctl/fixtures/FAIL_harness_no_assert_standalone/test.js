const { Observation } = require('@superinstance/observation-primitive');
const { attest, aggregateTrust } = require('./index.js');

const o = new Observation({
  subject: 'substrate',
  predicate: 'has_primitive',
  object: 'observation',
  issuer: 'casey',
});

const a1 = attest(o, { id: 'jane' }, { trust: 0.9 });
console.log('aggregate trust:', aggregateTrust([a1]).toFixed(3));
console.log('irrevocable:', a1.is_irrevocable);

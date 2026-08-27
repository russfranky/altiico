import assert from 'node:assert/strict';
import test from 'node:test';
import { createRequire } from 'node:module';
const require=createRequire(import.meta.url);const {localAvatarCatalogAdapter}=require('../../.tmp/catalog-test-build/adapters/local/adapter.js');
test('local adapter filters ready sets',async()=>{const r=await localAvatarCatalogAdapter.listAvatarSets({readiness:'ready'});assert.ok(r.items.length>0);assert.ok(r.items.every(x=>x.readiness==='ready'));assert.equal(r.provenance.sourceMode,'fixture')});
test('local adapter resolves set and avatar routes',async()=>{const c=await localAvatarCatalogAdapter.listAvatarSets();const s=await localAvatarCatalogAdapter.getAvatarSetBySlug(c.items[0].slug);assert.ok(s);const a=await localAvatarCatalogAdapter.getAvatarByRoute(s.slug,s.avatarSlots[0].avatarSlug);assert.ok(a);assert.equal(a.identity.productSetId,s.id)});
test('missing records return null',async()=>{assert.equal(await localAvatarCatalogAdapter.getAvatarSetBySlug('missing'),null);assert.equal(await localAvatarCatalogAdapter.getAvatarByRoute('missing','missing'),null)});

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {issueNumber, issueURL, readStatus, validate, STATUS_MARKER} from '../web/config.js';
const catalog = JSON.parse(fs.readFileSync(new URL('../web/catalog.json', import.meta.url)));
const copy = () => structuredClone(catalog.defaults);

test('default configuration is bounded and round-trips into a GitHub issue URL', () => {
  const url = new URL(issueURL(copy(), catalog));
  assert.equal(url.origin, 'https://github.com');
  assert.equal(url.pathname, '/huhao0208/tcl-firmware-builder/issues/new');
  assert.match(url.searchParams.get('body'), /<!-- TVFW:1 -->/);
  const body = url.searchParams.get('body').match(/```json\n([\s\S]*?)\n```/)[1];
  assert.deepEqual(JSON.parse(body), validate(copy(), catalog));
});
test('reject incompatible root, desktop, key and field choices', () => {
  assert.throws(() => validate({...copy(), root: false}, catalog));
  assert.throws(() => validate({...copy(), launcher: 'stock'}, catalog));
  assert.throws(() => validate({...copy(), remove_apps: ['shell;id']}, catalog));
  assert.throws(() => validate({...copy(), command: 'id'}, catalog));
  assert.throws(() => validate({...copy(), root: 'true'}, catalog));
});
test('request numbers are positive integers, never paths or expressions', () => {
  for (const value of ['', '0', '-1', '1/../../', '1;id', '123456789']) assert.throws(() => issueNumber(value));
  assert.equal(issueNumber(' 17 '), 17);
});
const key = '0123456789abcdef';
const status = {schema: 1, phase: 'ready', message: '完成', build_id: key, zip_file: `TCL-T800T11-V178-${key}.zip`, zip_sha256: 'a'.repeat(64), release_url: `https://github.com/${catalog.repository}/releases/tag/build-${key}`, run_url: `https://github.com/${catalog.repository}/actions/runs/123`};
const comment = (value, login = 'github-actions[bot]') => ({user: {login}, body: STATUS_MARKER + '\n```json\n' + JSON.stringify(value) + '\n```'});
test('trust only the GitHub Actions bot and exact repository URLs', () => {
  assert.equal(readStatus([comment(status)], catalog.repository).phase, 'ready');
  assert.equal(readStatus([comment(status, 'attacker')], catalog.repository), null);
  assert.equal(readStatus([comment({...status, release_url: 'https://evil.example/package'})], catalog.repository), null);
  assert.equal(readStatus([comment({...status, run_url: 'https://github.com/other/repo/actions/runs/123'})], catalog.repository), null);
  assert.equal(readStatus([comment({...status, zip_file: '../../bad.zip'})], catalog.repository), null);
});
test('malformed, empty and nonfinal status handling', () => {
  assert.equal(readStatus([], catalog.repository), null);
  assert.equal(readStatus([{user: {login:'github-actions[bot]'},body: STATUS_MARKER+'\n```json\n{\n```'}], catalog.repository), null);
  assert.equal(readStatus([comment({...status, phase: 'building', release_url: null})], catalog.repository).phase, 'building');
});

import { resolveApiBaseUrl } from './api-base-url';

describe('resolveApiBaseUrl', () => {
  // Host podajemy wprost: w Chrome `window.location` nie da się podmienić (non-configurable).
  it('uses LAN host for dev when page is served from LAN', () => {
    expect(resolveApiBaseUrl('203.0.113.50')).toBe('http://203.0.113.50:8000');
  });

  it('uses loopback when page is on localhost in browser dev', () => {
    expect(resolveApiBaseUrl('127.0.0.1')).toBe('http://127.0.0.1:8000');
  });
});

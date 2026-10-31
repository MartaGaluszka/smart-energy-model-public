import { resolveApiBaseUrl } from './api-base-url';

describe('resolveApiBaseUrl', () => {
  const originalLocation = globalThis.location;

  afterEach(() => {
    Object.defineProperty(globalThis, 'location', {
      value: originalLocation,
      configurable: true,
    });
  });

  it('uses LAN host for dev when page is served from LAN', () => {
    Object.defineProperty(globalThis, 'location', {
      value: { hostname: '203.0.113.50' },
      configurable: true,
    });
    expect(resolveApiBaseUrl()).toBe('http://203.0.113.50:8000');
  });

  it('uses loopback when page is on localhost in browser dev', () => {
    Object.defineProperty(globalThis, 'location', {
      value: { hostname: '127.0.0.1' },
      configurable: true,
    });
    expect(resolveApiBaseUrl()).toBe('http://127.0.0.1:8000');
  });
});

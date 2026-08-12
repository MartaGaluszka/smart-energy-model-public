import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, map, of, shareReplay, switchMap, tap } from 'rxjs';
import { environment } from '../../environments/environment';

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

const ACCESS_TOKEN_KEY = 'se_access_token';
const REFRESH_TOKEN_KEY = 'se_refresh_token';

// MVP: brak jeszcze ekranu logowania (Faza 1, T1.5) — do czasu jego powstania
// klient sam zakłada/loguje jedno demo konto, żeby endpointy chronione JWT
// dało się zademonstrować na żywym backendzie z §12.
// Uwaga: `email-validator` (backend) odrzuca TLD zarezerwowane jak .local/.test/.invalid
// jako "special-use domain" — stąd zwykła domena, nie *.local.
const DEMO_EMAIL = 'mobile.demo@example.com';
const DEMO_PASSWORD = 'demo12345678';

/**
 * Zarządza sesją JWT klienta wobec `api/` (FastAPI, Faza 0). Patrz
 * docs/PROJEKT_APLIKACJA_MOBILNA.md §12.3 (Auth) i §5 (decyzja: własny IdP + vault Fox).
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly baseUrl = environment.apiBaseUrl;
  private session$: Observable<string | null> | null = null;

  constructor(private readonly http: HttpClient) {}

  getAccessToken(): string | null {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  }

  /** Zwraca aktywny access token, logując/rejestrując demo sesję przy pierwszym użyciu. */
  ensureSession(): Observable<string | null> {
    const existing = this.getAccessToken();
    if (existing) {
      return of(existing);
    }
    if (!this.session$) {
      this.session$ = this.login(DEMO_EMAIL, DEMO_PASSWORD).pipe(
        catchError(() => this.register(DEMO_EMAIL, DEMO_PASSWORD)),
        catchError((err) => {
          console.warn('[AuthService] Nie udało się utworzyć sesji demo — API offline?', err);
          return of(null);
        }),
        shareReplay(1),
      );
    }
    return this.session$;
  }

  private login(email: string, password: string): Observable<string> {
    return this.http
      .post<TokenResponse>(`${this.baseUrl}/api/v1/auth/login`, { email, password })
      .pipe(
        tap((tokens) => this.storeTokens(tokens)),
        map((tokens) => tokens.access_token),
      );
  }

  private register(email: string, password: string): Observable<string> {
    return this.http
      .post<TokenResponse>(`${this.baseUrl}/api/v1/auth/register`, { email, password })
      .pipe(
        tap((tokens) => this.storeTokens(tokens)),
        map((tokens) => tokens.access_token),
        catchError(() => this.login(email, password)),
      );
  }

  /**
   * Access token żyje tylko `JWT_ACCESS_TOKEN_MINUTES` (domyślnie 30 min) — bez tego
   * ApiService po tym czasie dostawałby same 401 i trwale pokazywał dane demo, nawet
   * gdy backend działa. Wołane z `ApiService.authed()` po pierwszym 401.
   */
  renewSession(): Observable<string | null> {
    this.session$ = null;
    return this.refreshAccessToken().pipe(
      switchMap((token) => {
        if (token) {
          return of(token);
        }
        this.logout();
        return this.ensureSession();
      }),
    );
  }

  private refreshAccessToken(): Observable<string | null> {
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (!refreshToken) {
      return of(null);
    }
    return this.http
      .post<{ access_token: string }>(`${this.baseUrl}/api/v1/auth/refresh`, { refresh_token: refreshToken })
      .pipe(
        tap((res) => localStorage.setItem(ACCESS_TOKEN_KEY, res.access_token)),
        map((res) => res.access_token),
        catchError(() => of(null)),
      );
  }

  private storeTokens(tokens: TokenResponse): void {
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
  }

  logout(): void {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    this.session$ = null;
  }
}

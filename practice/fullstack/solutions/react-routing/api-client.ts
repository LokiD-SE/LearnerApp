// A small typed client for the SandPay dashboard API (fictional). Reference solution.

/** An HTTP error from the API, or status 0 when the request never got a response. */
export class ApiError extends Error {
  override readonly name = 'ApiError';
  constructor(
    readonly status: number,
    readonly title: string,
    readonly url: string,
  ) {
    super(`${status} ${title} (${url})`);
  }
}

export interface GetOptions<T> {
  /** Checks the JSON body and returns it typed - types alone check nothing at runtime. */
  parse: (body: unknown) => T;
  signal?: AbortSignal;
  baseUrl?: string;
}

/** The `title` of an RFC 9457 Problem Details body, if the body is one. */
async function problemTitle(response: Response): Promise<string | undefined> {
  const type = response.headers.get('content-type') ?? '';
  if (!type.includes('json')) return undefined;
  try {
    const body: unknown = await response.json();
    if (typeof body === 'object' && body !== null && 'title' in body && typeof body.title === 'string') {
      return body.title;
    }
  } catch {
    // An unreadable error body still is an error - fall back to the status text.
  }
  return undefined;
}

export async function apiGet<T>(path: string, options: GetOptions<T>): Promise<T> {
  const url = `${options.baseUrl ?? '/api'}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      headers: { Accept: 'application/json' },
      ...(options.signal ? { signal: options.signal } : {}),
    });
  } catch (error) {
    // An abort is the caller's decision, not a failure: let it through unchanged.
    if (error instanceof Error && error.name === 'AbortError') throw error;
    throw new ApiError(0, 'Network error', url);
  }
  // fetch resolves for every HTTP status; only response.ok (200-299) means success.
  if (!response.ok) {
    const title = (await problemTitle(response)) ?? (response.statusText || 'Request failed');
    throw new ApiError(response.status, title, url);
  }
  return options.parse(await response.json());
}

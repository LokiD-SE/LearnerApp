// A small typed client for the SandPay dashboard API (fictional).
//
// Write apiGet so that it:
//  1. sends GET `${baseUrl ?? '/api'}${path}` with the header `Accept: application/json`, passing
//     options.signal to fetch so the caller can cancel the request;
//  2. on a 2xx response, reads the JSON body and returns options.parse(body);
//  3. on any other status, throws an ApiError with that status, the `title` of a Problem Details
//     (JSON) body when there is one - otherwise the response's statusText - and the URL;
//  4. when fetch itself rejects: re-throws an abort (error.name === 'AbortError') unchanged, and turns
//     anything else (a network error) into ApiError(0, 'Network error', url).

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

export async function apiGet<T>(path: string, options: GetOptions<T>): Promise<T> {
  // TODO: replace this naive version - it ignores the status, the signal and the parser.
  const response = await fetch(`/api${path}`);
  return (await response.json()) as T;
}

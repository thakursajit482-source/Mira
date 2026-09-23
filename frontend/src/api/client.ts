/**
 * Centralized API HTTP client for Mira.
 * Interacts with FastAPI backend at /api/v1.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

interface RequestOptions extends RequestInit {
  timeoutMs?: number;
}

export async function apiClient<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = 15000, ...fetchOptions } = options;

  // Ensure leading slash
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const url = `${API_BASE_URL}${cleanEndpoint}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...fetchOptions.headers,
      },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      let errorMessage = `HTTP Error ${response.status}: ${response.statusText}`;
      let errorData: unknown = null;

      try {
        errorData = await response.json();
        if (typeof errorData === 'object' && errorData !== null) {
          const apiErr = errorData as { detail?: unknown };
          if (typeof apiErr.detail === 'string') {
            errorMessage = apiErr.detail;
          } else if (Array.isArray(apiErr.detail)) {
            // FastAPI validation error array
            errorMessage = apiErr.detail
              .map((err: { msg?: string; loc?: string[] }) => err.msg || JSON.stringify(err))
              .join(', ');
          } else if (typeof apiErr.detail === 'object' && apiErr.detail !== null) {
            // Structured error detail object (e.g. { message: "...", errors: [...] })
            const detailObj = apiErr.detail as { message?: string; errors?: string[] };
            if (detailObj.message) {
              errorMessage = detailObj.errors && detailObj.errors.length > 0
                ? `${detailObj.message} (${detailObj.errors.join('; ')})`
                : detailObj.message;
            }
          }
        }
      } catch {
        // Non-JSON error body
      }

      throw new ApiError(errorMessage, response.status, errorData);
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    return (await response.json()) as T;
  } catch (error: unknown) {
    clearTimeout(timeoutId);
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError('Request timed out. Please try again.', 408);
    }
    const message = error instanceof Error ? error.message : 'Network request failed';
    throw new ApiError(message, 0);
  }
}

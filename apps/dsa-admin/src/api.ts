import type { ApiError } from './types'

export async function requestJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-DSA-Auth-Client': 'admin',
      ...(options?.headers ?? {}),
    },
    ...options,
  })

  if (!response.ok) {
    let detail: unknown
    try {
      detail = await response.json()
    } catch {
      detail = await response.text()
    }
    const err = new Error(`Request failed: ${response.status}`) as ApiError
    err.status = response.status
    err.detail = detail
    throw err
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

export async function optionalRequest<T>(promise: Promise<T>, fallback: T): Promise<T> {
  try {
    return await promise
  } catch (err) {
    if ((err as ApiError).status === 403) {
      return fallback
    }
    throw err
  }
}

export function getErrorMessage(error: unknown): string {
  const apiError = error as ApiError
  const detail = apiError.detail as { detail?: { message?: string }; message?: string } | undefined
  return detail?.detail?.message ?? detail?.message ?? apiError.message ?? '请求失败'
}

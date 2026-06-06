export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

export function apiPath(path: string) {
  return `${API_BASE_URL}${path}`;
}

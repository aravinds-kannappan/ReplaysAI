// ReplaysAI runs fully free with no login. This shim keeps the existing
// `getToken`-based fetch helpers working: there is simply never a token, so the
// backend treats every request as an anonymous guest.
export function useAuth() {
  return { getToken: async (): Promise<string | null> => null };
}

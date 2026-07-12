// Anonymous device identity.
//
// One UUID per browser, generated on first use and kept in localStorage. It is
// the durable key the API uses for a fan's picks, points, and leaderboard rank
// (sent on every request as the `X-Device-Id` header, see lib/api.ts). No login,
// no PII: the id is meaningless outside this browser.

const DEVICE_KEY = "replaysai:uid";

function makeId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  // Fallback for older browsers.
  return "dev-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export function getDeviceId(): string {
  if (typeof window === "undefined") return "";
  let id = window.localStorage.getItem(DEVICE_KEY);
  if (!id) {
    id = makeId();
    window.localStorage.setItem(DEVICE_KEY, id);
  }
  return id;
}

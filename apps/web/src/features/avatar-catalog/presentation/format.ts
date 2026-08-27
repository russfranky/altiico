export function displayOptional(value: string | null) {
  return value ?? 'NOT CONNECTED';
}

export function displayReachability(value: boolean | null) {
  if (value === true) return 'REACHABLE';
  if (value === false) return 'UNREACHABLE';
  return 'NO CLAIM';
}

export function displayBytes(value: number | null) {
  if (value === null) return 'NOT CONNECTED';
  return `${(value / 1_000_000).toFixed(2)} MB`;
}

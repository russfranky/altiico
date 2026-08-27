export function normalizeChain(value: string) {
  return value.trim().toLowerCase();
}

export function normalizeContract(value: string) {
  const trimmed = value.trim();
  return /^0x[0-9a-f]+$/i.test(trimmed) ? trimmed.toLowerCase() : trimmed;
}

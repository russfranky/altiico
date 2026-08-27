import { existsSync,statSync } from 'node:fs';import { dirname,join,resolve } from 'node:path';
export function importSpecifiers(s){return [...new Set([...s.matchAll(/(?:from\s+|import\s*)['"]([^'"]+)['"]/g),...s.matchAll(/import\s*\(\s*['"]([^'"]+)['"]\s*\)/g)].map(m=>m[1]))]}
export const isLocalSpecifier=s=>s.startsWith('.')||s.startsWith('@/');
export function resolveLocalImport(from,s){if(!isLocalSpecifier(s))return null;const b=s.startsWith('@/')?resolve('apps/web/src',s.slice(2)):resolve(dirname(from),s);return [b,`${b}.ts`,`${b}.tsx`,`${b}.css`,join(b,'index.ts'),join(b,'index.tsx')].find(p=>existsSync(p)&&statSync(p).isFile())??null}

import { readdir } from 'node:fs/promises';
import { join } from 'node:path';
export async function walkFiles(dir){const out=[];for(const e of await readdir(dir,{withFileTypes:true})){const p=join(dir,e.name);out.push(...(e.isDirectory()?await walkFiles(p):[p]))}return out}

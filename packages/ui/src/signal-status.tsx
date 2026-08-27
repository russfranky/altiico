import type { HTMLAttributes } from 'react';
type Props=HTMLAttributes<HTMLSpanElement>&{label?:string};
export function SignalStatus({label='ONLINE',className='',...props}:Props){return <span className={`altiico-signal-status ${className}`.trim()} {...props}><span className="altiico-signal-dot" aria-hidden="true"/><span>{label}</span></span>}

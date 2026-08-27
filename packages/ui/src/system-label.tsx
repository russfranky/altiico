import type { HTMLAttributes,ReactNode } from 'react';
type Props=HTMLAttributes<HTMLSpanElement>&{children:ReactNode;tone?:'muted'|'signal'|'ink'};
export function SystemLabel({children,className='',tone='muted',...props}:Props){return <span className={`altiico-system-label altiico-system-label--${tone} ${className}`.trim()} {...props}>{children}</span>}

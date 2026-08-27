import type { HTMLAttributes,ReactNode } from 'react';
type Props=HTMLAttributes<HTMLDivElement>&{children:ReactNode;corners?:boolean};
export function TechnicalFrame({children,className='',corners=true,...props}:Props){return <div className={`altiico-technical-frame ${corners?'altiico-technical-frame--corners':''} ${className}`.trim()} data-altiico-frame {...props}>{children}</div>}

import type { AnchorHTMLAttributes,ReactNode } from 'react';
type Props=AnchorHTMLAttributes<HTMLAnchorElement>&{children:ReactNode;variant?:'primary'|'secondary'|'quiet'};
export function SystemButton({children,className='',variant='secondary',...props}:Props){return <a className={`altiico-system-button altiico-system-button--${variant} ${className}`.trim()} {...props}><span>{children}</span><span aria-hidden="true">→</span></a>}

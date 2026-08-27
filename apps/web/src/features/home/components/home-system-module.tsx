import { SystemButton, SystemIcon, SystemLabel } from '@altiico/ui';

type Props = {
  index: string;
  icon: 'ii' | 'cube' | 'crosshair';
  title: string;
  descriptor: string;
  action: string;
  href: string;
};

export function HomeSystemModule({ index, icon, title, descriptor, action, href }: Props) {
  return (
    <article className="systemModule">
      <div className="systemModuleTopline"><SystemLabel tone="signal">{index} / SYSTEM</SystemLabel><SystemIcon name={icon} /></div>
      <div className="systemModuleCopy"><h2>{title}</h2><SystemLabel tone="muted">{descriptor}</SystemLabel></div>
      <SystemButton variant="secondary" href={href}>{action}</SystemButton>
    </article>
  );
}

type Props = {
  children: React.ReactNode;
  className?: string;
  /** Use muted background for alternating sections */
  variant?: 'default' | 'muted';
};

export default function PageSection({ children, className = '', variant = 'default' }: Props) {
  return (
    <section
      className={`py-16 ${variant === 'muted' ? 'bg-muted/30' : 'bg-background'} ${className}`}
    >
      <div className="max-w-7xl mx-auto px-4">
        {children}
      </div>
    </section>
  );
}

const GITHUB_URL = 'https://github.com/missmoss/hooli-survival';
const SUBSTACK_URL = 'https://clairetsao.substack.com/p/building-hooli-survival-software?r=w4jh';

function GitHubIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4 fill-current">
      <path d="M12 2C6.48 2 2 6.59 2 12.25c0 4.53 2.87 8.37 6.84 9.73.5.1.68-.22.68-.49 0-.24-.01-1.04-.01-1.88-2.78.62-3.37-1.21-3.37-1.21-.46-1.2-1.11-1.52-1.11-1.52-.91-.64.07-.63.07-.63 1 .07 1.53 1.06 1.53 1.06.9 1.57 2.35 1.12 2.92.86.09-.67.35-1.12.63-1.38-2.22-.26-4.56-1.15-4.56-5.12 0-1.13.39-2.05 1.03-2.77-.1-.26-.45-1.31.1-2.74 0 0 .84-.28 2.75 1.06A9.3 9.3 0 0 1 12 6.92c.85 0 1.71.12 2.51.37 1.91-1.34 2.75-1.06 2.75-1.06.55 1.43.2 2.48.1 2.74.64.72 1.03 1.64 1.03 2.77 0 3.98-2.34 4.85-4.57 5.11.36.32.68.94.68 1.89 0 1.37-.01 2.47-.01 2.81 0 .27.18.6.69.49A10.25 10.25 0 0 0 22 12.25C22 6.59 17.52 2 12 2Z" />
    </svg>
  );
}

function SubstackIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4 fill-none">
      <rect x="4" y="4" width="16" height="3" fill="currentColor" />
      <rect x="4" y="9" width="16" height="2.5" fill="currentColor" />
      <rect x="4" y="13" width="16" height="2.5" fill="currentColor" />
      <path d="M4 18.5h16V20H4z" fill="currentColor" />
    </svg>
  );
}

function LinkButton({
  href,
  label,
  className,
  children,
}: {
  href: string;
  label: string;
  className: string;
  children: React.ReactNode;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      aria-label={label}
      title={label}
      className={`flex h-10 w-10 items-center justify-center rounded-full border shadow-frame backdrop-blur-sm transition hover:-translate-y-0.5 ${className}`}
    >
      {children}
    </a>
  );
}

export default function SiteLinksDock() {
  return (
    <div className="fixed left-3 z-20 flex items-center gap-2 bottom-[calc(env(safe-area-inset-bottom)+5.25rem)] md:bottom-4">
      <LinkButton href={GITHUB_URL} label="GitHub" className="border-black/85 bg-black text-white hover:bg-white hover:text-black">
        <GitHubIcon />
      </LinkButton>
      <LinkButton href={SUBSTACK_URL} label="Substack" className="border-[#ff6719]/60 bg-[#ff6719] text-white hover:bg-white hover:text-[#ff6719]">
        <SubstackIcon />
      </LinkButton>
    </div>
  );
}

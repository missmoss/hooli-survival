import type { Metadata } from 'next';
import './globals.css';

import { I18nProvider } from '@/lib/i18n';
import SiteLinksDock from '@/components/SiteLinksDock';

export const metadata: Metadata = {
  metadataBase: new URL('https://hooli-survival.vercel.app'),
  title: 'Hooli Survival',
  description: 'Corporate survival simulator. Every meeting says it is aligning direction, and the direction still changes every week.',
  openGraph: {
    title: 'Hooli Survival',
    description: 'Corporate survival simulator. Every meeting says it is aligning direction, and the direction still changes every week.',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <script async src="https://vibejam.cc/2026/widget.js" />
      </head>
      <body>
        <I18nProvider>{children}</I18nProvider>
        <SiteLinksDock />
      </body>
    </html>
  );
}

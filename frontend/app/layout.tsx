import type { Metadata } from 'next';
import Script from 'next/script';
import './globals.css';

import { I18nProvider } from '@/lib/i18n';

export const metadata: Metadata = {
  title: 'Hooli Survival',
  description: 'Corporate survival simulator',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <Script src="https://vibejam.cc/2026/widget.js" strategy="afterInteractive" />
        <I18nProvider>{children}</I18nProvider>
      </body>
    </html>
  );
}

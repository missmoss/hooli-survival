import type { Metadata } from 'next';
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
      <head>
        <script async src="https://vibejam.cc/2026/widget.js" />
      </head>
      <body>
        <I18nProvider>{children}</I18nProvider>
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import { Manrope } from "next/font/google";
import "./globals.css";

const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
});

export const metadata: Metadata = {
  title: "BaseballPath",
  description: "The AI that gets you recruited! Trusted by coaches. Built by players. Powered by AI.",
  icons: {
    icon: '/logo_concepts/Second Logo/Favicon/Favicon-02.jpg',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${manrope.variable} font-sans antialiased`}
        style={{ fontFamily: 'var(--font-manrope)' }}
        suppressHydrationWarning={true}
      >
        {children}
      </body>
    </html>
  );
}

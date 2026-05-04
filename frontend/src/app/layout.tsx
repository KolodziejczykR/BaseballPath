import type { Metadata } from "next";
import { Sora, Fraunces } from "next/font/google";
import "./globals.css";

const sora = Sora({
  subsets: ["latin"],
  variable: "--font-sora",
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  display: "swap",
  axes: ["opsz"],
});

export const metadata: Metadata = {
  title: "BaseballPath",
  description: "The AI that gets you recruited! Trusted by coaches. Built by players. Powered by AI.",
  icons: {
    icon: "/BP-cream-logo-circle.png",
    apple: "/BP-cream-logo-circle.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${sora.variable} ${fraunces.variable}`}>
      <body className="font-sans antialiased" suppressHydrationWarning={true}>
        {children}
      </body>
    </html>
  );
}

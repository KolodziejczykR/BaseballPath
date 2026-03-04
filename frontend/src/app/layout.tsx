import type { Metadata } from "next";
import "./globals.css";

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
    <html lang="en">
      <body className="font-sans antialiased" suppressHydrationWarning={true}>
        {children}
      </body>
    </html>
  );
}

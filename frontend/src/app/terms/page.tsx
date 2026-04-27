import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms and Conditions | BaseballPath",
  description: "BaseballPath Terms and Conditions.",
};

export default function TermsPage() {
  const html = fs.readFileSync(
    path.join(process.cwd(), "src/app/terms/content.html"),
    "utf-8",
  );

  return (
    <main className="min-h-screen bg-[var(--warm-cream)] py-16 px-4">
      <div
        className="max-w-3xl mx-auto bg-white rounded-2xl shadow-sm border border-[var(--walnut)]/10 p-8 md:p-12"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </main>
  );
}
